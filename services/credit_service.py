# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 크레딧 관리 및 트랜잭션 서비스 (CreditService)
- 프로필 생성, 웰컴 크레딧 지급, 원자적 크레딧 차감 및 환불 트랜잭션을 전담합니다.
- Race Condition(동시성 문제)을 방지하기 위해 DB 레벨 원자적 갱신을 보장합니다.

예약·멱등·복구를 포함하는 operation 단위 처리는 `services.credit_operation_service`에
있다. 이 모듈은 그 아래에서 쓰는 잔액과 장부의 기본 연산만 담는다.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.config import settings
from core.models.counsel import CounselSession, CreditLedger, UserProfile

logger = logging.getLogger(__name__)

# 하위 호환성을 위해 모듈 레벨 상수를 남기되, 실제 값은 settings로부터 읽습니다.
CONSULTATION_CREDIT_COST = settings.CONSULTATION_CREDIT_COST
WELCOME_CREDITS = settings.WELCOME_CREDITS
FREE_BETA_REFILL_CREDITS = settings.FREE_BETA_REFILL_CREDITS
FREE_BETA_REFILL_HOURS = settings.FREE_BETA_REFILL_HOURS

# 원장 이벤트 종류. operation별 중복과 사용자별 웰컴/리필 구분을 위함
EVENT_WELCOME = "WELCOME"
EVENT_DEBIT = "DEBIT"
EVENT_RELEASE = "RELEASE"
EVENT_REFILL = "REFILL_FREE"


def utcnow() -> datetime:
    """UTC 현재 시각을 반환합니다."""
    return datetime.now(timezone.utc)


def is_chargeable(result) -> bool:
    """크레딧 차감 대상 턴인지 판별합니다 (위기 감지 시에는 미차감/환불 원칙)."""
    return getattr(result, "safety_category", "") != "BLOCK_CRISIS"


class RefillStatus(str, Enum):
    REFILLED = "REFILLED"
    SKIPPED = "SKIPPED"
    FAILED_RECOVERED = "FAILED_RECOVERED"


@dataclass
class RefillOutcome:
    status: RefillStatus
    new_balance: Optional[int] = None
    grant: int = 0
    reason: Optional[str] = None
    error: Optional[Exception] = None

    @property
    def refilled_amount(self) -> int:
        return self.grant


    def __int__(self) -> int:
        return self.new_balance or 0

    def __bool__(self) -> bool:
        return self.status == RefillStatus.REFILLED


