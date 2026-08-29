"""FastAPI 인증 및 공통 의존성 (Supabase JWT Verification).

클라이언트가 전송한 Authorization: Bearer <JWT> 헤더를 검증하여
위조 불가능한 user_id(sub)를 확정합니다.
"""

import logging
from typing import Optional
from fastapi import HTTPException, Request
import jwt

from core.config import settings

logger = logging.getLogger("iching_auth")


async def require_user(request: Request) -> str:
    """Authorization 헤더의 Supabase JWT를 검증하고 user_id(sub)를 반환합니다.

    - 알고리즘: HS256 (Supabase JWT Secret 서명)
    - Audience: 'authenticated'
    - 만료 시간(exp) 및 필수 클레임(sub) 검증
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

    # 1. 프로덕션 환경이거나 JWT Secret이 설정된 경우: 엄격한 서명 및 클레임 검증
    if jwt_secret:
        try:
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
            sub = claims.get("sub")
            if not sub or not isinstance(sub, str):
                raise HTTPException(status_code=401, detail="인증 정보가 유효하지 않습니다.")
            return sub
        except jwt.PyJWTError as e:
            logger.warning("JWT 서명 검증 실패: %s", type(e).__name__)
            # 에러 마스킹 원칙: 내부 예외를 노출하지 않고 일반화된 메시지만 반환
            raise HTTPException(
                status_code=401,
                detail="인증 정보가 유효하지 않습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        # 2. 로컬 개발/테스트 환경 (SUPABASE_JWT_SECRET 미설정 시)
        if settings.ENVIRONMENT == "production":
            logger.error("프로덕션 환경에 SUPABASE_JWT_SECRET이 설정되지 않았습니다.")
            raise HTTPException(
                status_code=500,
                detail="인증 서버 설정 오류가 발생했습니다.",
            )

        # 개발/테스트 환경 fallback: JWT 포맷이면 payload 디코드, 일반 문자열이면 그대로 sub로 사용
        try:
            unverified_claims = jwt.decode(token, options={"verify_signature": False})
            sub = unverified_claims.get("sub")
            if sub and isinstance(sub, str):
                return sub
        except jwt.PyJWTError:
            pass

        # 토큰 자체가 단순 mock ID인 경우 (테스트 환경)
        return token
