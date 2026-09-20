"""Pytest 전역 설정 및 안전 가드.

- 기본 테스트의 외부 네트워크/API 호출 차단
- **모든** 테스트의 DB 대상을 폐기 DB로 제한 (기본 차단)
- 파괴적 DB 테스트의 추가 opt-in, 대상 이름 및 DB 내부 marker 검증

``localhost``도 SSH 터널을 통해 운영 DB를 가리킬 수 있으므로 로컬 주소만으로
안전하다고 판단하지 않는다.

DB 가드가 fixture opt-in이었을 때의 구멍
----------------------------------------
예전에는 `require_disposable_database`를 **명시적으로 요청한** 테스트만 보호했다.
그런데 `AsyncSessionLocal`을 직접 쓰는 테스트가 그 fixture 없이도 여럿 있었고,
`TEST_DATABASE_URL`이 없으면 `DATABASE_URL`이 `.env` 값(운영자의 로컬 개발 DB)으로
남았다. 결과적으로 `pytest tests/` 한 번이 개발 DB에 행을 썼다. 파괴적 테스트만
막고 일반 테스트의 쓰기는 막지 않았던 것이다.

이제는 반대로 한다. **기본이 차단이고, 폐기 DB를 명시해야 열린다.**
`TEST_DATABASE_URL`이 없거나 폐기 대상이 아니면 `DATABASE_URL`을 연결 불가능한
sentinel로 돌린다. DB를 쓰는 테스트는 조용히 통과하는 대신 연결 실패로 끊긴다.
그것이 개발 DB에 쓰는 것보다 낫다.

폐기 DB로 전체 테스트를 돌리려면::

    scripts/e2e/run_cycle06.sh   # 하네스는 자체 폐기 컨테이너를 띄운다
    # 또는 직접 준비한 폐기 DB를 지정한다
    TEST_DATABASE_URL=postgresql+asyncpg://u:p@127.0.0.1:15432/iching_x_test pytest tests/
"""

import os
import socket

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url


_DESTRUCTIVE_CONFIRMATION = "I_UNDERSTAND_THIS_DATABASE_IS_DISPOSABLE"
_DATABASE_MARKER = "ICHING_DISPOSABLE_TEST_DB_V1"
_MARKER_QUERY = text(
    "SELECT marker_value FROM public.test_environment_marker "
    "WHERE marker_key = 'purpose'"
)

# 연결이 성립할 수 없는 대상. 이름 자체가 차단 사유를 설명한다.
# 포트 1은 열려 있지 않으므로 쓰기는커녕 연결도 되지 않는다.
_BLOCKED_DATABASE_URL = (
    "postgresql+asyncpg://guard:blocked@127.0.0.1:1/iching_guard_blocked_test"
)


def _disposable_target_errors(raw_url: str) -> list[str]:
    """일반 테스트가 써도 되는 폐기 DB인지 연결 전에 판정한다.

    파괴적 테스트용 `_destructive_database_configuration_errors`보다 느슨하다.
    확인 문구(`ICHING_TEST_DB_CONFIRM`)는 요구하지 않는다. 여기서 막으려는 것은
    "개발·운영 DB를 테스트 대상으로 쓰는 것"이지 파괴적 연산 자체가 아니다.
    """
    errors: list[str] = []
    if not raw_url:
        return ["TEST_DATABASE_URL이 설정되지 않았습니다"]

    try:
        parsed = make_url(raw_url)
    except Exception:
        return ["TEST_DATABASE_URL을 SQLAlchemy URL로 해석할 수 없습니다"]

    if not parsed.drivername.startswith("postgresql"):
        errors.append("테스트 DB는 PostgreSQL 전용입니다")
    if parsed.host not in {"localhost", "127.0.0.1", "::1", None}:
        errors.append("TEST_DATABASE_URL은 로컬 호스트 또는 Unix socket만 허용합니다")
    if not (parsed.database or "").lower().endswith("_test"):
        errors.append("테스트 DB 이름은 '_test'로 끝나야 합니다")
    return errors


# core.db가 엔진을 생성하기 전에 대상을 확정한다. 제품 설정이나 .env의
# DATABASE_URL을 테스트 대상으로 암묵 재사용하지 않는다.
_test_database_url = os.getenv("TEST_DATABASE_URL", "").strip()
_database_target_errors = _disposable_target_errors(_test_database_url)

if _database_target_errors:
    # 폐기 DB가 지정되지 않았거나 지정값이 안전하지 않다. 연결 자체를 막는다.
    os.environ["DATABASE_URL"] = _BLOCKED_DATABASE_URL
    _database_guard_state = "BLOCKED"
