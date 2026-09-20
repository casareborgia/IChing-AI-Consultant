# -*- coding: utf-8 -*-
"""운영자 대시보드 API (/api/ops/*) 단위 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from api.deps import check_rate_limit, require_operator, require_user
from api.main import app


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ops_non_operator_returns_404():
    """비운영자가 접근할 경우 경로의 존재를 감추기 위해 404를 반환해야 한다."""
    # check_rate_limit 통과
    app.dependency_overrides[check_rate_limit] = lambda: None
    # 일반 사용자 id
    app.dependency_overrides[require_user] = lambda: "non-operator-id"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # budget
        res_budget = await client.get("/api/ops/budget")
        assert res_budget.status_code == 404

        # dashboard
        res_dash = await client.get("/api/ops/dashboard")
        assert res_dash.status_code == 404

        # credits grant
        res_grant = await client.post(
            "/api/ops/credits/grant",
            json={"target_user_id": "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c", "amount": 100},
        )
        assert res_grant.status_code == 404


@pytest.mark.asyncio
async def test_ops_operator_access_authorized():
    """기본 운영자 ID(casareborgia)로 접근 시 require_operator가 정상 통과한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_operator] = lambda: "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"

    # budget_tracker 모킹
    with patch("api.routers.ops.budget_tracker.get_status_async", new_callable=AsyncMock) as mock_budget:
        mock_budget.return_value = {
            "daily_cost_usd": 0.05,
            "monthly_cost_usd": 1.20,
            "daily_limit_usd": 10.0,
            "monthly_limit_usd": 100.0,
            "daily_remaining_usd": 9.95,
            "monthly_remaining_usd": 98.80,
            "budget_enabled": True,
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res_budget = await client.get("/api/ops/budget")
            assert res_budget.status_code == 200
            data = res_budget.json()
            assert data["daily_cost_usd"] == 0.05
            assert data["budget_enabled"] is True


@pytest.mark.asyncio
async def test_grant_credit_invalid_uuid():
    """크레딧 지급 시 UUID가 비정상이면 400 Bad Request를 반환한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_operator] = lambda: "c9ffeec3-3c26-428e-b22c-fbc7ac5b114c"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/ops/credits/grant",
            json={"target_user_id": "not-a-valid-uuid", "amount": 100},
        )
        assert res.status_code == 400
        assert "UUID" in res.json()["detail"]
