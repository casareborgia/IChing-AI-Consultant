"""크레딧 operation 서비스 단위 테스트 (DB 없이 실행).

여기서는 DB에 붙지 않는다. 대신 세 가지를 확인한다.

  1. 계약이 정한 순수 판정 — 키 검증, 요청 지문, 상태 매핑.
  2. 발행되는 SQL이 원자성 조건을 실제로 달고 나가는지. '조건부 UPDATE로
     했다'는 주장은 문장을 들여다봐야 확인된다.
  3. 모델과 마이그레이션이 계약이 요구한 DB 제약을 실제로 선언하는지.

동시성·경합의 최종 판정은 폐기 DB가 있어야 한다. 그쪽은 통합 인수 테스트의 몫이다.
"""

import pathlib
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import postgresql

from core.models.counsel import CreditLedger, CreditOperation, UserProfile
from services import credit_operation_service as svc
from services.credit_service import CONSULTATION_CREDIT_COST, WELCOME_CREDITS


# --- 테스트용 가짜 세션 ---------------------------------------------------------


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def one_or_none(self):
        return self._value


class RecordingSession:
    """실행된 문장을 PostgreSQL 방언으로 컴파일해 모아 두는 세션 대역.

    반환값은 미리 넣어둔 큐에서 차례로 꺼낸다. 큐가 비면 None을 돌려준다.
    """

    def __init__(self, results=None):
        self.statements: list[str] = []
        self._results = list(results or [])
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement, *args, **kwargs):
        try:
            self.statements.append(
                str(statement.compile(dialect=postgresql.dialect()))
            )
        except Exception:  # pragma: no cover - 컴파일 불가 문장은 원문으로
            self.statements.append(str(statement))
        value = self._results.pop(0) if self._results else None
        return _FakeResult(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    def sql_matching(self, needle: str) -> list[str]:
        return [s for s in self.statements if needle in s]


def _squash(sql: str) -> str:
    """줄바꿈·들여쓰기 차이 때문에 검사가 깨지지 않도록 공백을 하나로 만든다."""
    return re.sub(r"\s+", " ", sql)


# --- 1. 순수 판정 --------------------------------------------------------------


def test_missing_idempotency_key_is_rejected_before_any_work():
    for raw in (None, "", "   "):
        with pytest.raises(svc.IdempotencyKeyError) as exc:
            svc.validate_idempotency_key(raw)
        assert exc.value.code == svc.CODE_IDEMPOTENCY_KEY_REQUIRED


def test_malformed_idempotency_key_is_rejected():
    # 너무 짧거나, 공백·경로 문자가 섞이거나, 상한을 넘는 값
    for raw in ("short", "has space", "a/b/c", "x" * 256, "?" * 12):
        with pytest.raises(svc.IdempotencyKeyError) as exc:
            svc.validate_idempotency_key(raw)
        assert exc.value.code == svc.CODE_IDEMPOTENCY_KEY_INVALID


def test_browser_crypto_random_uuid_is_a_valid_key():
    """프런트가 crypto.randomUUID()로 만든 값이 그대로 통과해야 한다."""
    key = str(uuid.uuid4())
    assert svc.validate_idempotency_key(f"  {key}  ") == key


def test_request_hash_separates_endpoints_and_bodies():
    start = svc.compute_request_hash(svc.ENDPOINT_START, {"question": "취업 고민"})
    same = svc.compute_request_hash(svc.ENDPOINT_START, {"question": "취업 고민"})
    other_body = svc.compute_request_hash(svc.ENDPOINT_START, {"question": "다른 고민"})
    other_endpoint = svc.compute_request_hash(svc.ENDPOINT_TURN, {"question": "취업 고민"})

    assert start == same, "같은 body는 같은 지문이어야 재시도가 재생된다"
    assert start != other_body, "다른 body는 409로 갈라져야 한다"
    assert start != other_endpoint
    assert len(start) == 64


def test_request_hash_does_not_embed_the_utterance():
    """상담 발화 원문이 지문에 남지 않는다."""
    secret = "회사를 그만두고 싶습니다"
    digest = svc.compute_request_hash(svc.ENDPOINT_START, {"question": secret})
    assert secret not in digest
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_contract_constants_match_credit_operation_v1():
    assert CONSULTATION_CREDIT_COST == 10
    assert WELCOME_CREDITS == 50
    assert svc.TERMINAL_STATUSES == {"SUCCEEDED", "RELEASED", "REJECTED"}
    assert svc.STATUS_PROCESSING == "PROCESSING"
    assert svc.CODE_IDEMPOTENCY_KEY_REUSED == "IDEMPOTENCY_KEY_REUSED"
    assert svc.CODE_OPERATION_IN_PROGRESS == "OPERATION_IN_PROGRESS"
    assert svc.OPERATION_LEASE_SECONDS > 600


def test_json_safe_keeps_snapshot_storable():
    """스냅샷 저장이 상담 자체를 실패시키면 안 된다."""
    payload = {"when": datetime(2026, 9, 9, tzinfo=timezone.utc), "n": 1, "ok": True}
    safe = svc.json_safe(payload)
    assert safe["n"] == 1 and safe["ok"] is True
    assert isinstance(safe["when"], str)


def test_naive_lease_timestamps_are_compared_as_utc():
    naive = datetime(2026, 9, 9, 12, 0, 0)
    assert svc._as_aware(naive).tzinfo is timezone.utc
    assert svc._as_aware(None) is None


def test_replay_outcome_maps_terminal_states():
    op = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_SUCCEEDED,
        amount=10,
        credit_delta=-10,
        fencing_token=str(uuid.uuid4()),
        balance_snapshot=40,
        response_snapshot={"user_facing_message": "ok"},
    )
    outcome = svc._replay_outcome(op)
    assert outcome.kind == svc.KIND_REPLAY
    assert outcome.credit_delta == -10
    assert outcome.remaining_credits == 40
    assert outcome.response_snapshot == {"user_facing_message": "ok"}


