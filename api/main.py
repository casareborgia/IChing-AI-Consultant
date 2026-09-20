# -*- coding: utf-8 -*-
"""
[K] FastAPI 백엔드 엔드포인트 및 메인 진입점.

프론트엔드와 멀티에이전트 파이프라인(agents/pipeline.py)을 연결하며,
제로 트러스트(Zero Trust) 원칙에 입각한 입력 검증, CORS 제어, Rate Limiting,
보안 헤더 설정 및 엔드포인트 라우팅을 총괄합니다.
"""

import logging
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.db import AsyncSessionLocal
from core.logging_config import configure_logging
from core.release_gate import (
    check_config_consistency,
    evaluate_release_gate,
    public_service_config,
)
from sqlalchemy import text

# uvicorn은 root 로거를 설정하지 않는다. 라우터·에이전트를 임포트하기 전에 여기서
# 잡아두지 않으면 앱의 logger.info()가 전부 유실된다(core/logging_config.py 참고).
configure_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)

logger = logging.getLogger("iching_api")

# 설정끼리 모순되면 기동을 막는다. free_beta인데 결제가 켜져 있다거나, allowlist에
# 없는 provider/리전으로 가려는 상태로 서비스가 뜨면 안 된다. 개발 환경에서는
# 경고만 남겨 로컬 실험을 막지 않는다.
_config_problems = check_config_consistency(settings)
if _config_problems:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError("설정 모순으로 기동할 수 없습니다: " + "; ".join(_config_problems))
    logger.warning("설정 모순 감지(개발 환경이라 계속 진행): %s", "; ".join(_config_problems))

from api.routers import counsel, card, credits, safety, consent, records, support, ops, account, telemetry

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
from services.credit_operation_service import (
    ENDPOINT_START,
    ENDPOINT_TURN,
    OPERATION_LEASE_SECONDS,
    begin_operation,
    compute_request_hash,
    finalize_release,
    finalize_success,
    read_credit_state,
    recover_expired_operations,
    validate_idempotency_key,
)
from api.deps import check_rate_limit, require_user
from agents.pipeline import run_turn
from api.routers.counsel import (
    start_consultation_endpoint,
    counsel_turn_endpoint,
    StartConsultationRequest,
    ConsultationTurnApiRequest,
)
from api.routers.counsel import get_operation_status_endpoint
from api.routers.credits import get_my_credits
from api.routers.card import export_card_image, CardExportRequest
from api.routers.safety import get_safety_resources

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


from api.deps import ConsentRequiredError


@app.exception_handler(ConsentRequiredError)
async def consent_required_handler(request: Request, exc: ConsentRequiredError):
    return JSONResponse(
        status_code=403,
        content={
            "code": "CONSENT_REQUIRED",
            "message": "서비스 이용약관 동의가 필요합니다.",
            "detail": "서비스 이용약관 동의가 필요합니다.",
        },
    )



# 3. 공개 서비스 설정 (DRAFT: 소비 형태는 Antigravity와 합의 후 확정)
# 프런트가 요율·1회 차감량·결제 가능 여부를 따로 하드코딩하지 않도록 서버가 알려준다.
# 비밀값과 운영자 결정 원문은 포함하지 않는다.
@app.get("/api/public/config", summary="프런트가 읽는 최소 공개 설정")
async def public_config():
    return public_service_config(
        settings,
        consultation_credit_cost=CONSULTATION_CREDIT_COST,
        welcome_credits=WELCOME_CREDITS,
    )


# 4. 출시 게이트 상태 (읽기 전용 진단)
# 운영자와 Codex의 출시 검사 스크립트가 같은 판정을 보게 한다.
@app.get("/api/public/release-gate", summary="설정 기준 출시 게이트 상태")
async def release_gate_status():
    return evaluate_release_gate(settings).to_dict()


# 5. 헬스 체크 엔드포인트
@app.get("/health", summary="시스템 헬스 체크")
async def health_check():
    try:
        async def check_db():
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))

        await asyncio.wait_for(check_db(), timeout=3.0)
    except Exception:
        logger.error("헬스 체크 DB 연결 실패", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": "iching-oracle-api",
                "env": settings.ENVIRONMENT,
                "database": "unavailable",
            },
        )
    return {
        "status": "ok",
        "service": "iching-oracle-api",
        "env": settings.ENVIRONMENT,
        "database": "ok",
    }


# 4. 기능별 APIRouter 등록
app.include_router(counsel.router)
app.include_router(credits.router)
app.include_router(card.router)
app.include_router(safety.router)
app.include_router(consent.router)
app.include_router(records.router)
app.include_router(support.router)
app.include_router(ops.router)
app.include_router(account.router)
app.include_router(telemetry.router)
