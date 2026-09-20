# -*- coding: utf-8 -*-
"""주역 상담 앱 - 크레딧 operation(예약·멱등·복구) 서비스.

`credit-operation-v1` 계약의 서버측 구현이다. 이 모듈이 지키는 것은 셋이다.

1. **예약과 실행의 분리.** 크레딧 예약은 짧은 트랜잭션에서 커밋하고 닫는다.
   LLM·RAG 파이프라인이 도는 동안 크레딧 행 lock이나 크레딧 트랜잭션을
   붙들고 있지 않는다. 상담이 20초 걸린다고 해서 다른 요청의 잔액 갱신이
   20초 밀리면 안 된다.

2. **멱등.** (사용자, endpoint, Idempotency-Key)가 작업 하나를 가리킨다.
   같은 body의 재요청은 새 차감도 새 파이프라인 실행도 만들지 않고 저장된
   결과를 재생한다. 같은 키를 다른 body에 쓰면 409로 끊는다.

3. **하나의 종결.** 모든 상태 전이는 현재 상태와 fencing token을 함께 조건으로
   건 원자적 UPDATE다. lease가 만료되어 복구가 먼저 종결을 쓰면, 뒤늦게 돌아온
   원래 실행의 UPDATE는 0행을 맞고 물러난다. 반대도 같다. 원장의 partial
   UNIQUE 인덱스가 그 위에서 debit/release 이벤트를 각각 1건으로 고정한다.
"""

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.models.counsel import CreditLedger, CreditOperation, UserProfile
from services.credit_service import (
    CONSULTATION_CREDIT_COST,
    EVENT_DEBIT,
    EVENT_RELEASE,
    EVENT_WELCOME,
    WELCOME_CREDITS,
    ensure_user_profile,
    has_welcome_grant,
    read_balance,
)

logger = logging.getLogger(__name__)


# --- 계약 상수 ---------------------------------------------------------------

STATUS_PROCESSING = "PROCESSING"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_RELEASED = "RELEASED"
STATUS_REJECTED = "REJECTED"

TERMINAL_STATUSES = frozenset({STATUS_SUCCEEDED, STATUS_RELEASED, STATUS_REJECTED})

ENDPOINT_START = "counsel.start"
ENDPOINT_TURN = "counsel.turn"

# 예약이 이 시간 안에 종결되지 않으면 복구 대상이다. 상담 파이프라인 한 턴이
# 최악의 경우에도 끝나 있어야 하는 시간보다 넉넉히 잡는다. 너무 짧으면 정상
# 실행을 복구가 가로채고, 너무 길면 죽은 예약이 오래 잔액을 묶는다.
# 현재 LLM 클라이언트의 단일 호출 최대 타임아웃은 600초다. 정상 요청을 stale로
# 오인하지 않도록 그보다 5분 긴 lease를 둔다. 운영 중 heartbeat를 도입하기 전까지
# 이 값은 LLM 최대 타임아웃보다 반드시 커야 한다.
OPERATION_LEASE_SECONDS = 900

# 202를 받은 클라이언트가 다시 물어보기까지 기다릴 시간.
OPERATION_RETRY_AFTER_SECONDS = 2

# 오류 코드 (HTTP 본문의 `code`로 그대로 나간다)
CODE_IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
CODE_IDEMPOTENCY_KEY_INVALID = "IDEMPOTENCY_KEY_INVALID"
CODE_IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
CODE_OPERATION_IN_PROGRESS = "OPERATION_IN_PROGRESS"
CODE_INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
CODE_OPERATION_RECOVERED = "OPERATION_RECOVERED"
CODE_PIPELINE_FAILED = "PIPELINE_FAILED"

# 결과 종류
KIND_RESERVED = "RESERVED"
KIND_REPLAY = "REPLAY"
KIND_IN_PROGRESS = "IN_PROGRESS"
KIND_CONFLICT = "CONFLICT"

_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{7,254}$")

_INSUFFICIENT_MESSAGE_TEMPLATE = (
    "크레딧이 부족합니다. (1회 {cost}C 필요, 현재 잔액: {balance}C. 무료 크레딧은 마지막 충전 시점 기준 12시간 후 자동으로 다시 충전됩니다.)"
)


