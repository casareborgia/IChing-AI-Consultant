"""FastAPI 인증 및 공통 의존성 (Supabase JWT Verification).

클라이언트가 전송한 Authorization: Bearer <JWT> 헤더를 검증하여
위조 불가능한 user_id(sub)를 확정합니다.
Supabase의 최신 ES256 (비대칭 JWKS) 및 레거시 HS256 서명을 모두 지원합니다.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Request
import jwt
from jwt import PyJWKClient

from core.config import settings

logger = logging.getLogger("iching_auth")

# Supabase JWKS 클라이언트 (ES256 공개키 캐싱)
_jwks_client: Optional[PyJWKClient] = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


async def require_user(request: Request) -> str:
    """Authorization 헤더의 Supabase JWT를 검증하고 user_id(sub)를 반환합니다.

    - 지원 알고리즘: ES256 (Supabase 신규 비대칭 JWKS), HS256 (레거시 대칭키)
    - Audience: 'authenticated'
    - 만료 시간(exp) 및 필수 클레임(sub) 검증
    """
    auth_header = request.headers.get("authorization", "").strip()
    token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

    # 로컬 개발 환경에서 dev-token 헤더를 명시적으로 보낸 경우만 테스트용 UUID 반환
    if settings.ENVIRONMENT != "production" and token == "dev-token":
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
            signing_key = jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
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
                options={"require": ["exp", "sub"]},
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
    return sub
