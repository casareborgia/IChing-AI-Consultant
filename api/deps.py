"""FastAPI 인증 및 공통 의존성 (Supabase JWT Verification).

클라이언트가 전송한 Authorization: Bearer <JWT> 헤더를 검증하여
위조 불가능한 user_id(sub)를 확정합니다.
Supabase의 최신 ES256 (비대칭 JWKS) 및 레거시 HS256 서명을 모두 지원합니다.
"""

import asyncio
import hashlib
import logging
from typing import Optional
from fastapi import Depends, HTTPException, Request
import jwt
from jwt import PyJWKClient

from core.config import settings

logger = logging.getLogger("iching_auth")

# Supabase JWKS 클라이언트 (ES256 공개키 캐싱)
_jwks_client: Optional[PyJWKClient] = None


def expected_issuer() -> str:
    """이 프로젝트의 Supabase가 발급한 토큰인지 대조할 iss 값."""
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{expected_issuer()}/.well-known/jwks.json"
        # timeout을 주지 않으면 라이브러리 기본값 30초가 걸린다. JWKS가 느려질 때
        # 요청이 길게 매달리고, 동기 호출이라 이벤트 루프까지 함께 막힌다.
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=3600,
            timeout=settings.JWKS_TIMEOUT_SECONDS,
        )
    return _jwks_client


