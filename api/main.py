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
from sqlalchemy import select, update

from agents.pipeline import run_turn
from api.deps import require_user
from core.config import settings
from core.crisis_resources import get_all_crisis_resources, get_crisis_resources_by_context
from core.db import AsyncSessionLocal
from core.models.counsel import CounselSession, CreditLedger, UserProfile

CONSULTATION_CREDIT_COST = 10
WELCOME_CREDITS = 50

# 크레딧을 받지 않는 유일한 경우는 위기 판정이다. 괘 없이 핫라인 안내만 나가고,
# 가입 화면이 "위기 감지 시 크레딧 미차감"을 약속하며 블루프린트는 이를 SaMD 윤리
# 기준으로 든다.
#
# 재삼독(같은 질문을 다시 물어 괘를 새로 뽑지 않는 경우)은 받는다. 괘가 안 나올 뿐
# 정리·중복 판정·상담 응답까지 파이프라인이 그대로 돌아 비용이 발생하고, 이전 상담을
# 다시 보여주거나 "무엇이 달라졌는지" 되묻는 것 자체가 제공하는 값이다(설계 원칙 2).
def _is_chargeable(result) -> bool:
    return result.safety_category != "BLOCK_CRISIS"


async def _ensure_profile(db_session, user_id: str) -> None:
    """프로필이 없으면 웰컴 크레딧과 함께 만든다. 이미 있으면 아무것도 하지 않는다."""
    exists = (
        await db_session.execute(select(UserProfile.id).where(UserProfile.id == user_id))
    ).scalar_one_or_none()
    if exists is not None:
        return

    # 장부가 프로필을 FK 로 참조하므로 프로필을 먼저 확정한다. 한 번에 flush 하면
    # 삽입 순서를 unit-of-work 에 맡기게 되고, 실제로 장부가 앞서 나가 FK 위반이 났다.
    db_session.add(UserProfile(id=user_id, credit_balance=WELCOME_CREDITS))
    await db_session.flush()
    db_session.add(
        CreditLedger(user_id=user_id, amount=WELCOME_CREDITS, reason="신규 가입 웰컴 크레딧")
    )
    await db_session.flush()


async def _charge(db_session, user_id: str, amount: int, reason: str) -> Optional[int]:
    """잔액이 충족되면 원자적으로 차감하고 장부에 기록한다.

    차감에 성공하면 차감 '후' 잔액을, 잔액이 모자라거나 유저가 없으면 None 을 돌려준다.
    """
    stmt = (
        update(UserProfile)
        .where(UserProfile.id == user_id, UserProfile.credit_balance >= amount)
        .values(credit_balance=UserProfile.credit_balance - amount)
        .returning(UserProfile.credit_balance)
    )
    balance = (await db_session.execute(stmt)).scalar_one_or_none()
    if balance is None:
        return None
    db_session.add(CreditLedger(user_id=user_id, amount=-amount, reason=reason))
    await db_session.flush()
    return balance


async def _refund(db_session, user_id: str, amount: int, reason: str) -> Optional[int]:
    """차감을 되돌린다. 되돌린 뒤 잔액을 돌려준다."""
    stmt = (
        update(UserProfile)
        .where(UserProfile.id == user_id)
        .values(credit_balance=UserProfile.credit_balance + amount)
        .returning(UserProfile.credit_balance)
    )
    balance = (await db_session.execute(stmt)).scalar_one_or_none()
    if balance is None:
        return None
    db_session.add(CreditLedger(user_id=user_id, amount=amount, reason=reason))
    await db_session.flush()
    return balance


logger = logging.getLogger("iching_api")

app = FastAPI(
    title="주역 AI 상담 API",
    description="주역 기반 AI 심층 성찰 상담 멀티에이전트 백엔드 API (Zero-Trust Secured)",
    version="1.0.0",
)

