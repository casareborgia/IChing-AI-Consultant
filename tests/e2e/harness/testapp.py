# -*- coding: utf-8 -*-
"""제품 ASGI 앱을 테스트 환경에 올린다.

제품 소스는 한 줄도 바꾸지 않는다. 바꾸는 것은 두 가지뿐이고 둘 다 제품이
스스로 열어 둔 이음매다.

1. `api.main.run_turn` → 결정론적 fake. 라우터가 이미 동적 참조한다.
2. `app.dependency_overrides[require_service_gate]` → FastAPI가 테스트를 위해
   제공하는 표준 기능.

2번이 필요한 이유는 `docs/commercialization/E2E_CONTRACT.md`에 적었다. 요약하면
이 SHA에서 `RELEASE_ELIGIBLE_SUITE_VERSIONS`가 빈 frozenset이라 어떤 환경변수나
서명 manifest로도 게이트가 열리지 않는다. 하네스는 게이트를 끄기 전에 먼저
'게이트가 실제로 503으로 닫는다'를 시나리오로 증명한다.

인증(`require_user`)과 rate limit(`check_rate_limit`)은 절대 override하지 않는다.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import httpx


def apply_environment(
    *,
    database_url: str,
    supabase_url: str,
    jwt_secret: str,
    cors_origins: str,
) -> None:
    """제품 설정 모듈을 import하기 **전에** 호출해야 한다."""
    os.environ["DATABASE_URL"] = database_url
    os.environ["SUPABASE_URL"] = supabase_url
    os.environ["SUPABASE_JWT_SECRET"] = jwt_secret
    os.environ["CORS_ORIGINS"] = cors_origins
    os.environ["ENVIRONMENT"] = "development"
    # dev-token 우회는 쓰지 않는다. 명시적으로 꺼 둔다.
    os.environ["DEV_AUTH_BYPASS_ENABLED"] = "false"
    # 외부 LLM 경로가 설정 정합성 검사에서 걸리지 않게 로컬 provider로 고정한다.
    # 실제 호출은 fake가 가로채므로 어떤 provider도 호출되지 않는다.
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["SERVICE_STAGE"] = "free_beta"
    os.environ["PURCHASE_ENABLED"] = "false"
    os.environ["GENERATION_ENABLED"] = "true"
    os.environ["LEGAL_DOCUMENTS_VERSION"] = "2026-09-12"


@dataclass
class ServerHandle:
    base_url: str
    port: int
    _server: object
    _thread: threading.Thread

    def shutdown(self) -> None:
        setattr(self._server, "should_exit", True)
        self._thread.join(timeout=20)


def build_app(*, install_fake_pipeline: bool = True):
    """제품 앱을 가져오고 테스트 이음매를 꽂는다."""
    import api.main as api_main
    from tests.e2e.harness import fake_pipeline
    import core.db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool
    from core.config import settings

    core.db.engine = create_async_engine(
        settings.DATABASE_URL, echo=False, future=True, poolclass=NullPool
    )
    core.db.AsyncSessionLocal = async_sessionmaker(
        bind=core.db.engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    if install_fake_pipeline:
        api_main.run_turn = fake_pipeline.fake_run_turn

    return api_main.app


def open_service_gate(app) -> None:
    """출시 게이트 의존성만 테스트 동안 통과시킨다."""
    from api.routers.counsel import require_service_gate

    async def _allow():
        return None

    app.dependency_overrides[require_service_gate] = _allow


def close_service_gate(app) -> None:
    """제품 기본값(fail-closed)으로 되돌린다."""
    from api.routers.counsel import require_service_gate

    app.dependency_overrides.pop(require_service_gate, None)


def start_server(app, port: int, *, timeout: float = 30.0) -> ServerHandle:
    """uvicorn을 백그라운드 스레드에서 띄운다. 실제 TCP 포트를 연다."""
    import uvicorn

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="e2e-uvicorn", daemon=True)
    thread.start()

    base_url = "http://127.0.0.1:{0}".format(port)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if getattr(server, "started", False):
            try:
                httpx.get(base_url + "/api/public/config", timeout=5.0)
                return ServerHandle(
                    base_url=base_url, port=port, _server=server, _thread=thread
                )
            except Exception:
                pass
        time.sleep(0.2)

    setattr(server, "should_exit", True)
    raise RuntimeError("테스트 백엔드가 제한 시간 안에 뜨지 않았습니다")


def build_engine_for_schema(database_url: str):
    """스키마 준비 전용 엔진. 제품 엔진과 같은 URL을 쓴다."""
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(database_url, echo=False, future=True)


def frontend_env(
    *,
    backend_base_url: str,
    supabase_url: Optional[str],
    supabase_anon_key: Optional[str],
) -> dict:
    """브라우저 모드에서 Next.js에 넘길 환경변수."""
    env = dict(os.environ)
    env["NEXT_PUBLIC_API_URL"] = backend_base_url
    if supabase_url:
        env["NEXT_PUBLIC_SUPABASE_URL"] = supabase_url
    if supabase_anon_key:
        env["NEXT_PUBLIC_SUPABASE_ANON_KEY"] = supabase_anon_key
    return env