class IdempotencyKeyError(ValueError):
    """Idempotency-Key 헤더 자체가 계약을 위반했을 때."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class OperationOutcome:
    """`begin_operation`의 판정 결과.

    라우터는 이 값만 보고 다음 행동을 정한다. 파이프라인을 돌릴지, 저장된
    결과를 재생할지, 202/409로 끊을지.
    """

    kind: str
    operation_id: str
    status: str
    amount: int = CONSULTATION_CREDIT_COST
    fencing_token: Optional[str] = None
    credit_delta: int = 0
    remaining_credits: Optional[int] = None
    response_snapshot: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_after_seconds: Optional[int] = None


# --- 작은 도구들 -------------------------------------------------------------


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """DB 드라이버가 naive datetime을 돌려주더라도 UTC로 비교할 수 있게 만든다."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def validate_idempotency_key(raw: Optional[str]) -> str:
    """헤더 값을 검증해 정규화된 키를 돌려준다.

    여기서 걸리면 operation도 원장도 만들어지기 전에 요청이 끝난다.
    """
    key = (raw or "").strip()
    if not key:
        raise IdempotencyKeyError(
            CODE_IDEMPOTENCY_KEY_REQUIRED,
            "Idempotency-Key 헤더가 필요합니다.",
        )
    if not _IDEMPOTENCY_KEY_PATTERN.match(key):
        raise IdempotencyKeyError(
            CODE_IDEMPOTENCY_KEY_INVALID,
            "Idempotency-Key 형식이 올바르지 않습니다. (영숫자와 -_.: 8~255자)",
        )
    return key


def compute_request_hash(endpoint: str, payload: dict) -> str:
    """같은 키가 다른 body에 재사용됐는지 판정할 지문.

    원문을 저장하지 않는다. 상담 발화는 민감한 개인 서사이고, 재사용 판정에는
    지문이면 충분하다.
    """
    canonical = json.dumps(
        {"endpoint": endpoint, "payload": payload},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def json_safe(value: Any) -> Any:
    """JSONB에 넣기 전에 직렬화 가능한 형태로 고정한다.

    저장 단계에서 터지면 이미 예약된 크레딧이 붕 뜬다. 스냅샷 저장이 상담
    자체를 실패시키지 않도록 여기서 흡수한다.
    """
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


# --- 프로필과 웰컴 크레딧 ------------------------------------------------------

# 프로필 upsert와 웰컴 지급의 본체는 credit_service에 있다. 여기서는 operation
# 경로가 쓰는 이름으로만 열어 둔다.
ensure_profile_with_welcome = ensure_user_profile
current_balance = read_balance


async def read_credit_state(db_session, user_id: str) -> dict:
    """`GET /api/me/credits`가 돌려줄 서버 기준 잔액.

    프런트가 Supabase `profiles`를 직접 읽거나 실패 시 50C로 추정하지 않도록,
    서버가 검증된 JWT sub 기준으로 확정한 값 하나만 알려준다.
    """
    await ensure_user_profile(db_session, user_id)

    return {
        "remaining_credits": await read_balance(db_session, user_id),
        "welcome_granted": await has_welcome_grant(db_session, user_id),
    }


# --- 예약 ---------------------------------------------------------------------


def _replay_outcome(op: CreditOperation) -> OperationOutcome:
    """종결된 작업을 저장된 결과 그대로 재생한다."""
    return OperationOutcome(
        kind=KIND_REPLAY,
        operation_id=str(op.id),
        status=op.status,
        amount=op.amount,
        credit_delta=op.credit_delta if op.credit_delta is not None else 0,
        remaining_credits=op.balance_snapshot,
        response_snapshot=op.response_snapshot,
        error_code=op.error_code,
        error_message=op.error_message,
    )


async def begin_operation(
    db_session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: str,
    request_hash: str,
    amount: int = CONSULTATION_CREDIT_COST,
) -> OperationOutcome:
    """작업을 열거나, 이미 있는 작업의 현재 판정을 돌려준다.

    호출자는 이 함수가 커밋한 뒤 세션을 닫아야 한다. 반환이 `RESERVED`일 때만
    파이프라인을 돌린다. 그 외에는 크레딧이 움직이지 않았거나 이미 확정됐다.
    """
    now = utcnow()
    operation_id = str(uuid.uuid4())
    fencing_token = str(uuid.uuid4())

    await ensure_profile_with_welcome(db_session, user_id)

    inserted = (
        await db_session.execute(
            pg_insert(CreditOperation)
            .values(
                id=operation_id,
                user_id=user_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                status=STATUS_PROCESSING,
                amount=amount,
                credit_delta=None,
                fencing_token=fencing_token,
                lease_expires_at=now + timedelta(seconds=OPERATION_LEASE_SECONDS),
            )
            .on_conflict_do_nothing(
                index_elements=[
                    CreditOperation.user_id,
                    CreditOperation.endpoint,
                    CreditOperation.idempotency_key,
                ]
            )
            .returning(CreditOperation.id)
        )
    ).scalar_one_or_none()

    if inserted is None:
        outcome = await _resolve_existing_operation(
            db_session,
            user_id=user_id,
            endpoint=endpoint,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            now=now,
        )
        await db_session.commit()
        return outcome

    # 이 요청이 작업의 주인이다. 같은 트랜잭션에서 예약까지 확정하고 닫는다.
    new_balance = (
        await db_session.execute(
            update(UserProfile)
            .where(UserProfile.id == user_id, UserProfile.credit_balance >= amount)
            .values(credit_balance=UserProfile.credit_balance - amount)
            .returning(UserProfile.credit_balance)
        )
    ).scalar_one_or_none()

    if new_balance is None:
        balance = await current_balance(db_session, user_id) or 0
        message = _INSUFFICIENT_MESSAGE_TEMPLATE.format(cost=amount, balance=balance)
        await db_session.execute(
            update(CreditOperation)
            .where(CreditOperation.id == operation_id)
            .values(
                status=STATUS_REJECTED,
                credit_delta=0,
                error_code=CODE_INSUFFICIENT_CREDITS,
                error_message=message,
                balance_snapshot=balance,
                lease_expires_at=None,
            )
        )
        await db_session.commit()
        return OperationOutcome(
            kind=KIND_REPLAY,
            operation_id=operation_id,
            status=STATUS_REJECTED,
            amount=amount,
            credit_delta=0,
            remaining_credits=balance,
            error_code=CODE_INSUFFICIENT_CREDITS,
            error_message=message,
        )

    await db_session.execute(
        pg_insert(CreditLedger)
        .values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=-amount,
            reason="상담 크레딧 예약 차감",
            operation_id=operation_id,
            event_type=EVENT_DEBIT,
        )
        .on_conflict_do_nothing()
    )
    await db_session.commit()

    return OperationOutcome(
        kind=KIND_RESERVED,
        operation_id=operation_id,
        status=STATUS_PROCESSING,
        amount=amount,
        fencing_token=fencing_token,
        credit_delta=-amount,
        remaining_credits=new_balance,
    )