async def require_user(request: Request) -> str:
    """Authorization 헤더의 Supabase JWT를 검증하고 user_id(sub)를 반환합니다.

    - 지원 알고리즘: ES256 (Supabase 신규 비대칭 JWKS), HS256 (레거시 대칭키)
    - Audience: 'authenticated'
    - 만료 시간(exp) 및 필수 클레임(sub) 검증
    """
    auth_header = request.headers.get("authorization", "").strip()
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

    # 개발용 우회는 명시적으로 켠 경우에만 열린다. 예전에는 ENVIRONMENT가
    # "production"이 아니기만 하면 통과했는데, 그 기본값이 "development"라
    # 환경변수가 누락된 배포에서 우회가 살아 있었다.
    if (
        settings.DEV_AUTH_BYPASS_ENABLED
        and settings.ENVIRONMENT != "production"
        and token == "dev-token"
    ):
        return "00000000-0000-0000-0000-000000000000"

    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. 토큰 헤더에서 알고리즘 확인
    alg = None
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
    except Exception:
        # JWT 형식이 아닌 잘못된 문자열인데 SUPABASE_JWT_SECRET도 설정되지 않은 경우 fail-closed 500 처리
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("SUPABASE_JWT_SECRET이 설정되지 않아 인증을 처리할 수 없습니다.")
            raise HTTPException(
                status_code=500,
                detail="인증 서버 설정 오류가 발생했습니다.",
            )
        # SUPABASE_JWT_SECRET이 있는 경우 일반 인증 실패 401 반환
        raise HTTPException(
            status_code=401,
            detail="인증 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. ES256 서명 검증 (Supabase 비대칭 JWKS)
    if alg == "ES256":
        try:
            jwks = get_jwks_client()
            # PyJWKClient는 동기 HTTP 호출이다. async 안에서 그대로 부르면
            # JWKS가 느려질 때 이 워커의 이벤트 루프 전체가 멈춘다.
            signing_key = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, jwks.get_signing_key_from_jwt, token
                ),
                timeout=settings.JWKS_TIMEOUT_SECONDS + 1.0,
            )
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
                issuer=expected_issuer(),
                options={"require": ["exp", "sub", "iss"]},
            )
        except asyncio.TimeoutError:
            # 서명이 틀린 것이 아니라 공개키를 못 가져온 것이다. 401로 뭉뚱그리면
            # 클라이언트가 재로그인을 시도해 상황을 악화시킨다.
            logger.error("JWKS 조회 시간 초과")
            raise HTTPException(
                status_code=503,
                detail="인증 서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
            )
        except jwt.PyJWTError as e:
            logger.warning("ES256 JWT 서명 검증 실패: %s", type(e).__name__)
            raise HTTPException(
                status_code=401,
                detail="인증 정보가 유효하지 않습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. HS256 서명 검증 (레거시 대칭키)
    elif alg == "HS256" or alg is None:
        jwt_secret = settings.SUPABASE_JWT_SECRET
        if not jwt_secret:
            logger.error("SUPABASE_JWT_SECRET이 설정되지 않아 인증을 처리할 수 없습니다.")
            raise HTTPException(
                status_code=500,
                detail="인증 서버 설정 오류가 발생했습니다.",
            )
        try:
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=expected_issuer(),
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError as e:
            logger.warning("HS256 JWT 서명 검증 실패: %s", type(e).__name__)
            raise HTTPException(
                status_code=401,
                detail="인증 정보가 유효하지 않습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        logger.warning("지원되지 않는 JWT 알고리즘: %s", alg)
        raise HTTPException(
            status_code=401,
            detail="인증 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = claims.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(
            status_code=401,
            detail="인증 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 검증이 끝난 뒤에 사용자 기준으로 한 번 더 센다. 헤더 문자열이 아니라
    # sub가 키라서 토큰을 새로 발급받아도 카운터가 초기화되지 않는다.
    _enforce_user_rate_limit(sub)

    # 이후 의존성·핸들러가 다시 검증하지 않고 쓸 수 있게 남긴다.
    request.state.user_id = sub
    return sub


class ConsentRequiredError(HTTPException):
    """이용약관 및 개인정보처리방침 미동의/버전불일치 403 예외 (FIX-2)."""
    def __init__(self):
        super().__init__(
            status_code=403,
            detail={"code": "CONSENT_REQUIRED", "message": "서비스 이용약관 동의가 필요합니다."},
        )


async def require_consent(
    request: Request,
    user_id: str = Depends(require_user),
) -> str:
    """현재 유효한 버전의 이용약관 및 개인정보처리방침 동의(GRANT)를 서버에서 강제합니다 (AG-1 / FIX-2).

    - 기대 버전(settings.LEGAL_DOCUMENTS_VERSION)의 GRANT가 user_consents에 있고,
    - 그보다 나중의 WITHDRAW가 없으면 통과.
    - 미동의, 이전 버전 동의, 또는 철회 상태이면 403 CONSENT_REQUIRED 오류 반환.
    - 정책 문서 버전이 설정되지 않은 경우 fail-closed 503 반환.
    """
    from core.config import get_settings
    from core.db import AsyncSessionLocal
    from sqlalchemy import text

    current_settings = get_settings()
    expected_version = (current_settings.LEGAL_DOCUMENTS_VERSION or "").strip()
    if not expected_version:
        raise HTTPException(
            status_code=503,
            detail={"code": "LEGAL_VERSION_UNSET", "message": "정책 문서 버전이 설정되지 않았습니다."},
        )

    query = text(
        """
        SELECT action, terms_version, privacy_version
        FROM public.user_consents
        WHERE user_id = :user_id
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(query, {"user_id": user_id})
        row = result.mappings().first()

    if not row:
        raise ConsentRequiredError()

    if (
        row["action"] != "GRANT"
        or row["terms_version"] != expected_version
        or row["privacy_version"] != expected_version
    ):
        raise ConsentRequiredError()

    return user_id


import time
from collections import defaultdict

_request_records = defaultdict(list)
_user_records = defaultdict(list)
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX_REQUESTS = 30

# 두 계층으로 나눈다.
#   check_rate_limit  인증 전에 도는 1차 방어. 키는 IP 또는 토큰 해시다.
#   _enforce_user_rate_limit  서명 검증이 끝난 sub 기준 2차 방어.
# 예전에는 Authorization 헤더 원문 하나만 키로 썼다. 토큰을 갱신하면 카운터가
# 초기화됐고, 임의 길이의 헤더가 그대로 딕셔너리 키가 됐다.
#
# 둘 다 아직 프로세스 로컬이다. 인스턴스 간 공유 저장소는 T11에서 도입한다.


def _prune(store: dict, now: float) -> None:
    if len(store) > 5000:
        expired = [k for k, v in store.items() if not v or (now - v[-1] > _RATE_LIMIT_WINDOW)]
        for k in expired:
            store.pop(k, None)


def _hit(store: dict, key: str, limit: int, now: float) -> bool:
    """윈도우 안의 호출을 세고 한도를 넘으면 False를 돌려준다."""
    store[key] = [t for t in store[key] if now - t < _RATE_LIMIT_WINDOW]
    if len(store[key]) >= limit:
        return False
    store[key].append(now)
    return True


def _client_key(request: Request) -> str:
    """인증 전 단계의 키. 토큰 원문을 키로 쓰지 않는다."""
    auth = request.headers.get("authorization", "")
    if auth:
        # 길이가 고정되고 원문이 메모리·로그에 남지 않는다.
        return "t:" + hashlib.sha256(auth.encode("utf-8")).hexdigest()[:32]
    return "ip:" + (request.client.host if request.client else "unknown")


def _enforce_user_rate_limit(user_id: str) -> None:
    """서명 검증이 끝난 사용자 기준 한도. 토큰을 갱신해도 이어서 센다."""
    now = time.time()
    _prune(_user_records, now)
    if not _hit(_user_records, "u:" + user_id, settings.USER_RATE_LIMIT_PER_MINUTE, now):
        raise HTTPException(
            status_code=429,
            detail="요청 빈도가 너무 높습니다. 1분 후 다시 시도해 주세요.",
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )


async def check_rate_limit(request: Request):
    """인증 전에 도는 1차 슬라이딩 윈도우 Rate Limiter."""
    now = time.time()
    _prune(_request_records, now)
    if not _hit(_request_records, _client_key(request), _RATE_LIMIT_MAX_REQUESTS, now):
        raise HTTPException(
            status_code=429,
            detail="요청 빈도가 너무 높습니다. 1분 후 다시 시도해 주세요.",
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
        )


DEFAULT_OPERATOR_USER_IDS = {"c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"}
DEFAULT_OPERATOR_EMAILS = {"casareborgia@gmail.com"}


async def require_operator(
    request: Request,
    user_id: str = Depends(require_user),
) -> str:
    """운영자 권한을 가진 사용자인지 검증합니다.

    1. 기본 및 설정된 OPERATOR_USER_IDS allowlist 대조
    2. 불일치 시 DB의 profiles 테이블에서 이메일을 조회하여 OPERATOR_EMAILS 대조
    3. 불일치 시 404 Not Found 반환 (보안상 경로의 존재를 감춤)
    """
    from core.release_gate import parse_csv_setting
    from core.db import AsyncSessionLocal
    from sqlalchemy import text

    allowed_ids = set(parse_csv_setting(getattr(settings, "OPERATOR_USER_IDS", ""))) | DEFAULT_OPERATOR_USER_IDS
    if user_id in allowed_ids:
        return user_id

    # 이메일 대조
    allowed_emails = set(parse_csv_setting(getattr(settings, "OPERATOR_EMAILS", ""))) | DEFAULT_OPERATOR_EMAILS
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT email FROM public.profiles WHERE id = :user_id"),
                {"user_id": user_id},
            )
            row = result.fetchone()
            if row and row[0] and row[0].strip().lower() in {e.lower() for e in allowed_emails}:
                return user_id
    except Exception:
        logger.warning("운영자 이메일 확인 중 DB 오류 발생", exc_info=True)

    # 비운영자는 경로 은닉을 위해 404 반환
    raise HTTPException(
        status_code=404,
        detail="Not Found",
    )
