# -*- coding: utf-8 -*-
"""비회원 무료 리포트(/api/counsel/preview) 및 세션 승계(/api/counsel/claim) 단위 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from api.deps import check_rate_limit, require_consent
from api.main import app
from api.routers.counsel import require_service_gate, require_generation_enabled, require_cost_budget


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_endpoint_unauthenticated_success():
    """인증 토큰 없이도 비회원은 preview를 호출하여 괘와 리포트를 받을 수 있어야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_service_gate] = lambda: None
    app.dependency_overrides[require_generation_enabled] = lambda: None

    mock_turn_result = SimpleNamespace(
        session_id="preview-session-1234",
        turn_number=1,
        user_facing_message="안녕하세요, 주역 심층 상담 미리보기입니다.",
        needs_followup=True,
        is_final=False,
        hexagram_id=1,
        transformed_hexagram_id=1,
        changing_lines=[],
        safety_category="NORMAL",
        is_duplicate=False,
        journal_summary=None,
        journal_data=None,
        focus_rule=None,
        evidences=[],
        report_data={"final_summary": "건위천 괘 분석 리포트"},
        report_status="ready",
        report_error_code=None,
    )

    with patch("api.main.run_turn", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_turn_result

        # Fake AsyncSessionLocal
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        class FakeSessionContext:
            async def __aenter__(self):
                return mock_session
            async def __aexit__(self, *args):
                return False

        with patch("api.routers.counsel.AsyncSessionLocal", return_value=FakeSessionContext()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                res = await client.post(
                    "/api/counsel/preview",
                    json={"question": "새로운 시작을 앞두고 조언을 구합니다."},
                )
                assert res.status_code == 200
                data = res.json()
                assert data["session_id"] == "preview-session-1234"
                assert data["hexagram_id"] == 1
                assert data["report_data"]["final_summary"] == "건위천 괘 분석 리포트"
                assert data["is_crisis"] is False


@pytest.mark.asyncio
async def test_claim_endpoint_session_not_found():
    """존재하지 않는 세션을 claim 시도하면 404를 반환해야 한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_service_gate] = lambda: None
    app.dependency_overrides[require_generation_enabled] = lambda: None
    app.dependency_overrides[require_consent] = lambda: "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"
    app.dependency_overrides[require_cost_budget] = lambda: None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_result = SimpleNamespace(scalar_one_or_none=lambda: None)
    mock_session.execute.return_value = mock_result

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, *args):
            return False

    with patch("api.routers.counsel.AsyncSessionLocal", return_value=FakeSessionContext()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post(
                "/api/counsel/claim",
                json={"session_id": "non-existent-session"},
                headers={"Idempotency-Key": "550e8400-e29b-41d4-a716-446655440000"},
            )
            assert res.status_code == 404
            assert res.json()["code"] == "SESSION_NOT_FOUND"
