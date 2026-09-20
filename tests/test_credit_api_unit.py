"""크레딧 operation HTTP 계약 단위 테스트 (DB 없이 실행).

영속 계층은 대역으로 바꾸고 라우터가 지켜야 하는 HTTP 계약만 본다.
`Idempotency-Key` 요구, 202/409/402 형태, 성공·위기 응답의 필드, 파이프라인
실패 시 예약이 정확히 한 번 풀리는지, 남의 작업이 404로 가려지는지.

잔액과 원장의 최종 불변조건은 폐기 PostgreSQL이 있어야 확인된다. 그쪽은
통합 인수 테스트의 몫이고 여기서 PASS라고 말하지 않는다.
"""

import pathlib
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import check_rate_limit, require_consent, require_user
from api.main import app
from api.routers import counsel as counsel_router
from api.routers import credits as credits_router
from services import credit_operation_service as svc


# --- 대역 --------------------------------------------------------------------


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value


class FakeSession:
    """`async with AsyncSessionLocal() as s:` 자리를 그대로 메우는 세션 대역."""

    def __init__(self, scalar=None):
        self.scalar = scalar
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, *args, **kwargs):
        return _Result(self.scalar)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def close(self):
        pass


def _turn_result(
    *,
    safety_category: str = "NORMAL",
    session_id: str = "sess-abc",
    is_duplicate: bool = False,
):
    return SimpleNamespace(
        session_id=session_id,
        turn_number=1,
        user_facing_message="테스트 괘 해설 메시지입니다.",
        needs_followup=True,
        is_final=False,
        hexagram_id=1,
        transformed_hexagram_id=2,
        changing_lines=[3],
        safety_category=safety_category,
        is_duplicate=is_duplicate,
        journal_summary=None,
        journal_data=None,
        focus_rule="focus",
        evidences=[],
        report_data=None,
        report_status="not_requested",
        report_error_code=None,
    )


@pytest.fixture(autouse=True)
def open_gates():
    """인증·게이트·rate limit은 이 파일의 관심사가 아니다. 열어두고 시작한다."""
    user_id = str(uuid.uuid4())

    async def _user():
        return user_id

    async def _noop():
        return None

    app.dependency_overrides[require_user] = _user
    app.dependency_overrides[require_consent] = _user
    app.dependency_overrides[check_rate_limit] = _noop
    app.dependency_overrides[counsel_router.require_service_gate] = _noop
    app.dependency_overrides[counsel_router.require_generation_enabled] = _noop
    app.dependency_overrides[counsel_router.require_cost_budget] = _noop
    yield user_id
    app.dependency_overrides.clear()


@pytest.fixture
def stub(monkeypatch):
    """라우터가 쓰는 영속 계층 이름을 대역으로 바꾼다."""

    def _apply(*, scalar=None, **overrides):
        counsel_sessions = []
        credit_sessions = []

        def _counsel_factory():
            session = FakeSession(scalar)
            counsel_sessions.append(session)
            return session

        def _credits_factory():
            session = FakeSession(scalar)
            credit_sessions.append(session)
            return session

        monkeypatch.setattr(counsel_router, "AsyncSessionLocal", _counsel_factory)
        monkeypatch.setattr(credits_router, "AsyncSessionLocal", _credits_factory)
        for name, value in overrides.items():
            target = (
                credits_router if name == "read_credit_state" else counsel_router
            )
            monkeypatch.setattr(target, name, value)

        return {"counsel": counsel_sessions, "credits": credit_sessions}

    return _apply


async def _post_start(headers=None, question="취업에 관한 고민이 있습니다."):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/api/counsel/start", headers=headers or {}, json={"question": question}
        )


async def _post_turn(headers=None, session_id="sess-abc", message="이어지는 이야기"):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/api/counsel/turn",
            headers=headers or {},
            json={"session_id": session_id, "user_message": message},
        )


def _key_header():
    return {"Idempotency-Key": str(uuid.uuid4())}


def _reserved(operation_id="op-1"):
    return svc.OperationOutcome(
        kind=svc.KIND_RESERVED,
        operation_id=operation_id,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token="token-1",
        credit_delta=-10,
        remaining_credits=40,
    )


# --- Idempotency-Key 요구 -------------------------------------------------------


@pytest.mark.asyncio
async def test_start_without_idempotency_key_is_refused_before_any_credit_work(stub):
    calls = []

    async def _begin(*args, **kwargs):
        calls.append(kwargs)

    stub(begin_operation=_begin)
    res = await _post_start()

    assert res.status_code == 400
    assert res.json()["code"] == svc.CODE_IDEMPOTENCY_KEY_REQUIRED
    assert calls == [], "키가 없으면 operation도 원장도 만들지 않는다"


