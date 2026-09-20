# -*- coding: utf-8 -*-
"""테스트 전용 JWT 발급.

제품 인증을 우회하지 않는다. `api.deps.require_user`의 실제 HS256 검증 경로를
그대로 지나가는 토큰을 만든다. 서명키는 이 실행에서만 존재하는 난수이고,
발급자는 로컬 테스트 발급자다. `dev-token` 우회는 쓰지 않는다 (모든 사용자가
같은 고정 UUID가 되어 소유권 검사를 검증할 수 없다).
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt


def new_secret() -> str:
    """이 실행에서만 쓰는 대칭 서명키."""
    return secrets.token_urlsafe(48)


def new_user_id() -> str:
    return str(uuid.uuid4())


def mint(
    *,
    secret: str,
    issuer: str,
    subject: str,
    expires_in_seconds: int = 3600,
    audience: str = "authenticated",
) -> str:
    """제품이 요구하는 클레임(sub, exp, iss, aud)을 갖춘 HS256 토큰."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "aud": audience,
        "iss": issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        "role": "authenticated",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def mint_expired(*, secret: str, issuer: str, subject: str) -> str:
    now = datetime.now(timezone.utc) - timedelta(hours=2)
    payload = {
        "sub": subject,
        "aud": "authenticated",
        "iss": issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=1)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def mint_wrong_signature(*, issuer: str, subject: str) -> str:
    """서명키가 다른 토큰. 서버는 401이어야 한다."""
    return mint(secret=new_secret(), issuer=issuer, subject=subject)


def issuer_for(supabase_url: str) -> str:
    """`api.deps.expected_issuer()`와 같은 규칙."""
    return "{0}/auth/v1".format((supabase_url or "").rstrip("/"))


def idempotency_key(prefix: str, suffix: Optional[str] = None) -> str:
    """제품 정규식 `^[A-Za-z0-9][A-Za-z0-9_.:\\-]{7,254}$`를 만족하는 키."""
    tail = suffix or uuid.uuid4().hex[:12]
    key = "{0}-{1}".format(prefix, tail)
    if len(key) < 8:
        key = key + "0" * (8 - len(key))
    return key