async def _resolve_existing_operation(
    db_session,
    *,
    user_id: str,
    endpoint: str,
    idempotency_key: str,
    request_hash: str,
    now: datetime,
) -> OperationOutcome:
    """이미 있던 작업에 대한 판정. 행을 잠근 채로 결정한다."""
    existing = (
        await db_session.execute(
            select(CreditOperation)
            .where(
                CreditOperation.user_id == user_id,
                CreditOperation.endpoint == endpoint,
                CreditOperation.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if existing is None:
        # INSERT는 충돌했는데 행이 보이지 않는다. 경쟁 트랜잭션이 아직
        # 커밋 전이라는 뜻이므로 잠시 뒤 다시 물어보게 한다.
        return OperationOutcome(
            kind=KIND_IN_PROGRESS,
            operation_id="",
            status=STATUS_PROCESSING,
            retry_after_seconds=OPERATION_RETRY_AFTER_SECONDS,
        )

    if existing.request_hash != request_hash:
        return OperationOutcome(
            kind=KIND_CONFLICT,
            operation_id=str(existing.id),
            status=existing.status,
            amount=existing.amount,
            error_code=CODE_IDEMPOTENCY_KEY_REUSED,
            error_message="같은 Idempotency-Key가 다른 요청 내용에 사용되었습니다.",
        )

    if existing.status in TERMINAL_STATUSES:
        return _replay_outcome(existing)

    lease_expires_at = _as_aware(existing.lease_expires_at)
    if lease_expires_at is not None and lease_expires_at > now:
        return OperationOutcome(
            kind=KIND_IN_PROGRESS,
            operation_id=str(existing.id),
            status=STATUS_PROCESSING,
            amount=existing.amount,
            retry_after_seconds=OPERATION_RETRY_AFTER_SECONDS,
        )

    # lease 만료. 예약을 풀고 종결시킨다. 뒤늦게 원래 실행이 돌아오면 상태와
    # fencing token 조건에서 0행을 맞고 물러난다.
    recovered = await _release_locked_operation(
        db_session,
        operation=existing,
        error_code=CODE_OPERATION_RECOVERED,
        error_message="처리가 시간 안에 끝나지 않아 예약을 되돌렸습니다.",
    )
    return _replay_outcome(recovered)


# --- 종결 ---------------------------------------------------------------------


async def _release_locked_operation(
    db_session,
    *,
    operation: CreditOperation,
    error_code: Optional[str],
    error_message: Optional[str],
    response_snapshot: Optional[dict] = None,
) -> CreditOperation:
    """이미 잠근 PROCESSING 행의 예약을 풀고 RELEASED로 종결한다.

    환불의 유일성은 원장의 partial UNIQUE 인덱스가 보장한다. RELEASE 행이
    실제로 들어간 경우에만 잔액을 되돌리므로, 어떤 경합에서도 두 번 환불되지
    않는다.
    """
    released_ledger_id = (
        await db_session.execute(
            pg_insert(CreditLedger)
            .values(
                id=str(uuid.uuid4()),
                user_id=operation.user_id,
                amount=operation.amount,
                reason="상담 크레딧 예약 해제",
                operation_id=operation.id,
                event_type=EVENT_RELEASE,
            )
            .on_conflict_do_nothing()
            .returning(CreditLedger.id)
        )
    ).scalar_one_or_none()

    balance: Optional[int] = None
    if released_ledger_id is not None:
        balance = (
            await db_session.execute(
                update(UserProfile)
                .where(UserProfile.id == operation.user_id)
                .values(credit_balance=UserProfile.credit_balance + operation.amount)
                .returning(UserProfile.credit_balance)
            )
        ).scalar_one_or_none()

    if balance is None:
        balance = await current_balance(db_session, operation.user_id)

    await db_session.execute(
        update(CreditOperation)
        .where(CreditOperation.id == operation.id)
        .values(
            status=STATUS_RELEASED,
            credit_delta=0,
            error_code=error_code,
            error_message=error_message,
            response_snapshot=response_snapshot,
            balance_snapshot=balance,
            lease_expires_at=None,
        )
    )
    await db_session.commit()

    return (
        await db_session.execute(
            select(CreditOperation).where(CreditOperation.id == operation.id)
        )
    ).scalar_one()


async def finalize_success(
    db_session,
    *,
    operation_id: str,
    fencing_token: str,
    response_snapshot: dict,
) -> OperationOutcome:
    """정상 답변을 제공했다. 예약을 그대로 확정한다 (최종 -amount).

    이미 다른 쪽이 종결을 썼다면 그 결과를 그대로 돌려준다. 늦게 돌아온
    실행이 복구 결과를 덮어쓰지 못한다.
    """
    snapshot = json_safe(response_snapshot)

    # 상태·fencing token 조건과 확정값 기록을 한 문장에 담는다. 잔액 스냅샷은
    # 같은 문장 안의 상관 서브쿼리로 읽어, 확정과 스냅샷 사이에 다른 요청이
    # 끼어들 틈을 없앤다.
    row = (
        await db_session.execute(
            update(CreditOperation)
            .where(
                CreditOperation.id == operation_id,
                CreditOperation.status == STATUS_PROCESSING,
                CreditOperation.fencing_token == fencing_token,
            )
            .values(
                status=STATUS_SUCCEEDED,
                credit_delta=-CreditOperation.amount,
                response_snapshot=snapshot,
                error_code=None,
                error_message=None,
                balance_snapshot=(
                    select(UserProfile.credit_balance)
                    .where(UserProfile.id == CreditOperation.user_id)
                    .scalar_subquery()
                ),
                lease_expires_at=None,
            )
            .returning(
                CreditOperation.amount,
                CreditOperation.credit_delta,
                CreditOperation.balance_snapshot,
            )
        )
    ).one_or_none()

    if row is None:
        await db_session.rollback()
        return await _outcome_from_current_row(db_session, operation_id)

    await db_session.commit()
    amount, credit_delta, balance = row

    return OperationOutcome(
        kind=KIND_REPLAY,
        operation_id=operation_id,
        status=STATUS_SUCCEEDED,
        amount=amount,
        credit_delta=credit_delta,
        remaining_credits=balance,
        response_snapshot=snapshot,
    )


async def finalize_release(
    db_session,
    *,
    operation_id: str,
    fencing_token: str,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    response_snapshot: Optional[dict] = None,
) -> OperationOutcome:
    """답변을 제공하지 못했거나 위기 응답이다. 예약을 되돌린다 (최종 0).

    위기 응답은 사용자에게 그대로 제공하되 `response_snapshot`에 담아 재생
    가능하게 만든다. 기술 장애는 스냅샷 없이 오류 코드만 남는다.
    """
    snapshot = json_safe(response_snapshot) if response_snapshot is not None else None

    operation = (
        await db_session.execute(
            select(CreditOperation)
            .where(
                CreditOperation.id == operation_id,
                CreditOperation.status == STATUS_PROCESSING,
                CreditOperation.fencing_token == fencing_token,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if operation is None:
        await db_session.rollback()
        return await _outcome_from_current_row(db_session, operation_id)

    released = await _release_locked_operation(
        db_session,
        operation=operation,
        error_code=error_code,
        error_message=error_message,
        response_snapshot=snapshot,
    )
    return _replay_outcome(released)


async def _outcome_from_current_row(db_session, operation_id: str) -> OperationOutcome:
    """경합에서 밀렸을 때 현재 확정된 상태를 읽어 재생 결과로 만든다."""
    op = (
        await db_session.execute(
            select(CreditOperation).where(CreditOperation.id == operation_id)
        )
    ).scalar_one_or_none()
    if op is None:
        return OperationOutcome(
            kind=KIND_REPLAY,
            operation_id=operation_id,
            status=STATUS_RELEASED,
            credit_delta=0,
            error_code=CODE_OPERATION_RECOVERED,
            error_message="작업 상태를 확인할 수 없습니다.",
        )
    logger.info(
        "operation 종결 경합에서 밀림: operation=%s status=%s", operation_id, op.status
    )
    return _replay_outcome(op)


# --- 조회와 복구 ---------------------------------------------------------------


async def load_owned_operation(
    db_session, *, user_id: str, operation_id: str
) -> Optional[CreditOperation]:
    """소유자 본인의 작업만 돌려준다.

    남의 작업은 `None`이다. 라우터는 '없음'과 '남의 것'을 구분하지 않고 404를
    돌려준다. 존재 여부 자체가 새어 나가면 안 된다.
    """
    return (
        await db_session.execute(
            select(CreditOperation).where(
                CreditOperation.id == operation_id,
                CreditOperation.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def recover_operation_if_stale(
    db_session, *, operation: CreditOperation
) -> CreditOperation:
    """lease가 만료된 PROCESSING이면 예약을 풀고 종결한다.

    상태 조회 경로에서 그대로 호출할 수 있다. 만료되지 않았거나 이미 종결된
    작업에는 아무 일도 하지 않는다.
    """
    if operation.status != STATUS_PROCESSING:
        return operation

    lease_expires_at = _as_aware(operation.lease_expires_at)
    if lease_expires_at is not None and lease_expires_at > utcnow():
        return operation

    locked = (
        await db_session.execute(
            select(CreditOperation)
            .where(
                CreditOperation.id == operation.id,
                CreditOperation.status == STATUS_PROCESSING,
                CreditOperation.fencing_token == operation.fencing_token,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if locked is None:
        await db_session.rollback()
        return (
            await db_session.execute(
                select(CreditOperation).where(CreditOperation.id == operation.id)
            )
        ).scalar_one()

    return await _release_locked_operation(
        db_session,
        operation=locked,
        error_code=CODE_OPERATION_RECOVERED,
        error_message="처리가 시간 안에 끝나지 않아 예약을 되돌렸습니다.",
    )


async def recover_expired_operations(db_session, *, limit: int = 50) -> list[str]:
    """만료된 예약을 모아 복구한다.

    백그라운드 스케줄러는 이번 범위가 아니다. 운영자가 안전하게 호출할 수 있는
    형태로만 열어 둔다. 여러 번 호출해도 결과는 같다.
    """
    stale = (
        (
            await db_session.execute(
                select(CreditOperation)
                .where(
                    CreditOperation.status == STATUS_PROCESSING,
                    CreditOperation.lease_expires_at.is_not(None),
                    CreditOperation.lease_expires_at <= utcnow(),
                )
                .order_by(CreditOperation.lease_expires_at)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    recovered: list[str] = []
    for operation in stale:
        result = await recover_operation_if_stale(db_session, operation=operation)
        if result.status == STATUS_RELEASED:
            recovered.append(str(operation.id))
    return recovered
