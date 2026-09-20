# -*- coding: utf-8 -*-
"""주역 상담 앱 - 사용자 크레딧 잔액 라우터.

프런트가 잔액의 출처를 하나로 갖게 하려고 연다. Supabase `profiles`를 직접
읽거나, 조회에 실패했을 때 50C로 추정하는 경로를 없애기 위한 것이다. 여기서
돌려주는 값은 검증된 JWT sub 기준의 서버 잔액이다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import check_rate_limit, require_user
from core.db import AsyncSessionLocal
from services.credit_operation_service import read_credit_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["Credits"])


@router.get(
    "/credits",
    dependencies=[Depends(check_rate_limit)],
    summary="인증된 사용자의 서버 기준 크레딧 잔액",
)
async def get_my_credits(user_id: str = Depends(require_user)):
    """`{remaining_credits, welcome_granted}`를 반환합니다.

    첫 조회에서 프로필이 없으면 웰컴 크레딧과 함께 정확히 한 번 생성된다.
    이미 있던 프로필에는 웰컴을 다시 지급하지 않는다.
    """
    async with AsyncSessionLocal() as db_session:
        try:
            state = await read_credit_state(db_session, user_id)
            # 첫 인증 조회는 프로필과 웰컴 원장을 멱등 생성할 수 있다. 세션을
            # 닫을 때 rollback되어 화면에만 50C가 보이는 phantom balance가 되지
            # 않도록 같은 짧은 트랜잭션에서 확정한다.
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            logger.error("크레딧 잔액 조회 실패", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail="잔액을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            )

    return {
        "remaining_credits": state["remaining_credits"],
        "welcome_granted": state["welcome_granted"],
    }
