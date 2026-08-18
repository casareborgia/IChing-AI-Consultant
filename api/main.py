"""[K] FastAPI 백엔드 엔드포인트.

프론트엔드와 멀티에이전트 파이프라인(agents/pipeline.py)을 연결합니다.
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.pipeline import run_turn
from core.db import AsyncSessionLocal

app = FastAPI(
    title="주역 AI 상담 API",
    description="주역 기반 AI 심층 성찰 상담 멀티에이전트 백엔드 API",
    version="1.0.0",
)

# CORS 설정 (Next.js 프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartConsultationRequest(BaseModel):
    user_id: Optional[str] = None
    question: str


class ConsultationTurnApiRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    user_message: str


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "iching-oracle-api"}


@app.post("/api/counsel/start")
async def start_consultation_endpoint(req: StartConsultationRequest):
    """최초 질문으로 상담 세션을 시작하고 괘 도출 및 1턴 결과를 반환합니다."""
    async with AsyncSessionLocal() as db_session:
        try:
            result = await run_turn(
                session=db_session,
                counsel_session_id=None,
                user_id=req.user_id,
                message=req.question,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"

            return {
                "session_id": result.session_id,
                "turn_number": result.turn_number,
                "user_facing_message": result.user_facing_message,
                "needs_followup": result.needs_followup,
                "is_final": result.is_final,
                "hexagram_id": result.hexagram_id,
                "transformed_hexagram_id": result.transformed_hexagram_id,
                "changing_lines": result.changing_lines,
                "safety_category": result.safety_category,
                "is_crisis": is_crisis,
                "is_duplicate": result.is_duplicate,
                "journal_summary": result.journal_summary,
                "focus_rule": result.focus_rule,
                # 답변을 만드는 데 실제로 쓰인 주석. 화면의 근거 패널이 이 값만 쓴다 —
                # 프론트엔드가 정적 표에서 근거를 지어내던 자리를 대신한다.
                "evidences": result.evidences,
            }
        except Exception as e:
            await db_session.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/counsel/turn")
async def counsel_turn_endpoint(req: ConsultationTurnApiRequest):
    """상담 턴을 실행하고 결과를 반환합니다."""
    async with AsyncSessionLocal() as db_session:
        try:
            result = await run_turn(
                session=db_session,
                counsel_session_id=req.session_id,
                user_id=req.user_id,
                message=req.user_message,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"

            return {
                "session_id": result.session_id,
                "turn_number": result.turn_number,
                "user_facing_message": result.user_facing_message,
                "needs_followup": result.needs_followup,
                "is_final": result.is_final,
                "hexagram_id": result.hexagram_id,
                "transformed_hexagram_id": result.transformed_hexagram_id,
                "changing_lines": result.changing_lines,
                "safety_category": result.safety_category,
                "is_crisis": is_crisis,
                "is_duplicate": result.is_duplicate,
                "journal_summary": result.journal_summary,
                "focus_rule": result.focus_rule,
                # 답변을 만드는 데 실제로 쓰인 주석. 화면의 근거 패널이 이 값만 쓴다 —
                # 프론트엔드가 정적 표에서 근거를 지어내던 자리를 대신한다.
                "evidences": result.evidences,
            }
        except Exception as e:
            await db_session.rollback()
            raise HTTPException(status_code=500, detail=str(e))