@pytest.mark.asyncio
async def test_turn_without_idempotency_key_is_refused(stub):
    stub()
    res = await _post_turn()
    assert res.status_code == 400
    assert res.json()["code"] == svc.CODE_IDEMPOTENCY_KEY_REQUIRED


@pytest.mark.asyncio
async def test_malformed_idempotency_key_is_refused(stub):
    calls = []

    async def _begin(*args, **kwargs):
        calls.append(kwargs)

    stub(begin_operation=_begin)
    res = await _post_start(headers={"Idempotency-Key": "bad key"})

    assert res.status_code == 400
    assert res.json()["code"] == svc.CODE_IDEMPOTENCY_KEY_INVALID
    assert calls == []


# --- 정상 처리 ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_start_keeps_existing_fields_and_adds_operation_fields(
    stub, monkeypatch
):
    async def _begin(*args, **kwargs):
        return _reserved()

    async def _success(session, *, operation_id, fencing_token, response_snapshot):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id=operation_id,
            status=svc.STATUS_SUCCEEDED,
            amount=10,
            credit_delta=-10,
            remaining_credits=40,
            response_snapshot=response_snapshot,
        )

    stub(begin_operation=_begin, finalize_success=_success)

    import api.main as api_main

    async def _runner(**kwargs):
        return _turn_result()

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 200
    # 기존 필드가 그대로 있어야 한다
    for field in (
        "session_id",
        "turn_number",
        "user_facing_message",
        "needs_followup",
        "is_final",
        "hexagram_id",
        "transformed_hexagram_id",
        "changing_lines",
        "is_crisis",
        "crisis_resources",
        "is_duplicate",
        "journal_summary",
        "focus_rule",
        "evidences",
        "report_data",
        "report_status",
        "report_error_code",
    ):
        assert field in body, f"기존 응답 필드 {field}이(가) 사라졌다"

    # 계약이 더하라고 한 네 필드
    assert body["operation_id"] == "op-1"
    assert body["operation_status"] == svc.STATUS_SUCCEEDED
    assert body["credit_delta"] == -10
    assert body["remaining_credits"] == 40
    assert body["is_crisis"] is False


@pytest.mark.asyncio
async def test_answer_is_charged_when_only_optional_report_generation_fails(
    stub, monkeypatch
):
    finalized = {}

    async def _begin(*args, **kwargs):
        return _reserved("op-report-fail")

    async def _success(session, *, operation_id, fencing_token, response_snapshot):
        finalized["snapshot"] = response_snapshot
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id=operation_id,
            status=svc.STATUS_SUCCEEDED,
            amount=10,
            credit_delta=-10,
            remaining_credits=40,
            response_snapshot=response_snapshot,
        )

    async def _release(*args, **kwargs):
        raise AssertionError("사용자 답변이 전달됐으면 보조 보고서 실패로 환불하지 않는다")

    stub(
        begin_operation=_begin,
        finalize_success=_success,
        finalize_release=_release,
    )

    import api.main as api_main

    async def _runner(**kwargs):
        result = _turn_result()
        result.report_status = "failed"
        result.report_error_code = "REPORT_RENDER_FAILED"
        return result

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 200
    assert body["user_facing_message"]
    assert body["report_status"] == "failed"
    assert body["report_error_code"] == "REPORT_RENDER_FAILED"
    assert body["operation_status"] == svc.STATUS_SUCCEEDED
    assert body["credit_delta"] == -10
    assert body["remaining_credits"] == 40
    assert finalized["snapshot"]["report_status"] == "failed"


@pytest.mark.asyncio
async def test_crisis_answer_is_delivered_but_released_at_zero(stub, monkeypatch):
    released = {}

    async def _begin(*args, **kwargs):
        return _reserved("op-crisis")

    async def _release(session, *, operation_id, fencing_token, **kwargs):
        released["count"] = released.get("count", 0) + 1
        released["snapshot"] = kwargs.get("response_snapshot")
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id=operation_id,
            status=svc.STATUS_RELEASED,
            amount=10,
            credit_delta=0,
            remaining_credits=50,
            response_snapshot=kwargs.get("response_snapshot"),
        )

    async def _success(*args, **kwargs):
        raise AssertionError("위기 응답을 성공으로 확정하면 안 된다")

    stub(begin_operation=_begin, finalize_release=_release, finalize_success=_success)

    import api.main as api_main

    async def _runner(**kwargs):
        return _turn_result(safety_category="BLOCK_CRISIS")

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 200, "위기 응답도 사용자에게 그대로 제공한다"
    assert body["is_crisis"] is True
    assert body["user_facing_message"]
    assert body["operation_status"] == svc.STATUS_RELEASED
    assert body["credit_delta"] == 0, "위기 판정은 최종 0C다"
    assert body["remaining_credits"] == 50
    assert released["count"] == 1


