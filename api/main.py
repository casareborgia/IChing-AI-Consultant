# -*- coding: utf-8 -*-
"""
[K] FastAPI 백엔드 엔드포인트 및 메인 진입점.

프론트엔드와 멀티에이전트 파이프라인(agents/pipeline.py)을 연결하며,
제로 트러스트(Zero Trust) 원칙에 입각한 입력 검증, CORS 제어, Rate Limiting,
보안 헤더 설정 및 엔드포인트 라우팅을 총괄합니다.
"""

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from api.routers import counsel, card, safety

# 하위 호환성 Re-export (단위 테스트 및 기존 모듈 100% 호환 보장)
from services.credit_service import (
    CONSULTATION_CREDIT_COST,
    WELCOME_CREDITS,
    _charge,
    _refund,
    _ensure_profile,
    _is_chargeable,
    charge_credits,
    refund_credits,
    ensure_user_profile,
    is_chargeable,
)
from api.deps import check_rate_limit, require_user
from agents.pipeline import run_turn
from api.routers.counsel import (
    start_consultation_endpoint,
    counsel_turn_endpoint,
    StartConsultationRequest,
    ConsultationTurnApiRequest,
)
from api.routers.card import export_card_image, CardExportRequest
from api.routers.safety import get_safety_resources

logger = logging.getLogger("iching_api")

app = FastAPI(
    title="주역 AI 상담 API",
    description="주역 기반 AI 심층 성찰 상담 멀티에이전트 백엔드 API (Zero-Trust Secured)",
    version="1.0.0",
)

# 1. CORS 설정 (제로 트러스트 도메인 명시적 제어)
default_dev_origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:3005",
    "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3005"
]
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

if settings.ENVIRONMENT != "production":
    allowed_origins = sorted(set(allowed_origins + default_dev_origins))
elif not allowed_origins:
    allowed_origins = []

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
    # 요청 바디 크기 사전 검사 (DoS 공격 방어)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "요청 본문 크기가 제한(1MB)을 초과했습니다."},
        )

    response = await call_next(request)

    # OWASP 보안 헤더 주입
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# 3. 헬스 체크 엔드포인트
@app.get("/health", summary="시스템 헬스 체크")
async def health_check():
    return {"status": "ok", "service": "iching-oracle-api", "env": settings.ENVIRONMENT}


# 4. 기능별 APIRouter 등록
app.include_router(counsel.router)
app.include_router(card.router)
app.include_router(safety.router)
