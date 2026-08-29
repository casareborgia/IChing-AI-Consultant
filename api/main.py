"""[K] FastAPI 백엔드 엔드포인트.

프론트엔드와 멀티에이전트 파이프라인(agents/pipeline.py)을 연결하며,
제로 트러스트(Zero Trust) 원칙에 입각한 입력 검증, CORS 제어, Rate Limiting,
세션 소유권 검증(BOLA 방지), 에러 마스킹을 수행합니다.
"""

from collections import defaultdict
import logging
import time
from typing import Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.pipeline import run_turn
from api.deps import require_user
from core.config import settings
from core.crisis_resources import get_all_crisis_resources, get_crisis_resources_by_context
from core.db import AsyncSessionLocal
from core.models.counsel import CounselSession

logger = logging.getLogger("iching_api")

app = FastAPI(
    title="주역 AI 상담 API",
    description="주역 기반 AI 심층 성찰 상담 멀티에이전트 백엔드 API (Zero-Trust Secured)",
    version="1.0.0",
)

# 1. CORS 설정 (제로 트러스트 도메인 명시적 제어)
default_dev_origins = ["http://localhost:3000", "http://localhost:3005", "http://127.0.0.1:3000", "http://127.0.0.1:3005"]
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = default_dev_origins
else:
    allowed_origins = list(set(allowed_origins + default_dev_origins))

cors_kwargs = {
    "allow_origins": allowed_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["*"],
}
if settings.CORS_ORIGIN_REGEX:
    cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX

app.add_middleware(CORSMiddleware, **cors_kwargs)

# 2. 제로 트러스트 보안 헤더 및 요청 크기 제한 미들웨어
_MAX_BODY_SIZE = 1024 * 1024  # 최대 1MB


@app.middleware("http")
async def add_security_headers_and_limit_size(request: Request, call_next):
    # 본문 크기 사전 검사 (Content-Length 헤더 기반)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "요청 페이로드 크기가 허용 범위(1MB)를 초과했습니다."},
        )

    response = await call_next(request)
    # OWASP 권장 표준 보안 헤더
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# 3. Rate Limiting (IP/사용자당 1분 최대 30회 DoS/과금폭탄 방어)
_RATE_LIMIT_WINDOW = 60.0  # 초
_RATE_LIMIT_MAX_REQUESTS = 30
_request_records: Dict[str, List[float]] = defaultdict(list)


async def check_rate_limit(request: Request):
    """클라이언트 IP 또는 인증 토큰 기준 슬라이딩 윈도우 Rate Limiter."""
    # 메모리 누수 방지: 5000개 이상의 키가 쌓이면 만료된 기록 정리
    now = time.time()
    if len(_request_records) > 5000:
        expired_keys = [k for k, v in _request_records.items() if not v or (now - v[-1] > _RATE_LIMIT_WINDOW)]
        for k in expired_keys:
            _request_records.pop(k, None)

    client_key = request.headers.get("authorization", "") or (request.client.host if request.client else "unknown")
    records = _request_records[client_key]
    _request_records[client_key] = [t for t in records if now - t < _RATE_LIMIT_WINDOW]

    if len(_request_records[client_key]) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="요청 빈도가 너무 높습니다. 1분 후 다시 시도해 주세요.",
        )
    _request_records[client_key].append(now)


# 4. Request Schemas (Pydantic Field 기반 엄격한 입력 검증, user_id 필드 제거)
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "iching-oracle-api", "env": settings.ENVIRONMENT}


@app.get("/api/safety/resources")
async def get_safety_resources_endpoint(context: Optional[str] = None):
    """한국 위기상담 공공 리소스 목록을 반환합니다."""
    if context:
        return {"resources": get_crisis_resources_by_context(context)}
    return {"resources": get_all_crisis_resources()}


@app.post("/api/counsel/start", dependencies=[Depends(check_rate_limit)])
async def start_consultation_endpoint(
    req: StartConsultationRequest,
    user_id: str = Depends(require_user),
):
    """최초 질문으로 상담 세션을 시작하고 괘 도출 및 1턴 결과를 반환합니다 (JWT 인증 필수)."""
    async with AsyncSessionLocal() as db_session:
        try:
            result = await run_turn(
                session=db_session,
                counsel_session_id=None,
                user_id=user_id,
                message=req.question,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

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
                "focus_rule": result.focus_rule,
                "evidences": result.evidences,
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


@app.post("/api/counsel/turn", dependencies=[Depends(check_rate_limit)])
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
                raise HTTPException(status_code=403, detail="해당 세션에 대한 접근 권한이 없습니다.")

            result = await run_turn(
                session=db_session,
                counsel_session_id=req.session_id,
                user_id=user_id,
                message=req.user_message,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

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
                "focus_rule": result.focus_rule,
                "evidences": result.evidences,
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