def test_replay_outcome_treats_unset_delta_as_zero():
    """종결 전 행을 재생해도 임의의 차감으로 읽히지 않는다."""
    op = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_TURN,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_RELEASED,
        amount=10,
        credit_delta=None,
        fencing_token=str(uuid.uuid4()),
    )
    assert svc._replay_outcome(op).credit_delta == 0


# --- 2. 발행되는 SQL의 원자성 ---------------------------------------------------


@pytest.mark.asyncio
async def test_reserve_debits_atomically_and_commits_once():
    """예약은 조건부 UPDATE 한 문장으로 하고, 짧은 트랜잭션으로 닫는다."""
    session = RecordingSession(results=[None, "op-1", 40])
    outcome = await svc.begin_operation(
        session,
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key=str(uuid.uuid4()),
        request_hash="h" * 64,
        amount=10,
    )

    assert outcome.kind == svc.KIND_RESERVED
    assert outcome.credit_delta == -10
    assert outcome.remaining_credits == 40
    assert outcome.fencing_token, "실행 주체를 가릴 fencing token이 있어야 한다"
    assert session.commits == 1, "예약은 한 번 커밋하고 닫는다"

    balance_updates = session.sql_matching("UPDATE profiles")
    assert len(balance_updates) == 1
    # 잔액이 모자라면 0행이 갱신되게 하는 조건이 문장 안에 있어야 한다.
    assert "credit_balance >=" in _squash(balance_updates[0])

    debit = session.sql_matching("INSERT INTO credit_ledger")
    assert len(debit) == 1
    assert "ON CONFLICT DO NOTHING" in _squash(debit[0])


@pytest.mark.asyncio
async def test_operation_insert_uses_idempotency_scope():
    """멱등 키의 범위는 (사용자, endpoint)다."""
    session = RecordingSession(results=[None, "op-1", 40])
    await svc.begin_operation(
        session,
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_TURN,
        idempotency_key=str(uuid.uuid4()),
        request_hash="h" * 64,
    )
    insert = _squash(session.sql_matching("INSERT INTO credit_operations")[0])
    assert "ON CONFLICT (user_id, endpoint, idempotency_key) DO NOTHING" in insert


@pytest.mark.asyncio
async def test_insufficient_balance_is_rejected_without_a_ledger_event():
    """잔액이 모자라면 원장에 아무 것도 남기지 않고 REJECTED로 확정한다."""
    session = RecordingSession(results=[None, "op-1", None, 5])
    outcome = await svc.begin_operation(
        session,
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key=str(uuid.uuid4()),
        request_hash="h" * 64,
    )

    assert outcome.kind == svc.KIND_REPLAY
    assert outcome.status == svc.STATUS_REJECTED
    assert outcome.credit_delta == 0, "거절은 최종 0C다"
    assert outcome.remaining_credits == 5
    assert outcome.error_code == svc.CODE_INSUFFICIENT_CREDITS
    assert "크레딧이 부족합니다" in outcome.error_message
    assert session.sql_matching("INSERT INTO credit_ledger") == []


