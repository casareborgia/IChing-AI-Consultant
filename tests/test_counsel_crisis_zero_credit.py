# -*- coding: utf-8 -*-
"""크레딧 0일 때도 위기 신호를 놓치지 않는 안전망 단위 테스트 (BACKLOG.md #73)."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from api.deps import check_rate_limit, require_consent
from api.routers.counsel import require_cost_budget, require_service_gate, require_generation_enabled
from api.main import app
from schemas.counsel import SafetyVerdict
from services.credit_operation_service import (
    OperationOutcome,
    STATUS_REJECTED,
    KIND_REPLAY,
    CODE_INSUFFICIENT_CREDITS,
)


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zero_credit_normal_message_returns_402():
    """잔액 부족 시 일반적인 메시지는 402 Insufficient Credit을 반환한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_consent] = lambda: "user-zero-credit"
    app.dependency_overrides[require_cost_budget] = lambda: None
    app.dependency_overrides[require_service_gate] = lambda: None
    app.dependency_overrides[require_generation_enabled] = lambda: None

    # begin_operation이 STATUS_REJECTED를 반환하도록 모킹
    rejected_outcome = OperationOutcome(
        kind=KIND_REPLAY,
        operation_id="op-rejected-1",
        status=STATUS_REJECTED,
        amount=10,
        credit_delta=0,
        remaining_credits=0,
        error_code=CODE_INSUFFICIENT_CREDITS,
        error_message="크레딧이 부족합니다. (필요: 10, 잔여: 0)",
    )

    with patch("api.routers.counsel.begin_operation", new_callable=AsyncMock) as mock_begin, \
         patch("agents.safety.screen", new_callable=AsyncMock) as mock_screen:
        mock_begin.return_value = rejected_outcome
        mock_screen.return_value = SafetyVerdict(category="NORMAL", signals=[], reason="일반 고민")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post(
                "/api/counsel/start",
                headers={"Idempotency-Key": "idemp-zero-credit-normal-1"},
                json={"question": "새로운 프로젝트를 준비 중입니다."},
            )
            assert res.status_code == 402
            data = res.json()
            assert data["code"] == CODE_INSUFFICIENT_CREDITS
            assert data["remaining_credits"] == 0


@pytest.mark.asyncio
async def test_zero_credit_crisis_message_returns_200_crisis():
    """잔액이 0이어도 위기 징후(BLOCK_CRISIS)가 감지되면 402 대신 200 OK와 핫라인 리소스를 반환한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None
    app.dependency_overrides[require_consent] = lambda: "user-zero-credit"
    app.dependency_overrides[require_cost_budget] = lambda: None
    app.dependency_overrides[require_service_gate] = lambda: None
    app.dependency_overrides[require_generation_enabled] = lambda: None

    rejected_outcome = OperationOutcome(
        kind=KIND_REPLAY,
        operation_id="op-rejected-2",
        status=STATUS_REJECTED,
        amount=10,
        credit_delta=0,
        remaining_credits=0,
        error_code=CODE_INSUFFICIENT_CREDITS,
        error_message="크레딧이 부족합니다. (필요: 10, 잔여: 0)",
    )

    with patch("api.routers.counsel.begin_operation", new_callable=AsyncMock) as mock_begin, \
         patch("agents.safety.screen", new_callable=AsyncMock) as mock_screen:
        mock_begin.return_value = rejected_outcome
        mock_screen.return_value = SafetyVerdict(
            category="BLOCK_CRISIS",
            context=None,
            signals=["crisis_detected"],
            reason="자해/위기 신호 감지",
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post(
                "/api/counsel/start",
                headers={"Idempotency-Key": "idemp-zero-credit-crisis-1"},
                json={"question": "더 이상 살고 싶지 않아요. 끝내고 싶습니다."},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["is_crisis"] is True
            assert len(data["crisis_resources"]) > 0
            assert "109" in [r["tel"] for r in data["crisis_resources"]]
            assert data["credit_delta"] == 0
            assert data["remaining_credits"] == 0