@pytest.mark.asyncio
async def test_pipeline_failure_releases_exactly_once_and_hides_internals(
    stub, monkeypatch
):
    calls = []

    async def _begin(*args, **kwargs):
        return _reserved("op-fail")

    async def _release(session, *, operation_id, fencing_token, **kwargs):
        calls.append(kwargs.get("error_code"))
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id=operation_id,
            status=svc.STATUS_RELEASED,
            amount=10,
            credit_delta=0,
            remaining_credits=50,
            error_code=svc.CODE_PIPELINE_FAILED,
            error_message="일시적인 서비스 오류가 발생했습니다.",
        )

    stub(begin_operation=_begin, finalize_release=_release)

    import api.main as api_main

    async def _runner(**kwargs):
        raise RuntimeError("asyncpg: relation \"counsel_sessions\" does not exist")

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 500
    assert calls == [svc.CODE_PIPELINE_FAILED], "release는 정확히 한 번이다"
    assert body["remaining_credits"] == 50, "답변을 못 줬으면 크레딧은 되돌아온다"

    raw = res.text
    for leak in ("asyncpg", "counsel_sessions", "RuntimeError", "Traceback"):
        assert leak not in raw, f"내부 정보가 응답에 새어 나갔다: {leak}"


# --- 재시도와 경합 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_progress_duplicate_returns_202_with_retry_hint(stub, monkeypatch):
    async def _begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_IN_PROGRESS,
            operation_id="op-live",
            status=svc.STATUS_PROCESSING,
            retry_after_seconds=svc.OPERATION_RETRY_AFTER_SECONDS,
        )

    stub(begin_operation=_begin)

    import api.main as api_main

    async def _runner(**kwargs):
        raise AssertionError("처리 중인 요청이 파이프라인을 다시 돌리면 안 된다")

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 202
    assert body["code"] == svc.CODE_OPERATION_IN_PROGRESS
    assert body["operation_id"] == "op-live"
    assert body["retry_after_seconds"] == svc.OPERATION_RETRY_AFTER_SECONDS
    assert res.headers["Retry-After"] == str(svc.OPERATION_RETRY_AFTER_SECONDS)


@pytest.mark.asyncio
async def test_same_key_with_a_different_body_returns_409(stub, monkeypatch):
    async def _begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_CONFLICT,
            operation_id="op-x",
            status=svc.STATUS_SUCCEEDED,
            error_code=svc.CODE_IDEMPOTENCY_KEY_REUSED,
            error_message="같은 Idempotency-Key가 다른 요청 내용에 사용되었습니다.",
        )

    stub(begin_operation=_begin)

    import api.main as api_main

    async def _runner(**kwargs):
        raise AssertionError("409는 파이프라인을 돌리지 않는다")

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    assert res.status_code == 409
    assert res.json()["code"] == svc.CODE_IDEMPOTENCY_KEY_REUSED


@pytest.mark.asyncio
async def test_completed_operation_is_replayed_without_rerunning_the_pipeline(
    stub, monkeypatch
):
    stored = {
        "session_id": "sess-abc",
        "turn_number": 1,
        "user_facing_message": "처음 저장된 응답",
        "is_crisis": False,
    }

    async def _begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id="op-done",
            status=svc.STATUS_SUCCEEDED,
            amount=10,
            credit_delta=-10,
            remaining_credits=40,
            response_snapshot=stored,
        )

    stub(begin_operation=_begin)

    import api.main as api_main

    async def _runner(**kwargs):
        raise AssertionError("재시도가 파이프라인을 다시 돌리면 안 된다")

    monkeypatch.setattr(api_main, "run_turn", _runner)

    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 200
    assert body["user_facing_message"] == "처음 저장된 응답"
    assert body["credit_delta"] == -10, "재생이 새로 차감하지 않는다"
    assert body["remaining_credits"] == 40


@pytest.mark.asyncio
async def test_recovered_operation_replays_as_a_zero_credit_failure(stub):
    async def _begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id="op-recovered",
            status=svc.STATUS_RELEASED,
            amount=10,
            credit_delta=0,
            remaining_credits=50,
            error_code=svc.CODE_OPERATION_RECOVERED,
        )

    stub(begin_operation=_begin)
    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 503
    assert body["code"] == svc.CODE_OPERATION_RECOVERED
    assert body["remaining_credits"] == 50
    assert body["operation_id"] == "op-recovered"