@pytest.mark.asyncio
async def test_new_profile_gets_welcome_exactly_once_via_upsert():
    # 프로필 upsert(신규) → 웰컴 원장 → operation 삽입 → 잔액 차감
    session = RecordingSession(results=[str(uuid.uuid4()), None, "op-1", 40])
    await svc.begin_operation(
        session,
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key=str(uuid.uuid4()),
        request_hash="h" * 64,
    )

    profile_insert = _squash(session.sql_matching("INSERT INTO profiles")[0])
    assert "ON CONFLICT (id) DO NOTHING" in profile_insert

    ledger = [_squash(s) for s in session.sql_matching("INSERT INTO credit_ledger")]
    welcome = [s for s in ledger if "ON CONFLICT DO NOTHING" in s]
    assert len(ledger) == 2, "웰컴 지급 + 예약 차감"
    assert len(welcome) == 2, "두 원장 삽입 모두 중복을 DB에서 흡수해야 한다"


@pytest.mark.asyncio
async def test_existing_profile_never_receives_a_second_welcome():
    """이미 있던 프로필에는 웰컴을 다시 얹지 않는다."""
    session = RecordingSession(results=[None, "op-1", 40])
    await svc.begin_operation(
        session,
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key=str(uuid.uuid4()),
        request_hash="h" * 64,
    )
    assert session.sql_matching("INSERT INTO profiles"), "upsert 자체는 시도한다"
    ledger = session.sql_matching("INSERT INTO credit_ledger")
    assert len(ledger) == 1, "예약 차감 하나뿐이어야 한다"


@pytest.mark.asyncio
async def test_finalize_success_requires_state_and_fencing_token():
    session = RecordingSession(results=[(10, -10, 40)])
    outcome = await svc.finalize_success(
        session,
        operation_id=str(uuid.uuid4()),
        fencing_token=str(uuid.uuid4()),
        response_snapshot={"user_facing_message": "정상 응답"},
    )

    assert outcome.status == svc.STATUS_SUCCEEDED
    assert outcome.credit_delta == -10, "SUCCEEDED만 최종 -10C다"
    assert outcome.remaining_credits == 40
    assert session.commits == 1

    stmt = _squash(session.sql_matching("UPDATE credit_operations")[0])
    assert "credit_operations.status =" in stmt, "현재 상태를 조건으로 걸어야 한다"
    assert "credit_operations.fencing_token =" in stmt, "fencing token 조건이 있어야 한다"


@pytest.mark.asyncio
async def test_late_finalize_yields_to_the_recorded_terminal_state():
    """복구가 먼저 종결을 썼다면 늦게 돌아온 실행은 그것을 덮어쓰지 못한다."""
    recovered = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_RELEASED,
        amount=10,
        credit_delta=0,
        fencing_token=str(uuid.uuid4()),
        balance_snapshot=50,
        error_code=svc.CODE_OPERATION_RECOVERED,
    )
    # 조건부 UPDATE가 0행 → 현재 행을 다시 읽어 그 결과를 돌려준다.
    session = RecordingSession(results=[None, recovered])

    outcome = await svc.finalize_success(
        session,
        operation_id=str(recovered.id),
        fencing_token="stale-token",
        response_snapshot={"user_facing_message": "늦게 도착한 응답"},
    )

    assert outcome.status == svc.STATUS_RELEASED
    assert outcome.credit_delta == 0, "복구된 작업은 최종 0C로 남는다"
    assert outcome.remaining_credits == 50
    assert session.rollbacks == 1
    assert session.commits == 0, "진 쪽은 아무 것도 확정하지 않는다"


@pytest.mark.asyncio
async def test_release_refund_is_guarded_by_the_ledger_unique_index():
    """환불은 RELEASE 원장 행이 실제로 들어간 경우에만 잔액에 반영된다."""
    operation = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
    )
    # 잠금 SELECT → RELEASE 삽입(성공) → 잔액 +10 → 상태 UPDATE → 재조회
    released_row = CreditOperation(
        id=operation.id,
        user_id=operation.user_id,
        endpoint=operation.endpoint,
        idempotency_key=operation.idempotency_key,
        request_hash=operation.request_hash,
        status=svc.STATUS_RELEASED,
        amount=10,
        credit_delta=0,
        fencing_token=operation.fencing_token,
        balance_snapshot=50,
    )
    session = RecordingSession(
        results=[operation, "ledger-1", 50, None, released_row]
    )

    outcome = await svc.finalize_release(
        session,
        operation_id=str(operation.id),
        fencing_token=str(operation.fencing_token),
        error_code=svc.CODE_PIPELINE_FAILED,
        error_message="일시적인 서비스 오류가 발생했습니다.",
    )

    assert outcome.status == svc.STATUS_RELEASED
    assert outcome.credit_delta == 0, "답변을 제공하지 못했으면 최종 0C다"
    assert outcome.remaining_credits == 50

    release_insert = _squash(session.sql_matching("INSERT INTO credit_ledger")[0])
    assert "ON CONFLICT DO NOTHING" in release_insert
    assert "RETURNING" in release_insert, "삽입 성사 여부를 보고 환불해야 한다"

    lock = _squash(session.sql_matching("FOR UPDATE")[0])
    assert "credit_operations.status =" in lock
    assert "credit_operations.fencing_token =" in lock


