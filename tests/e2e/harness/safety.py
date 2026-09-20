# -*- coding: utf-8 -*-
"""실행 전 안전 가드.

원격 Supabase나 운영 DB를 향한 실행을 연결 전에 끊는다. `tests/conftest.py`가
파괴적 DB 테스트에 쓰는 것과 같은 계약(`*_test` 이름, marker, 로컬 호스트)을
따른다. 하네스가 자기 규칙을 따로 만들지 않는다.
"""

from __future__ import annotations

import re
from typing import List, Optional

from sqlalchemy.engine import make_url

DATABASE_MARKER = "ICHING_DISPOSABLE_TEST_DB_V1"
DESTRUCTIVE_CONFIRMATION = "I_UNDERSTAND_THIS_DATABASE_IS_DISPOSABLE"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# 원격 관리형 DB로 보이는 호스트. 하나라도 걸리면 즉시 중단한다.
_FORBIDDEN_HOST_PATTERNS = (
    re.compile(r"supabase\.(co|com|net)$", re.I),
    re.compile(r"\.pooler\.supabase\.com$", re.I),
    re.compile(r"amazonaws\.com$", re.I),
    re.compile(r"neon\.tech$", re.I),
    re.compile(r"render\.com$", re.I),
    re.compile(r"run\.app$", re.I),
)


def database_url_problems(url: str) -> List[str]:
    """쓰기가 허용되는 폐기 DB URL인지 판정한다. 빈 목록이면 통과."""
    problems: List[str] = []
    raw = (url or "").strip()
    if not raw:
        return ["DATABASE_URL이 비어 있습니다"]

    try:
        parsed = make_url(raw)
    except Exception:
        return ["DATABASE_URL을 SQLAlchemy URL로 해석할 수 없습니다"]

    if not parsed.drivername.startswith("postgresql"):
        problems.append("E2E 하네스는 PostgreSQL 전용입니다")

    host = (parsed.host or "").strip()
    if host and host not in _LOCAL_HOSTS:
        problems.append("DATABASE_URL은 로컬 호스트만 허용합니다")
    for pattern in _FORBIDDEN_HOST_PATTERNS:
        if host and pattern.search(host):
            problems.append("원격 관리형 데이터베이스 호스트는 거부합니다")
            break

    name = (parsed.database or "").lower()
    if not name.endswith("_test"):
        problems.append("테스트 DB 이름은 '_test'로 끝나야 합니다")

    return problems


def supabase_url_problems(url: str, *, allow_remote_jwks: bool) -> List[str]:
    """토큰 발급자 설정 검사.

    기본 모드는 로컬 발급자만 허용한다. 브라우저 모드에서는 실제 프로젝트의
    공개 JWKS를 **읽기 전용**으로 받아야 ES256 검증이 가능하므로 그때만 원격을
    허용한다. 어느 쪽이든 DB 쓰기 경로와는 무관하다.
    """
    raw = (url or "").strip()
    if not raw:
        return ["SUPABASE_URL이 비어 있습니다"]
    if allow_remote_jwks:
        return []
    if raw.startswith("http://127.0.0.1") or raw.startswith("http://localhost"):
        return []
    return ["기본 모드에서는 로컬 발급자만 허용합니다 (원격 JWKS는 브라우저 모드 전용)"]


def assert_safe_or_die(problems: List[str], context: str) -> None:
    if problems:
        raise SystemExit(
            "[E2E-ABORT] {0} 안전 가드가 실행을 막았습니다: {1}".format(
                context, "; ".join(problems)
            )
        )


def redact(value: Optional[str]) -> str:
    """보고서에 남길 수 없는 값을 고정 문자열로 바꾼다."""
    return "[REDACTED]" if value else "[EMPTY]"
