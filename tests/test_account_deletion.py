# -*- coding: utf-8 -*-
"""회원 탈퇴 API (/api/me/account) 단위 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from api.deps import check_rate_limit, require_user
from api.main import app


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_account_deletion_unauthenticated_blocked():
    """인증 토큰이 없으면 401로 차단되어야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.delete("/api/me/account")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_account_deletion_invalid_uuid():
    """user_id가 UUID 형식이 아니면 400 Bad Request를 반환해야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_user] = lambda: "invalid-user-id"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.delete("/api/me/account")
        assert res.status_code == 400
        assert "UUID" in res.json()["detail"]


@pytest.mark.asyncio
async def test_account_deletion_success():
    """D-6 & D-4: 인증된 유저가 탈퇴 요청 시 정상 성공 응답(200) 및 auth_account_deleted=True를 반환해야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_user] = lambda: "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"

    # AsyncSessionLocal 모킹
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            return False

    with patch("api.routers.account.AsyncSessionLocal", return_value=FakeSessionContext()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.delete("/api/me/account")
            assert res.status_code == 200
            data = res.json()
            assert data["success"] is True
            assert data["auth_account_deleted"] is True
            assert "파기" in data["message"]
            assert mock_session.commit.call_count == 2
            assert not mock_session.rollback.called


@pytest.mark.asyncio
async def test_account_deletion_partial_failure_auth_users_fails(caplog):
    """D-1, D-2, D-3: 7단계 auth.users 실패 시 1~6단계는 커밋되고, auth_account_deleted=False 및 ERROR 로그가 남아야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    test_uid = "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"
    app.dependency_overrides[require_user] = lambda: test_uid

    executed_statements = []
    commits = 0
    rollbacks = 0

    async def fake_execute(stmt, params=None):
        stmt_str = str(stmt.text if hasattr(stmt, "text") else stmt)
        executed_statements.append(stmt_str)
        if "auth.users" in stmt_str:
            raise RuntimeError("permission denied for relation auth.users")
        return AsyncMock()

    async def fake_commit():
        nonlocal commits
        commits += 1

    async def fake_rollback():
        nonlocal rollbacks
        rollbacks += 1

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=fake_execute)
    mock_session.commit = AsyncMock(side_effect=fake_commit)
    mock_session.rollback = AsyncMock(side_effect=fake_rollback)

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            return False

    with caplog.at_level("ERROR"):
        with patch("api.routers.account.AsyncSessionLocal", return_value=FakeSessionContext()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.delete("/api/me/account")

    # D-1: 1~6단계(프로필, 방문로그, 상담세션 등) SQL이 정상 실행되고 주 삭제 확정 커밋됨
    assert any("profiles" in s for s in executed_statements)
    assert any("site_visits" in s for s in executed_statements)
    assert any("counsel_sessions" in s for s in executed_statements)
    assert commits == 1  # 1~6단계 주 삭제 확정 1차 커밋
    assert rollbacks == 1  # 7단계 실패에 대한 롤백

    # D-2: HTTP 200, success=True, auth_account_deleted=False, 안내 문구
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["auth_account_deleted"] is False
    assert "로그인 계정 삭제가 완료되지 않았습니다" in data["message"]
    assert "고객지원" in data["message"]

    # D-3: logger.error 기록 확인
    assert any("auth.users 삭제 실패" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_account_deletion_main_step_failure_returns_500_and_rollbacks():
    """D-5: 1~6단계 중 실패 시 500 반환 및 전체 롤백되어 아무것도 커밋되지 않아야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_user] = lambda: "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB connection error during profiles delete"))
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            return False

    with patch("api.routers.account.AsyncSessionLocal", return_value=FakeSessionContext()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.delete("/api/me/account")

    assert res.status_code == 500
    assert "회원 탈퇴 처리 중 오류" in res.json()["detail"]
    assert mock_session.commit.call_count == 0
    assert mock_session.rollback.called