@pytest.mark.asyncio
async def test_release_skips_refund_when_the_event_already_exists():
    """RELEASE 행이 이미 있으면 잔액을 다시 올리지 않는다 (이중 환불 방지)."""
    operation = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
    )
    released_row = CreditOperation(
        id=operation.id,
        user_id=operation.user_id,
        endpoint=operation.endpoint,
        idempotency_key=operation.idempotency_key,
        request_hash=operation.request_hash,
        status=svc.STATUS_RELEASED,
        amount=10,
        credit_delta=0,
        fencing_token=operation.fencing_token,
        balance_snapshot=50,
    )
    # 잠금 SELECT → RELEASE 삽입이 충돌로 0행(None) → 잔액 조회 → 상태 UPDATE → 재조회
    session = RecordingSession(results=[operation, None, 50, None, released_row])

    await svc.finalize_release(
        session,
        operation_id=str(operation.id),
        fencing_token=str(operation.fencing_token),
        error_code=svc.CODE_OPERATION_RECOVERED,
    )

    assert session.sql_matching("UPDATE profiles") == [], "환불이 두 번 일어나면 안 된다"


@pytest.mark.asyncio
async def test_fresh_lease_reports_in_progress_without_touching_credits():
    """처리 중인 같은 요청은 새 차감 없이 202로 돌아간다."""
    live = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    # 프로필 upsert 0행 → operation 삽입 충돌(None) → 기존 행 조회
    session = RecordingSession(results=[None, None, live])

    outcome = await svc.begin_operation(
        session,
        user_id=str(live.user_id),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
    )

    assert outcome.kind == svc.KIND_IN_PROGRESS
    assert outcome.retry_after_seconds == svc.OPERATION_RETRY_AFTER_SECONDS
    assert session.sql_matching("UPDATE profiles") == [], "새 차감이 없어야 한다"


@pytest.mark.asyncio
async def test_same_key_with_a_different_body_conflicts():
    stored = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="a" * 64,
        status=svc.STATUS_SUCCEEDED,
        amount=10,
        credit_delta=-10,
        fencing_token=str(uuid.uuid4()),
    )
    session = RecordingSession(results=[None, None, stored])

    outcome = await svc.begin_operation(
        session,
        user_id=str(stored.user_id),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="b" * 64,
    )

    assert outcome.kind == svc.KIND_CONFLICT
    assert outcome.error_code == svc.CODE_IDEMPOTENCY_KEY_REUSED
    assert session.sql_matching("UPDATE profiles") == []


@pytest.mark.asyncio
async def test_completed_operation_replays_without_rerunning():
    stored = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_SUCCEEDED,
        amount=10,
        credit_delta=-10,
        balance_snapshot=40,
        fencing_token=str(uuid.uuid4()),
        response_snapshot={"user_facing_message": "저장된 응답"},
    )
    session = RecordingSession(results=[None, None, stored])

    outcome = await svc.begin_operation(
        session,
        user_id=str(stored.user_id),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
    )

    assert outcome.kind == svc.KIND_REPLAY
    assert outcome.status == svc.STATUS_SUCCEEDED
    assert outcome.response_snapshot == {"user_facing_message": "저장된 응답"}
    assert outcome.remaining_credits == 40
    assert session.sql_matching("UPDATE profiles") == [], "재시도는 새 차감을 만들지 않는다"


@pytest.mark.asyncio
async def test_recovery_leaves_a_terminal_state_for_an_expired_lease():
    expired = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
        lease_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    recovered = CreditOperation(
        id=expired.id,
        user_id=expired.user_id,
        endpoint=expired.endpoint,
        idempotency_key=expired.idempotency_key,
        request_hash=expired.request_hash,
        status=svc.STATUS_RELEASED,
        amount=10,
        credit_delta=0,
        fencing_token=expired.fencing_token,
        balance_snapshot=50,
        error_code=svc.CODE_OPERATION_RECOVERED,
    )
    # 프로필 upsert → operation 삽입 충돌 → 기존 행 → RELEASE 삽입 → 잔액 → UPDATE → 재조회
    session = RecordingSession(
        results=[None, None, expired, "ledger-1", 50, None, recovered]
    )

    outcome = await svc.begin_operation(
        session,
        user_id=str(expired.user_id),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
    )

    assert outcome.kind == svc.KIND_REPLAY
    assert outcome.status == svc.STATUS_RELEASED
    assert outcome.credit_delta == 0
    assert outcome.error_code == svc.CODE_OPERATION_RECOVERED