else:
    os.environ["DATABASE_URL"] = _test_database_url
    _database_guard_state = "DISPOSABLE"

from core.config import settings  # noqa: E402
from core.db import engine  # noqa: E402


def pytest_report_header(config):
    """실행 머리말에 DB 가드 상태를 알린다. 실패했을 때 이유를 찾게 만든다."""
    if _database_guard_state == "DISPOSABLE":
        name = make_url(_test_database_url).database
        return f"iching db guard: DISPOSABLE (대상 {name})"
    return [
        "iching db guard: BLOCKED — DB를 쓰는 테스트는 연결 실패로 끊깁니다",
        "  사유: " + "; ".join(_database_target_errors),
        "  해제: TEST_DATABASE_URL에 로컬 '_test' PostgreSQL을 지정하십시오",
    ]


def _destructive_database_configuration_errors() -> list[str]:
    """연결 전에 판정할 수 있는 파괴적 테스트 설정 오류를 반환한다."""
    errors: list[str] = []
    test_url = os.getenv("TEST_DATABASE_URL", "").strip()
    confirmation = os.getenv("ICHING_TEST_DB_CONFIRM", "").strip()

    if not test_url:
        return ["TEST_DATABASE_URL이 설정되지 않았습니다"]

    try:
        parsed = make_url(test_url)
    except Exception:
        return ["TEST_DATABASE_URL을 SQLAlchemy URL로 해석할 수 없습니다"]

    if not parsed.drivername.startswith("postgresql"):
        errors.append("파괴적 통합 테스트는 PostgreSQL 전용입니다")

    if parsed.host not in {"localhost", "127.0.0.1", "::1", None}:
        errors.append("TEST_DATABASE_URL은 로컬 호스트 또는 Unix socket만 허용합니다")

    database_name = (parsed.database or "").lower()
    if not database_name.endswith("_test"):
        errors.append("테스트 DB 이름은 '_test'로 끝나야 합니다")

    if confirmation != _DESTRUCTIVE_CONFIRMATION:
        errors.append(
            "ICHING_TEST_DB_CONFIRM에 파괴적 테스트 확인 문구가 없습니다"
        )

    if settings.DATABASE_URL != test_url:
        errors.append("테스트 엔진이 TEST_DATABASE_URL을 사용하지 않습니다")

    return errors


@pytest.fixture(autouse=True)
def guard_external_network(monkeypatch, request):
    """'live_api' 마크가 없는 테스트에서 외부 네트워크 연결을 차단합니다."""
    if "live_api" in request.keywords:
        return

    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        # 로컬호스트 및 유닉스 소켓만 허용 (DB 및 로컬 서비스)
        if host in ("localhost", "127.0.0.1", "::1") or not isinstance(host, str):
            return orig_connect(self, address)
        raise RuntimeError(
            f"단위 테스트 중 외부 네트워크 연결이 차단되었습니다 ({host}). "
            "Mock LLM 또는 DB fixture를 사용하십시오."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
async def require_disposable_database():
    """전체 DELETE/DDL 테스트 전에 전용 DB와 marker를 검증한다.

    marker는 테스트 DB를 준비하는 사람이 명시적으로 생성해야 한다::

        CREATE TABLE public.test_environment_marker (
            marker_key text PRIMARY KEY,
            marker_value text NOT NULL
        );
        INSERT INTO public.test_environment_marker(marker_key, marker_value)
        VALUES ('purpose', 'ICHING_DISPOSABLE_TEST_DB_V1');

    이 fixture는 marker를 생성하거나 DB를 초기화하지 않는다.
    """
    errors = _destructive_database_configuration_errors()
    if errors:
        pytest.fail(
            "파괴적 DB 테스트 안전 가드가 실행을 차단했습니다: " + "; ".join(errors),
            pytrace=False,
        )

    try:
        async with engine.connect() as connection:
            marker = (await connection.execute(_MARKER_QUERY)).scalar_one_or_none()
    except Exception as exc:
        pytest.fail(
            "파괴적 DB 테스트 marker를 확인할 수 없습니다 "
            f"({type(exc).__name__}). 대상 DB에서 marker를 먼저 준비하십시오.",
            pytrace=False,
        )

    if marker != _DATABASE_MARKER:
        pytest.fail(
            "파괴적 DB 테스트 marker 값이 일치하지 않습니다.",
            pytrace=False,
        )

    yield


@pytest.fixture(autouse=True)
async def cleanup_db_pool():
    """각 async 테스트 후 이벤트 루프와 연결된 DB 풀 정리"""
    yield
    await engine.dispose()
