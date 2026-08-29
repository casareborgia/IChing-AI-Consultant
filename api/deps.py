"""FastAPI 인증 및 공통 의존성 (Supabase JWT Verification).

클라이언트가 전송한 Authorization: Bearer <JWT> 헤더를 검증하여
위조 불가능한 user_id(sub)를 확정합니다.
"""

import logging
from fastapi import HTTPException, Request
import jwt

from core.config import settings

logger = logging.getLogger("iching_auth")


async def require_user(request: Request) -> str:
    """Authorization 헤더의 Supabase JWT를 검증하고 user_id(sub)를 반환합니다.

    - 알고리즘: HS256 (Supabase JWT Secret 서명)
    - Audience: 'authenticated'
    - 만료 시간(exp) 및 필수 클레임(sub) 검증
    - SUPABASE_JWT_SECRET 미설정 시 환경과 무관하게 거부 (fail-closed)
    """
    auth_header = request.headers.get("authorization", "").strip()
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

    jwt_secret = settings.SUPABASE_JWT_SECRET

    # 시크릿이 없으면 환경과 무관하게 거부한다 (fail-closed).
    #
    # 이전에는 ENVIRONMENT != "production" 이면 서명 검증을 건너뛰고 토큰 문자열을
    # 그대로 user_id 로 썼다. 설정값 둘(시크릿·환경)이 모두 맞아야만 안전한 구조라,
    # ENVIRONMENT 하나가 빠지면(기본값이 "development"다) 위조 방지가 조용히
    # 사라진다. 그것이 막으려던 바로 그 취약점이다.
    #
    # 로컬 개발도 .env 에 SUPABASE_JWT_SECRET 을 넣어야 한다(.env.example 참고).
    # 테스트는 monkeypatch 로 주입한다(tests/test_jwt_auth.py).
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
        logger.warning("JWT 서명 검증 실패: %s", type(e).__name__)
        # 에러 마스킹 원칙: 내부 예외를 노출하지 않고 일반화된 메시지만 반환
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