# 1. CORS 설정 (제로 트러스트 도메인 명시적 제어)
#
# 와일드카드 정규식(`^https://.*\.vercel\.app$`)을 쓰지 않는다. vercel.app 하위
# 도메인은 누구나 무료로 받을 수 있어, allow_credentials=True 와 만나면 임의의
# 제3자 페이지가 자격증명을 실은 교차출처 요청을 보낼 수 있다. 프리뷰 배포가
# 필요하면 CORS_ORIGIN_REGEX 로 프로젝트 이름까지 좁혀 명시적으로 켠다.
default_dev_origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:3005",
    "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3005"
]
allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]

# 개발 기본 오리진을 프로덕션에 자동으로 얹지 않는다. 필요하면 CORS_ORIGINS 에
# 직접 적을 것 — 코드가 몰래 넣어주면 설정 목록만 보고는 무엇이 허용됐는지 모른다.
#
# 이 가드는 859631b 에서 넣었다가 1840196 의 api/main.py 재작성 때 사라졌고,
# 그 사이 프로덕션이 localhost 를 계속 허용하고 있었다. 지우지 말 것.
if settings.ENVIRONMENT != "production":
    allowed_origins = sorted(set(allowed_origins + default_dev_origins))
elif not allowed_origins:
    # 프로덕션인데 목록이 비었다면 개발 기본값으로 열지 않는다. 아무것도 허용하지 않는다.
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
    """최초 질문으로 상담 세션을 시작하고 괘 도출 및 1턴 결과를 반환합니다 (JWT 인증 필수, 10 크레딧 차감)."""
    async with AsyncSessionLocal() as db_session:
        try:
            # 1. 크레딧 차감 — 턴을 돌리기 전에 원자적으로 잡아둔다.
            #
            # ORM 객체의 credit_balance 를 파이썬에서 빼는 방식은 읽고-계산하고-쓰기라,
            # 동시 요청 둘이 같은 잔액을 읽고 서로의 차감을 덮어쓴다. 40 크레딧에 8건을
            # 동시에 던지면 8건이 전부 통과했다(tests/test_credit_system.py). _charge 는
            # 조건과 갱신을 한 문장에 두어 그 창을 없앤다.
            await _ensure_profile(db_session, user_id)
            balance_after_charge = await _charge(
                db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 상담 세션 시작"
            )
            if balance_after_charge is None:
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

            # 2. 턴 실행
            result = await run_turn(
                session=db_session,
                counsel_session_id=None,
                user_id=user_id,
                message=req.question,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

            # 3. 위기 판정이면 되돌린다.
            #
            # run_turn 이 내부에서 커밋하므로 차감은 이미 확정돼 있다. 취소가 아니라
            # 환불이고, 장부에 -10 과 +10 이 사유와 함께 나란히 남는다.
            remaining_credits = balance_after_charge
            if not _is_chargeable(result):
                refunded = await _refund(
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

            # 크레딧 차감 (대화 턴당 10C). start 와 같은 자를 쓴다 —
            # ORM 객체의 잔액을 파이썬에서 빼면 동시 요청이 서로의 차감을 덮어쓴다.
            await _ensure_profile(db_session, user_id)
            balance_after_charge = await _charge(
                db_session, user_id, CONSULTATION_CREDIT_COST, "주역 성찰 대화 턴 진행"
            )
            if balance_after_charge is None:
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

            result = await run_turn(
                session=db_session,
                counsel_session_id=req.session_id,
                user_id=user_id,
                message=req.user_message,
            )
            await db_session.commit()

            is_crisis = result.safety_category == "BLOCK_CRISIS"
            crisis_resources = get_crisis_resources_by_context() if is_crisis else []

            # 위기 판정이면 되돌린다. 위기 신호는 첫 질문보다 대화 도중에 나올 여지가
            # 크므로, start 에만 붙여두면 정작 필요한 자리가 비게 된다.
            remaining_credits = balance_after_charge
            if not _is_chargeable(result):
                refunded = await _refund(
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
