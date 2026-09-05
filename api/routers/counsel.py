# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 상담 세션 시작 및 대화 턴 진행 라우터 (CounselRouter)
- 최초 질문 intake 및 괘 도출 (/api/counsel/start)
- 소크라테스식 5턴 대화 진행 및 최종 저널 발급 (/api/counsel/turn)
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.pipeline import run_turn
from api.deps import check_rate_limit, require_user
from core.config import settings
from core.crisis_resources import get_crisis_resources_by_context
from core.db import AsyncSessionLocal
from core.models.counsel import CounselSession, UserProfile
from services.credit_service import (
    CONSULTATION_CREDIT_COST,
    charge_credits,
    ensure_user_profile,
    is_chargeable,
    refund_credits,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/counsel", tags=["Counsel"])


class StartConsultationRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="내담자의 최초 질문 발화 (최대 1000자)",
    )


class ConsultationTurnApiRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="상담 세션 UUID",
    )
    user_message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="내담자의 이번 턴 발화 (최대 1000자)",
    )


@router.post("/start", dependencies=[Depends(check_rate_limit)], summary="상담 세션 시작 및 괘 도출")
async def start_consultation_endpoint(
    req: StartConsultationRequest,
    user_id: str = Depends(require_user),
):
    """최초 질문으로 상담 세션을 시작하고 괘 도출 및 1턴 결과를 반환합니다 (JWT 인증 필수, 10 크레딧 차감)."""
    async with AsyncSessionLocal() as db_session:
        try:
            # 1. 크레딧 차감 (원자적 갱신)
            await ensure_user_profile(db_session, user_id)
            balance_after_charge = await charge_credits(
                db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 상담 세션 시작"
            )
            if balance_after_charge is None:
                if user_id == "00000000-0000-0000-0000-000000000000" and settings.ENVIRONMENT != "production":
                    # 로컬 개발 브라우저 테스트 연속성을 위한 기본 계정 자동 보충
                    await refund_credits(db_session, user_id, 100, "로컬 개발 테스트 크레딧 자동 보충")
                    balance_after_charge = await charge_credits(
                        db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 상담 세션 시작"
                    )
                else:
                    current = (
                        await db_session.execute(
                            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
                        )
                    ).scalar_one_or_none()
                    raise HTTPException(
                        status_code=402,
                        detail=(
                            f"크레딧이 부족합니다. (상담 1회: {CONSULTATION_CREDIT_COST} 크레딧 필요, "
                            f"현재 잔액: {current if current is not None else 0}C)"
                        ),
                    )

            # 2. 턴 실행 (테스트 mocking 호환을 위해 api.main.run_turn 동적 참조)
            import api.main as api_main
            runner = getattr(api_main, "run_turn", run_turn)
            result = await runner(
                session=db_session,
                counsel_session_id=None,
                user_id=user_id,
                message=req.question,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

            # 3. 위기 판정 시 안심 환불
            remaining_credits = balance_after_charge
            if not is_chargeable(result):
                refunded = await refund_credits(
                    db_session, user_id, CONSULTATION_CREDIT_COST, "위기 감지 안심 환불"
                )
                await db_session.commit()
                if refunded is not None:
                    remaining_credits = refunded
                logger.info("위기 감지 크레딧 환불: user=%s", user_id)

            return {
                "session_id": result.session_id,
                "turn_number": result.turn_number,
                "user_facing_message": result.user_facing_message,
                "needs_followup": result.needs_followup,
                "is_final": result.is_final,
                "hexagram_id": result.hexagram_id,
                "transformed_hexagram_id": result.transformed_hexagram_id,
                "changing_lines": result.changing_lines,
                "is_crisis": is_crisis,
                "crisis_resources": [r.dict() for r in crisis_resources],
                "is_duplicate": result.is_duplicate,
                "journal_summary": result.journal_summary,
                "journal_data": getattr(result, "journal_data", None) if isinstance(getattr(result, "journal_data", None), dict) else None,
                "focus_rule": result.focus_rule,
                "evidences": result.evidences,
                "remaining_credits": remaining_credits,
                "report_data": result.report_data if isinstance(result.report_data, dict) else None,
            }

        except HTTPException:
            await db_session.rollback()
            raise
        except Exception as e:
            await db_session.rollback()
            logger.error("상담 시작 중 서버 내부 오류: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )


@router.post("/turn", dependencies=[Depends(check_rate_limit)], summary="상담 턴 대화 진행")
async def counsel_turn_endpoint(
    req: ConsultationTurnApiRequest,
    user_id: str = Depends(require_user),
):
    """상담 턴을 실행하고 결과를 반환합니다 (JWT 인증 및 엄격한 세션 소유권 검증)."""
    async with AsyncSessionLocal() as db_session:
        try:
            # 세션 소유권 검증 (BOLA 방지: 토큰의 user_id와 세션 소유자 1:1 대조)
            stmt = select(CounselSession).where(CounselSession.id == req.session_id)
            c_session = (await db_session.execute(stmt)).scalar_one_or_none()
            if not c_session:
                raise HTTPException(status_code=404, detail="존재하지 않는 상담 세션입니다.")

            if not c_session.user_id or c_session.user_id != user_id:
                logger.warning(
                    "세션 접근 권한 불일치 감지: session=%s, owner=%s, req_user=%s",
                    req.session_id,
                    c_session.user_id,
                    user_id,
                )
                raise HTTPException(status_code=403, detail="이 상담 세션에 접근할 권한이 없습니다.")

            # 크레딧 차감 (대화 턴당 10C)
            await ensure_user_profile(db_session, user_id)
            balance_after_charge = await charge_credits(
                db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 대화 턴 진행"
            )
            if balance_after_charge is None:
                if user_id == "00000000-0000-0000-0000-000000000000" and settings.ENVIRONMENT != "production":
                    await refund_credits(db_session, user_id, 100, "로컬 개발 테스트 크레딧 자동 보충")
                    balance_after_charge = await charge_credits(
                        db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 대화 턴 진행"
                    )
                else:
                    current = (
                        await db_session.execute(
                            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
                        )
                    ).scalar_one_or_none()
                    raise HTTPException(
                        status_code=402,
                        detail=(
                            f"크레딧이 부족합니다. (대화 1회: {CONSULTATION_CREDIT_COST} 크레딧 필요, "
                            f"현재 잔액: {current if current is not None else 0}C)"
                        ),
                    )

            # 턴 실행 (테스트 mocking 호환을 위해 api.main.run_turn 동적 참조)
            import api.main as api_main
            runner = getattr(api_main, "run_turn", run_turn)
            result = await runner(
                session=db_session,
                counsel_session_id=req.session_id,
                user_id=user_id,
                message=req.user_message,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

            # 위기 판정 시 안심 환불
            remaining_credits = balance_after_charge
            if not is_chargeable(result):
                refunded = await refund_credits(
                    db_session, user_id, CONSULTATION_CREDIT_COST, "위기 감지 안심 환불"
                )
                await db_session.commit()
                if refunded is not None:
                    remaining_credits = refunded
                logger.info("위기 감지 크레딧 환불: user=%s turn=%s", user_id, result.turn_number)

            return {
                "session_id": result.session_id,
                "turn_number": result.turn_number,
                "user_facing_message": result.user_facing_message,
                "needs_followup": result.needs_followup,
                "is_final": result.is_final,
                "hexagram_id": result.hexagram_id,
                "transformed_hexagram_id": result.transformed_hexagram_id,
                "changing_lines": result.changing_lines,
                "is_crisis": is_crisis,
                "crisis_resources": [r.dict() for r in crisis_resources],
                "is_duplicate": result.is_duplicate,
                "journal_summary": result.journal_summary,
                "journal_data": getattr(result, "journal_data", None) if isinstance(getattr(result, "journal_data", None), dict) else None,
                "focus_rule": result.focus_rule,
                "evidences": result.evidences,
                "remaining_credits": remaining_credits,
            }
        except HTTPException:
            await db_session.rollback()
            raise
        except Exception as e:
            await db_session.rollback()
            logger.error("상담 턴 진행 중 서버 내부 오류: %s", e, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