# --- 잔액 부족 --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insufficient_credit_returns_402_in_both_old_and_new_shapes(stub):
    async def _begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id="op-poor",
            status=svc.STATUS_REJECTED,
            amount=10,
            credit_delta=0,
            remaining_credits=5,
            error_code=svc.CODE_INSUFFICIENT_CREDITS,
            error_message="크레딧이 부족합니다. (1회 10 크레딧 필요, 현재 잔액: 5C)",
        )

    stub(begin_operation=_begin)
    res = await _post_start(headers=_key_header())
    body = res.json()

    assert res.status_code == 402
    assert body["code"] == svc.CODE_INSUFFICIENT_CREDITS
    assert body["remaining_credits"] == 5
    # 기존 클라이언트가 읽던 자리도 유지한다
    assert "크레딧이 부족합니다" in body["detail"]


# --- 소유권 -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turn_rejects_a_session_owned_by_someone_else(stub):
    from core.models.counsel import CounselSession

    calls = []

    async def _begin(*args, **kwargs):
        calls.append(kwargs)

    other = CounselSession(
        id="sess-abc", user_id=str(uuid.uuid4()), raw_question="남의 세션"
    )
    stub(scalar=other, begin_operation=_begin)

    res = await _post_turn(headers=_key_header())

    assert res.status_code == 403
    assert calls == [], "소유권 검증은 크레딧이 움직이기 전에 끝난다"


@pytest.mark.asyncio
async def test_turn_returns_404_for_a_missing_session(stub):
    calls = []

    async def _begin(*args, **kwargs):
        calls.append(kwargs)

    stub(scalar=None, begin_operation=_begin)
    res = await _post_turn(headers=_key_header())

    assert res.status_code == 404
    assert calls == []


@pytest.mark.asyncio
async def test_operation_status_hides_other_users_operations(stub):
    async def _load(session, *, user_id, operation_id):
        return None

    stub(load_owned_operation=_load)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/counsel/operations/{uuid.uuid4()}")

    assert res.status_code == 404, "존재 여부가 드러나면 안 된다"


@pytest.mark.asyncio
async def test_operation_status_returns_stored_result_for_the_owner(stub):
    from core.models.counsel import CreditOperation

    op = CreditOperation(
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
        response_snapshot={"user_facing_message": "저장된 결과"},
    )

    async def _load(session, *, user_id, operation_id):
        return op

    stub(load_owned_operation=_load)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/counsel/operations/{op.id}")

    body = res.json()
    assert res.status_code == 200
    assert body["operation_status"] == svc.STATUS_SUCCEEDED
    assert body["credit_delta"] == -10
    assert body["remaining_credits"] == 40
    assert body["result"] == {"user_facing_message": "저장된 결과"}


@pytest.mark.asyncio
async def test_operation_status_reports_processing_while_the_lease_is_live(stub):
    from core.models.counsel import CreditOperation

    op = CreditOperation(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        endpoint=svc.ENDPOINT_START,
        idempotency_key="k" * 12,
        request_hash="h" * 64,
        status=svc.STATUS_PROCESSING,
        amount=10,
        fencing_token=str(uuid.uuid4()),
    )

    async def _load(session, *, user_id, operation_id):
        return op

    async def _recover(session, *, operation):
        return operation

    stub(load_owned_operation=_load, recover_operation_if_stale=_recover)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get(f"/api/counsel/operations/{op.id}")

    body = res.json()
    assert res.status_code == 200
    assert body["operation_status"] == svc.STATUS_PROCESSING
    assert body["result"] is None
    assert body["retry_after_seconds"] == svc.OPERATION_RETRY_AFTER_SECONDS


# --- 잔액 조회 ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_credits_returns_the_server_balance(stub):
    async def _state(session, user_id):
        return {"remaining_credits": 40, "welcome_granted": True}

    sessions = stub(read_credit_state=_state)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/api/me/credits")

    assert res.status_code == 200
    assert res.json() == {"remaining_credits": 40, "welcome_granted": True}
    assert sessions["credits"][0].commits == 1


@pytest.mark.asyncio
async def test_me_credits_failure_never_guesses_fifty(stub):
    """조회에 실패하면 실패라고 말한다. 50C로 위장하지 않는다."""

    async def _state(session, user_id):
        raise RuntimeError("asyncpg connection refused")

    stub(read_credit_state=_state)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/api/me/credits")

    assert res.status_code == 503
    assert "50" not in res.text
    assert "asyncpg" not in res.text


# --- 제거된 개발용 경로 -------------------------------------------------------------


def test_product_path_has_no_developer_credit_top_up():
    """개발용 UUID에 대한 자동 +100C 보충이 제품 경로에 남아 있으면 안 된다."""
    source = pathlib.Path(counsel_router.__file__).read_text(encoding="utf-8")
    assert "100" not in source or "자동 보충" not in source
    assert "로컬 개발 테스트 크레딧 자동 보충" not in source
    assert "00000000-0000-0000-0000-000000000000" not in source
