# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 크레딧 관리 및 트랜잭션 서비스 (CreditService)
- 프로필 생성, 웰컴 크레딧 지급, 원자적 크레딧 차감 및 환불 트랜잭션을 전담합니다.
- Race Condition(동시성 문제)을 방지하기 위해 DB 레벨 원자적 갱신을 보장합니다.
"""

import logging
from typing import Optional
from sqlalchemy import select, update
from core.models.counsel import CounselSession, CreditLedger, UserProfile

logger = logging.getLogger(__name__)

CONSULTATION_CREDIT_COST = 10
WELCOME_CREDITS = 50


def is_chargeable(result) -> bool:
    """크레딧 차감 대상 턴인지 판별합니다 (위기 감지 시에는 미차감/환불 원칙)."""
    return getattr(result, "safety_category", "") != "BLOCK_CRISIS"


async def ensure_user_profile(db_session, user_id: str) -> None:
    """프로필이 없으면 웰컴 크레딧과 함께 생성합니다."""
    exists = (
        await db_session.execute(select(UserProfile.id).where(UserProfile.id == user_id))
    ).scalar_one_or_none()
    if exists is not None:
        return

    # 장부가 프로필을 FK로 참조하므로 프로필을 먼저 확정
    db_session.add(UserProfile(id=user_id, credit_balance=WELCOME_CREDITS))
    await db_session.flush()
    db_session.add(
        CreditLedger(user_id=user_id, amount=WELCOME_CREDITS, reason="신규 가입 웰컴 크레딧")
    )
    await db_session.flush()


async def charge_credits(
    db_session, user_id: str, amount: int, reason: str
) -> Optional[int]:
    """
    잔액이 충족되면 원자적으로 차감하고 장부에 기록합니다.
    성공 시 잔여 크레딧, 잔액 부족 시 None을 반환합니다.
    """
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