@pytest.mark.asyncio
async def test_recover_if_stale_leaves_a_live_lease_alone():
    live = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    session = RecordingSession()
    result = await svc.recover_operation_if_stale(session, operation=live)

    assert result is live
    assert session.statements == [], "아직 살아 있는 실행을 건드리지 않는다"


@pytest.mark.asyncio
async def test_recover_if_stale_is_a_noop_for_terminal_operations():
    done = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_SUCCEEDED,
        amount=10,
        credit_delta=-10,
        fencing_token=str(uuid.uuid4()),
    )
    session = RecordingSession()
    assert await svc.recover_operation_if_stale(session, operation=done) is done
    assert session.statements == []


# --- 3. 모델과 마이그레이션이 선언한 DB 제약 -------------------------------------


def test_operation_table_scopes_idempotency_key_per_user_and_endpoint():
    constraint = next(
        c
        for c in CreditOperation.__table__.constraints
        if c.name == "uq_credit_operations_user_endpoint_key"
    )
    assert {c.name for c in constraint.columns} == {
        "user_id",
        "endpoint",
        "idempotency_key",
    }


def test_operation_status_is_constrained_to_the_four_contract_states():
    check = next(
        c
        for c in CreditOperation.__table__.constraints
        if c.name == "ck_credit_operations_status"
    )
    text = str(check.sqltext)
    for status in ("PROCESSING", "SUCCEEDED", "RELEASED", "REJECTED"):
        assert status in text


def test_ledger_blocks_duplicate_operation_events():
    index = next(
        i
        for i in CreditLedger.__table__.indexes
        if i.name == "uq_credit_ledger_operation_event"
    )
    assert index.unique is True
    assert [c.name for c in index.columns] == ["operation_id", "event_type"]
    assert "operation_id IS NOT NULL" in str(
        index.dialect_options["postgresql"]["where"]
    )


def test_ledger_blocks_a_second_welcome_per_user():
    index = next(
        i
        for i in CreditLedger.__table__.indexes
        if i.name == "uq_credit_ledger_welcome_per_user"
    )
    assert index.unique is True
    assert [c.name for c in index.columns] == ["user_id"]
    assert "WELCOME" in str(index.dialect_options["postgresql"]["where"])


def test_profiles_forbid_a_negative_balance():
    check = next(
        c
        for c in UserProfile.__table__.constraints
        if c.name == "ck_profiles_credit_balance_non_negative"
    )
    assert "credit_balance >= 0" in str(check.sqltext)


# --- 4. 마이그레이션 정적 검증 ---------------------------------------------------

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "c3a91f4d6b27_credit_operations_and_ledger_integrity.py"
)


def test_migration_chains_to_the_current_head():
    source = _MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "c3a91f4d6b27"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = "d7f4a1c2e8b9"' in source


def test_migration_declares_every_contract_constraint():
    source = _MIGRATION.read_text(encoding="utf-8")
    for fragment in (
        "ck_profiles_credit_balance_non_negative",
        "uq_credit_operations_user_endpoint_key",
        "ck_credit_operations_status",
        "uq_credit_ledger_operation_event",
        "uq_credit_ledger_welcome_per_user",
    ):
        assert fragment in source, f"{fragment}이(가) 마이그레이션에 없다"


def test_downgrade_never_drops_balances_or_the_ledger():
    """되돌리기가 잔액과 장부를 지우면 안 된다.

    `profiles`와 `credit_ledger`는 이 마이그레이션이 소유한 표가 아니다.
    downgrade가 이 둘을 DROP하면 사용자의 잔액과 입출금 기록이 통째로 사라진다.
    """
    source = _MIGRATION.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade()") :]

    assert "DROP TABLE IF EXISTS credit_operations" in downgrade
    for forbidden in (
        "DROP TABLE IF EXISTS profiles",
        "DROP TABLE profiles",
        "DROP TABLE IF EXISTS credit_ledger",
        "DROP TABLE credit_ledger",
        "DELETE FROM credit_ledger",
        "DELETE FROM profiles",
    ):
        assert forbidden not in downgrade, f"downgrade가 데이터를 지운다: {forbidden}"
