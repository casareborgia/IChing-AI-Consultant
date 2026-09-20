# -*- coding: utf-8 -*-
"""운영자 전용 상태 조회 및 관리 라우터 (OPS).

- GET /api/ops/budget: 런타임 AI 비용 예산 누적 상태 조회
- GET /api/ops/dashboard: 종합 KPI, 방문자 통계, 회원 목록, 최근 상담 세션, 크레딧 원장 조회
- POST /api/ops/credits/grant: 운영자 수동 크레딧 지급
- 접근 제어: require_operator (비인가자 404 반환으로 경로 은닉)
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from api.deps import check_rate_limit, require_operator
from core.cost_budget import budget_tracker
from core.db import AsyncSessionLocal
from services.visit_analytics_service import purge_expired_visits, summarize_visits

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ops", tags=["Operations"])


class GrantCreditRequest(BaseModel):
    target_user_id: str = Field(..., description="크레딧을 지급할 대상 사용자 ID (UUID)")
    amount: int = Field(..., gt=0, le=100000, description="지급할 크레딧 수량 (양수)")
    reason: Optional[str] = Field("운영자 수동 지급", description="지급 사유")


@router.get("/budget", dependencies=[Depends(check_rate_limit)], summary="운영자 AI 비용 예산 누적 상태 조회")
async def get_ops_budget_status(
    operator_id: str = Depends(require_operator),
) -> Dict[str, Any]:
    """운영자 전용 일일/월간 AI 호출 비용 누적 및 예산 잔여 상태를 반환합니다."""
    return await budget_tracker.get_status_async()


@router.get("/dashboard", dependencies=[Depends(check_rate_limit)], summary="운영자 종합 대시보드 지표 조회")
async def get_ops_dashboard(
    operator_id: str = Depends(require_operator),
) -> Dict[str, Any]:
    """가입자 현황, 세션/턴/저널 통계, 크레딧 현황 및 최근 활동 로그를 반환합니다."""
    async with AsyncSessionLocal() as session:
        try:
            # 1. KPI 지표 집계
            users_count_res = await session.execute(text("SELECT COUNT(*) FROM public.profiles"))
            total_users = users_count_res.scalar() or 0

            sessions_count_res = await session.execute(text("SELECT COUNT(*) FROM public.counsel_sessions"))
            total_sessions = sessions_count_res.scalar() or 0

            turns_count_res = await session.execute(text("SELECT COUNT(*) FROM public.counsel_turns"))
            total_turns = turns_count_res.scalar() or 0

            journals_count_res = await session.execute(text("SELECT COUNT(*) FROM public.journal_entries"))
            total_journals = journals_count_res.scalar() or 0

            credits_in_circ_res = await session.execute(text("SELECT COALESCE(SUM(credit_balance), 0) FROM public.profiles"))
            total_credits_in_circulation = credits_in_circ_res.scalar() or 0

            credits_consumed_res = await session.execute(
                text("SELECT COALESCE(ABS(SUM(amount)), 0) FROM public.credit_ledger WHERE amount < 0")
            )
            total_credits_consumed = credits_consumed_res.scalar() or 0

            # 2. 회원 목록 (최대 50명)
            users_query = text("""
                SELECT
                    p.id,
                    p.email,
                    p.nickname,
                    p.credit_balance,
                    p.created_at,
                    p.updated_at,
                    (SELECT COUNT(*) FROM public.counsel_sessions cs WHERE cs.user_id = p.id::text) AS session_count
                FROM public.profiles p
                ORDER BY p.created_at DESC
                LIMIT 50
            """)
            users_rows = (await session.execute(users_query)).fetchall()
            users_list: List[Dict[str, Any]] = [
                {
                    "id": str(row.id),
                    "email": row.email,
                    "nickname": row.nickname,
                    "credit_balance": row.credit_balance,
                    "session_count": row.session_count,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in users_rows
            ]

            # 3. 최근 상담 세션 (최대 20건)
            sessions_query = text("""
                SELECT
                    cs.id,
                    cs.user_id,
                    cs.raw_question,
                    cs.topic_category,
                    cs.status,
                    cs.created_at,
                    COUNT(ct.id) AS turn_count,
                    EXISTS(SELECT 1 FROM public.journal_entries je WHERE je.session_id = cs.id) AS has_journal,
                    p.email AS user_email
                FROM public.counsel_sessions cs
                LEFT JOIN public.counsel_turns ct ON ct.session_id = cs.id
                LEFT JOIN public.profiles p ON p.id::text = cs.user_id
                GROUP BY cs.id, cs.user_id, cs.raw_question, cs.topic_category, cs.status, cs.created_at, p.email
                ORDER BY cs.created_at DESC
                LIMIT 20
            """)
            sessions_rows = (await session.execute(sessions_query)).fetchall()
            recent_sessions: List[Dict[str, Any]] = [
                {
                    "id": str(row.id),
                    "user_id": str(row.user_id) if row.user_id else None,
                    "user_email": row.user_email,
                    "raw_question": row.raw_question,
                    "topic_category": row.topic_category,
                    "status": row.status,
                    "turn_count": row.turn_count,
                    "has_journal": bool(row.has_journal),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in sessions_rows
            ]

            # 4. 최근 크레딧 원장 (최대 30건)
            ledger_query = text("""
                SELECT
                    cl.id,
                    cl.user_id,
                    cl.amount,
                    cl.reason,
                    cl.event_type,
                    cl.created_at,
                    p.email AS user_email
                FROM public.credit_ledger cl
                LEFT JOIN public.profiles p ON p.id = cl.user_id
                ORDER BY cl.created_at DESC
                LIMIT 30
            """)
            ledger_rows = (await session.execute(ledger_query)).fetchall()
            recent_ledger: List[Dict[str, Any]] = [
                {
                    "id": str(row.id),
                    "user_id": str(row.user_id),
                    "user_email": row.user_email,
                    "amount": row.amount,
                    "reason": row.reason,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in ledger_rows
            ]

            # 5. AI 비용/예산 상태
            budget_status = await budget_tracker.get_status_async()

            # 6. 방문자·재방문 지표 (자체 1st-party 방문 로그)
            # 보존기간 경과분 파기를 집계보다 먼저 수행한다 (F1).
            # 수집 스위치가 꺼져 있어도 파기는 멈추지 않는다.
            try:
                purged = await purge_expired_visits(session)
                if purged:
                    logger.info("보존기간 경과 방문 로그 %d건 파기", purged)
            except Exception as purge_err:
                logger.warning("방문 로그 파기 실패: %s", purge_err)

            # 수집이 꺼져 있거나 집계가 실패해도 대시보드의 나머지 지표는 그대로
            # 내려간다. 방문 통계 하나 때문에 운영 화면 전체가 죽으면 안 된다.
            try:
                visitors = await summarize_visits(session)
            except Exception as visit_err:
                logger.warning("방문자 지표 집계 실패(나머지 지표는 정상 반환): %s", visit_err)
                visitors = {"enabled": False, "reason": "방문자 지표 집계에 실패했습니다."}

            return {
                "kpi": {
                    "total_users": total_users,
                    "total_sessions": total_sessions,
                    "total_turns": total_turns,
                    "total_journals": total_journals,
                    "total_credits_in_circulation": total_credits_in_circulation,
                    "total_credits_consumed": total_credits_consumed,
                    "budget": budget_status,
                },
                "visitors": visitors,
                "users": users_list,
                "recent_sessions": recent_sessions,
                "recent_ledger": recent_ledger,
            }
        except Exception as e:
            logger.error("대시보드 지표 조회 실패: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="대시보드 데이터를 불러오지 못했습니다.",
            )


@router.post("/credits/grant", dependencies=[Depends(check_rate_limit)], summary="운영자 크레딧 수동 지급")
async def grant_user_credit(
    payload: GrantCreditRequest,
    operator_id: str = Depends(require_operator),
) -> Dict[str, Any]:
    """운영자가 특정 사용자에게 테스트 또는 보너스 크레딧을 안전하게 지급합니다."""
    target_id_str = payload.target_user_id.strip()
    try:
        target_uuid = uuid.UUID(target_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바른 UUID 형식이 아닙니다.",
        )

    async with AsyncSessionLocal() as session:
        try:
            # 1. 프로필 잔액 갱신
            update_query = text("""
                UPDATE public.profiles
                SET credit_balance = credit_balance + :amount, updated_at = NOW()
                WHERE id = :user_id
                RETURNING credit_balance, email
            """)
            update_res = await session.execute(
                update_query,
                {"amount": payload.amount, "user_id": target_uuid},
            )
            row = update_res.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="해당 사용자를 찾을 수 없습니다.",
                )

            new_balance = row.credit_balance
            user_email = row.email

            # 2. 원장(credit_ledger)에 기록
            ledger_id = uuid.uuid4()
            insert_ledger_query = text("""
                INSERT INTO public.credit_ledger (id, user_id, amount, reason, event_type, created_at)
                VALUES (:id, :user_id, :amount, :reason, 'ADMIN_GRANT', NOW())
            """)
            await session.execute(
                insert_ledger_query,
                {
                    "id": ledger_id,
                    "user_id": target_uuid,
                    "amount": payload.amount,
                    "reason": payload.reason or "운영자 수동 지급",
                },
            )

            await session.commit()

            logger.info(
                "운영자 크레딧 지급 완료: operator=%s target=%s amount=%d new_balance=%d",
                operator_id,
                target_id_str,
                payload.amount,
                new_balance,
            )

            return {
                "status": "success",
                "target_user_id": target_id_str,
                "user_email": user_email,
                "granted_amount": payload.amount,
                "new_balance": new_balance,
                "reason": payload.reason,
            }
        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error("운영자 크레딧 지급 실패: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="크레딧 지급 처리 중 오류가 발생했습니다.",
            )


@router.post(
    "/visits/purge",
    dependencies=[Depends(check_rate_limit)],
    summary="보존기간 경과 방문 로그 수동/스케줄 파기 (운영자 전용)",
)
async def purge_visits_endpoint(
    operator_id: str = Depends(require_operator),
) -> Dict[str, int]:
    """보존기간(VISIT_RETENTION_DAYS)이 지난 방문 기록을 파기하고 건수를 반환합니다."""
    async with AsyncSessionLocal() as session:
        purged = await purge_expired_visits(session)
        return {"purged": purged}