async def refill_free_credits_if_due(db_session, user_id: str) -> RefillOutcome:
    """
    무료 베타 기간 중 마지막 충전 후 12시간이 경과한 사용자에게 50 크레딧까지 자동 충전합니다.
    - REFILLED: 충전 성공 (new_balance, grant)
    - SKIPPED: 충전 대상 아님 (쿨다운 미도달, 이미 50C 이상 등)
    - FAILED_RECOVERED: 충전 중 DB 예외 발생했으나 savepoint로 세션 복구 완료
    """
    refill_target = getattr(settings, "FREE_BETA_REFILL_TARGET_CREDITS", getattr(settings, "FREE_BETA_REFILL_CREDITS", 50))
    refill_hours = getattr(settings, "FREE_BETA_REFILL_INTERVAL_HOURS", getattr(settings, "FREE_BETA_REFILL_HOURS", 12))

    if refill_target <= 0 or refill_hours <= 0:
        return RefillOutcome(status=RefillStatus.SKIPPED, reason="REFILL_DISABLED")

    now = utcnow()
    threshold = now - timedelta(hours=refill_hours)

    profile_obj = None

    async def _do_refill():
        nonlocal profile_obj
        # 1. 프로필 행 잠금 조회 (SELECT ... FOR UPDATE)
        stmt = select(UserProfile).where(UserProfile.id == user_id).with_for_update()
        res = await db_session.execute(stmt)

        row = None
        if hasattr(res, "scalar_one_or_none") and callable(res.scalar_one_or_none):
            row = res.scalar_one_or_none()
        elif hasattr(res, "first") and callable(res.first):
            row = res.first()

        if row is None:
            return RefillOutcome(status=RefillStatus.SKIPPED, reason="PROFILE_NOT_FOUND")

        # row가 UserProfile 인스턴스인 경우와 튜플/가짜 객체인 경우 모두 지원
        if isinstance(row, UserProfile):
            profile = row
            profile_obj = profile
            current_balance = profile.credit_balance
            last_refilled_at = profile.last_refilled_at
        elif isinstance(row, (tuple, list)):
            profile = None
            current_balance, last_refilled_at = row[0], row[1]
        elif hasattr(row, "credit_balance"):
            profile = row
            profile_obj = profile
            current_balance = row.credit_balance
            last_refilled_at = getattr(row, "last_refilled_at", None)
        else:
            return RefillOutcome(status=RefillStatus.SKIPPED, reason="INVALID_ROW")

        # 12시간 경과 여부 확인
        if last_refilled_at is not None and last_refilled_at > threshold:
            return RefillOutcome(status=RefillStatus.SKIPPED, reason="COOLDOWN_ACTIVE")

        # 이미 목표 잔액(50C) 이상이면 충전하지 않음 (원장도 생성하지 않음)
        if current_balance >= refill_target:
            return RefillOutcome(status=RefillStatus.SKIPPED, reason="BALANCE_SUFFICIENT")

        grant = min(refill_target - current_balance, refill_target)
        if grant <= 0:
            return RefillOutcome(status=RefillStatus.SKIPPED, reason="ZERO_GRANT")

        new_balance = current_balance + grant

        if profile is not None and hasattr(profile, "credit_balance"):
            profile.credit_balance = new_balance
            profile.last_refilled_at = now
            profile.updated_at = now
        else:
            # FakeSession 등 객체 바인딩이 안 된 경우 UPDATE문 실행
            upd_stmt = (
                update(UserProfile)
                .where(UserProfile.id == user_id)
                .values(
                    credit_balance=new_balance,
                    last_refilled_at=now,
                    updated_at=now,
                )
            )
            await db_session.execute(upd_stmt)

        ledger_entry = CreditLedger(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=grant,
            reason=f"{refill_hours}시간 무료 자동 충전",
            event_type=EVENT_REFILL,
        )
        db_session.add(ledger_entry)
        await db_session.flush()

        logger.info(
            "무료 크레딧 12시간 자동 충전 완료: user_id=%s, grant=%d, new_balance=%d",
            user_id,
            grant,
            new_balance,
        )
        return RefillOutcome(status=RefillStatus.REFILLED, new_balance=new_balance, grant=grant)

    # 세션에 begin_nested(savepoint)가 지원되는 경우 savepoint로 감싸서 실패 격리
    if hasattr(db_session, "begin_nested") and callable(db_session.begin_nested):
        try:
            async with db_session.begin_nested():
                return await _do_refill()
        except Exception as exc:
            # 프로필 메모리 dirty state 복원 (CR-6 롤백 보장)
            if profile_obj is not None and hasattr(db_session, "expire") and callable(db_session.expire):
                try:
                    db_session.expire(profile_obj)
                except Exception:
                    pass
            logger.error(
                "무료 크레딧 자동 충전 중 예외 발생 (savepoint 롤백 완료, 기존 잔액으로 진행): user_id=%s, err=%s",
                user_id,
                exc,
            )
            return RefillOutcome(status=RefillStatus.FAILED_RECOVERED, error=exc, reason=str(exc))
    else:
        try:
            return await _do_refill()
        except Exception as exc:
            if profile_obj is not None and hasattr(db_session, "expire") and callable(db_session.expire):
                try:
                    db_session.expire(profile_obj)
                except Exception:
                    pass
            logger.error(
                "무료 크레딧 자동 충전 중 예외 발생 (기존 잔액으로 진행): user_id=%s, err=%s",
                user_id,
                exc,
            )
            return RefillOutcome(status=RefillStatus.FAILED_RECOVERED, error=exc, reason=str(exc))


