# -*- coding: utf-8 -*-
"""주역 상담 앱 - 사용자 상담 기록 열람 및 삭제 라우터 (AG-3 / A29).

개인정보 자기결정권 보장을 위한 기록 조회 및 즉시 파기 엔드포인트.
- require_service_gate에 의존하지 않는다 (서비스 정지 시에도 본인 기록 접근/파기 보장).
- 타 사용자의 세션이나 존재하지 않는 세션은 403이 아닌 404로 응답하여 존재 여부를 감춘다.
- user_id IS NULL 익명 세션은 어떤 사용자에게도 노출/삭제되지 않는다.
- 단일 DELETE 문에 user_id 조건을 포함하여 경합을 방지한다.
- 세션 삭제 시 credit_operations.response_snapshot에 보관된 상담 본문도 함께 NULL로 스크러빙한다.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from api.deps import check_rate_limit, require_user
from core.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["Records"])


@router.get(
    "/records",
    dependencies=[Depends(check_rate_limit)],
    summary="사용자의 상담 기록 목록 조회 (본문 미포함, 페이지네이션)",
)
async def list_my_records(
    limit: int = Query(20, ge=1, le=100, description="조회 건수 (기본 20, 최대 100)"),
    cursor: Optional[str] = Query(None, description="이전 페이지 마지막 세션의 created_at ISO 문자열"),
    user_id: str = Depends(require_user),
):
    """인증된 사용자의 상담 세션 목록을 반환합니다. 본문은 포함하지 않습니다."""
    async with AsyncSessionLocal() as db:
        try:
            params: Dict[str, Any] = {"user_id": user_id, "limit": limit + 1}
            cursor_filter = ""
            if cursor:
                cursor_filter = "AND cs.created_at < :cursor"
                params["cursor"] = cursor

            query = text(
                f"""
                SELECT
                    cs.id AS session_id,
                    cs.raw_question,
                    cs.created_at,
                    cs.updated_at,
                    cs.status,
                    cs.report_status,
                    cs.topic_category,
                    cs.report_data,
                    COUNT(ct.id) AS turn_count,
                    EXISTS(SELECT 1 FROM public.journal_entries je WHERE je.session_id = cs.id) AS has_journal,
                    (SELECT ct2.original_hexagram_id FROM public.counsel_turns ct2 WHERE ct2.session_id = cs.id AND ct2.turn_number = 1 LIMIT 1) AS original_hexagram_id,
                    (SELECT ct2.transformed_hexagram_id FROM public.counsel_turns ct2 WHERE ct2.session_id = cs.id AND ct2.turn_number = 1 LIMIT 1) AS transformed_hexagram_id
                FROM public.counsel_sessions cs
                LEFT JOIN public.counsel_turns ct ON ct.session_id = cs.id
                WHERE cs.user_id = :user_id
                  {cursor_filter}
                GROUP BY cs.id, cs.raw_question, cs.created_at, cs.updated_at, cs.status, cs.report_status, cs.topic_category, cs.report_data
                ORDER BY cs.created_at DESC, cs.id DESC
                LIMIT :limit
                """
            )
            res = await db.execute(query, params)
            rows = res.mappings().all()

            records = []
            has_next = len(rows) > limit
            items = rows[:limit] if has_next else rows

            for r in items:
                records.append({
                    "session_id": str(r["session_id"]),
                    "raw_question": r.get("raw_question"),
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                    "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
                    "status": r.get("status", "completed"),
                    "report_status": r.get("report_status", "not_requested"),
                    "topic_category": r.get("topic_category"),
                    "turn_count": int(r.get("turn_count") or 0),
                    "has_journal": bool(r.get("has_journal")),
                    "original_hexagram_id": r.get("original_hexagram_id"),
                    "transformed_hexagram_id": r.get("transformed_hexagram_id"),
                    "report_data": r.get("report_data"),
                })

            next_cursor = None
            if has_next and items:
                next_cursor = items[-1]["created_at"].isoformat() if items[-1]["created_at"] else None

            return {
                "records": records,
                "next_cursor": next_cursor,
            }
        except Exception:
            logger.error("상담 기록 목록 조회 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="상담 기록 목록 조회 중 오류가 발생했습니다.",
            )


@router.get(
    "/records/{session_id}",
    dependencies=[Depends(check_rate_limit)],
    summary="상담 기록 상세 조회 (대화 턴 및 성찰 저널 포함)",
)
async def get_my_record_detail(
    session_id: str,
    user_id: str = Depends(require_user),
):
    """지정된 세션의 전체 대화 내용과 성찰 저널을 조회합니다. 타 사용자 세션은 404 처리."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. 세션 메타 조회 (소유자 user_id 일치 필수)
            session_stmt = text(
                """
                SELECT id, created_at, updated_at, status, report_status, raw_question, clarified_question, topic_category, report_data
                FROM public.counsel_sessions
                WHERE id = :session_id
                  AND user_id = :user_id
                """
            )
            s_res = await db.execute(session_stmt, {"session_id": session_id, "user_id": user_id})
            session_row = s_res.mappings().first()
            if not session_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="상담 기록을 찾을 수 없습니다.",
                )

            # 2. 대화 턴(turns) 조회
            turns_stmt = text(
                """
                SELECT id, turn_number, user_message, agent_response, original_hexagram_id, transformed_hexagram_id, changing_lines, created_at
                FROM public.counsel_turns
                WHERE session_id = :session_id
                ORDER BY turn_number ASC, created_at ASC
                """
            )
            t_res = await db.execute(turns_stmt, {"session_id": session_id})
            turn_rows = t_res.mappings().all()

            turns = []
            for t in turn_rows:
                turns.append({
                    "turn_number": t.get("turn_number", 1),
                    "user_message": t.get("user_message", ""),
                    "agent_response": t.get("agent_response", ""),
                    "original_hexagram_id": t.get("original_hexagram_id"),
                    "transformed_hexagram_id": t.get("transformed_hexagram_id"),
                    "changing_lines": t.get("changing_lines", []),
                    "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                })

            # 3. 성찰 저널(journal) 조회
            journal_stmt = text(
                """
                SELECT id, summary, key_insights, action_items, created_at
                FROM public.journal_entries
                WHERE session_id = :session_id
                LIMIT 1
                """
            )
            j_res = await db.execute(journal_stmt, {"session_id": session_id})
            journal_row = j_res.mappings().first()

            journal = None
            if journal_row:
                journal = {
                    "summary": journal_row["summary"],
                    "key_insights": journal_row["key_insights"],
                    "action_items": journal_row["action_items"],
                    "created_at": journal_row["created_at"].isoformat() if journal_row["created_at"] else None,
                }

            return {
                "session_id": str(session_row["id"]),
                "created_at": session_row["created_at"].isoformat() if session_row["created_at"] else None,
                "updated_at": session_row["updated_at"].isoformat() if session_row["updated_at"] else None,
                "status": session_row.get("status", "completed"),
                "report_status": session_row.get("report_status", "not_requested"),
                "raw_question": session_row["raw_question"],
                "clarified_question": session_row["clarified_question"],
                "topic_category": session_row["topic_category"],
                "report_data": session_row.get("report_data"),
                "turns": turns,
                "journal": journal,
            }
        except HTTPException:
            raise
        except Exception:
            logger.error("상담 상세 기록 조회 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="상담 상세 기록 조회 중 오류가 발생했습니다.",
            )


@router.delete(
    "/records/{session_id}",
    dependencies=[Depends(check_rate_limit)],
    summary="상담 기록 즉시 파기 (턴, 저널, 크레딧 작업 스냅샷 영구 삭제)",
)
async def delete_my_record(
    session_id: str,
    user_id: str = Depends(require_user),
):
    """지정된 상담 기록을 즉시 영구 삭제합니다.

    - counsel_sessions 행 삭제 (user_id 일치 조건 직접 포함)
    - counsel_turns, journal_entries는 FK CASCADE로 즉시 삭제
    - credit_operations.response_snapshot에 잔존하는 상담 본문 스크러빙 (NULL 업데이트)
    - 타 사용자 세션이나 존재하지 않는 세션은 404 반환
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. 삭제 대상 턴 및 저널 건수 사전 확인
            cnt_turns_stmt = text("SELECT COUNT(*) AS cnt FROM public.counsel_turns WHERE session_id = :session_id")
            res_turns = await db.execute(cnt_turns_stmt, {"session_id": session_id})
            turns_deleted = res_turns.scalar() or 0

            cnt_journal_stmt = text("SELECT COUNT(*) AS cnt FROM public.journal_entries WHERE session_id = :session_id")
            res_journal = await db.execute(cnt_journal_stmt, {"session_id": session_id})
            journal_deleted = bool(res_journal.scalar() or 0)

            # 2. 세션 단일 DELETE 문 실행 (소유권 검증 및 삭제를 한 문장으로 처리하여 경합 방지)
            delete_stmt = text(
                """
                DELETE FROM public.counsel_sessions
                WHERE id = :session_id
                  AND user_id = :user_id
                """
            )
            del_res = await db.execute(delete_stmt, {"session_id": session_id, "user_id": user_id})
            if del_res.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="삭제할 상담 기록이 존재하지 않거나 권한이 없습니다.",
                )

            # 3. 크레딧 작업 스냅샷 스크러빙 (D04: 상담 본문 복제본 제거, 원장 무결성을 위해 행 자체는 보존)
            # user_id가 UUID 형식일 수 있으므로 안전하게 처리
            scrub_stmt = text(
                """
                UPDATE public.credit_operations
                SET response_snapshot = NULL
                WHERE user_id::text = :user_id
                  AND (
                    response_snapshot->>'session_id' = :session_id
                    OR response_snapshot->'journal_data'->>'session_id' = :session_id
                  )
                """
            )
            scrub_res = await db.execute(scrub_stmt, {"user_id": user_id, "session_id": session_id})
            operation_snapshots_scrubbed = scrub_res.rowcount or 0

            await db.commit()

            return {
                "session_id": session_id,
                "deleted": True,
                "turns_deleted": turns_deleted,
                "journal_deleted": journal_deleted,
                "operation_snapshots_scrubbed": operation_snapshots_scrubbed,
            }
        except HTTPException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            logger.error("상담 기록 삭제 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="상담 기록 삭제 처리 중 오류가 발생했습니다.",
            )
