"""Pytest 전역 설정 및 단위 테스트 가드.

- 단위 테스트 중 의도치 않은 외부 네트워크/API 호출 차단 (비용 0원 보장)
- 로컬 DB (localhost, 127.0.0.1, Unix domain socket) 소켓은 허용
"""

import socket
import pytest
from core.db import engine

_real_socket = socket.socket


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


@pytest.fixture(autouse=True)
async def cleanup_db_pool():
    """각 async 테스트 후 이벤트 루프와 연결된 DB 풀 정리"""
    yield
    await engine.dispose()