async def ensure_user_profile(db_session, user_id: str) -> bool:
    """프로필을 upsert하고, 이번 호출이 실제로 만들었을 때만 웰컴을 지급합니다.

    예전에는 SELECT로 존재를 확인한 뒤 INSERT했다. 두 요청이 같은 순간에
    들어오면 둘 다 '없음'을 보고 둘 다 지급하거나, 나중 INSERT가 PK 충돌로
    터졌다. 이제는 PostgreSQL upsert 한 문장이 승자를 정하고, 진 쪽은 0행을
    받아 웰컴 지급 자체를 건너뛴다.

    이미 있던 프로필에는 어떤 경우에도 웰컴을 다시 얹지 않는다.

    Returns:
        이번 호출이 프로필을 새로 만들었으면 True.
    """
    created = (
        await db_session.execute(
            pg_insert(UserProfile)
            .values(id=user_id, credit_balance=WELCOME_CREDITS)
            .on_conflict_do_nothing(index_elements=[UserProfile.id])
            .returning(UserProfile.id)
        )
    ).scalar_one_or_none()

    if created is None:
        return False

    # 잔액과 장부를 같은 트랜잭션에서 함께 확정한다. 사용자당 웰컴 1건은
    # partial UNIQUE 인덱스가 이중으로 막는다.
    await db_session.execute(
        pg_insert(CreditLedger)
        .values(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=WELCOME_CREDITS,
            reason="신규 가입 웰컴 크레딧",
            event_type=EVENT_WELCOME,
        )
        .on_conflict_do_nothing()
    )
    return True


async def has_welcome_grant(db_session, user_id: str) -> bool:
    """웰컴 크레딧이 지급된 것으로 장부에 기록되어 있는지."""
    return (
        await db_session.execute(
            select(CreditLedger.id)
            .where(
                CreditLedger.user_id == user_id,
                CreditLedger.event_type == EVENT_WELCOME,
            )
            .limit(1)
        )
    ).scalar_one_or_none() is not None


async def read_balance(db_session, user_id: str) -> Optional[int]:
    """서버가 아는 현재 잔액. 프로필이 없으면 None."""
    return (
        await db_session.execute(
            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
        )
    ).scalar_one_or_none()


async def charge_credits(
    db_session, user_id: str, amount: int, reason: str
) -> Optional[int]:
    """
    잔액이 충족되면 원자적으로 차감하고 장부에 기록합니다.
    성공 시 잔여 크레딧, 잔액 부족 시 None을 반환합니다.
    차감 전 12시간 자동 충전 조건을 먼저 확인합니다.
    """
    refill_outcome = await refill_free_credits_if_due(db_session, user_id)
    if refill_outcome.status == RefillStatus.FAILED_RECOVERED:
        logger.warning(
            "charge_credits 내 무료 크레딧 충전 실패(세션 복구 완료, 기존 잔액으로 차감 진행): user_id=%s, err=%s",
            user_id,
            refill_outcome.error,
        )

    stmt = (
        update(UserProfile)
        .where(UserProfile.id == user_id, UserProfile.credit_balance >= amount)
        .values(credit_balance=UserProfile.credit_balance - amount)
        .returning(UserProfile.credit_balance)
    )
    res = await db_session.execute(stmt)
    new_balance = res.scalar_one_or_none()

    if new_balance is None:
        return None

    db_session.add(
        CreditLedger(user_id=user_id, amount=-amount, reason=reason)
    )
    await db_session.flush()
    return new_balance


async def refund_credits(
    db_session, user_id: str, amount: int, reason: str
) -> Optional[int]:
    """위기 감지 시 상담에 쓰인 크레딧을 장부에 환불 기록하고 잔액을 되돌립니다."""
    stmt = (
        update(UserProfile)
        .where(UserProfile.id == user_id)
        .values(credit_balance=UserProfile.credit_balance + amount)
        .returning(UserProfile.credit_balance)
    )
    res = await db_session.execute(stmt)
    new_balance = res.scalar_one_or_none()

    if new_balance is None:
        return None

    db_session.add(
        CreditLedger(user_id=user_id, amount=amount, reason=reason)
    )
    await db_session.flush()
    return new_balance


# 하위 호환성 별칭 (기존 코드 및 단위 테스트 100% 호환)
_ensure_profile = ensure_user_profile
_charge = charge_credits
_refund = refund_credits
_is_chargeable = is_chargeable
