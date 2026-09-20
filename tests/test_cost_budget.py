# -*- coding: utf-8 -*-
"""A02-R1 런타임 AI 비용 상한 영속화 및 예산 쿼터 단위/반증 테스트."""

import pytest
from core.config import settings
from core.cost_budget import (
    BudgetUnverifiableError,
    CostBudgetExceededError,
    CostBudgetTracker,
    calculate_token_cost,
)
from core.release_gate import check_config_consistency


def test_calculate_token_cost_precedence():
    # R1-D: 긴 모델명이 먼저 매칭되어야 함 (gemini-2.5-flash-lite vs gemini-2.5-flash)
    cost_lite = calculate_token_cost("gemini-2.5-flash-lite", 1_000_000, 1_000_000)
    assert cost_lite == pytest.approx(0.25, rel=1e-3)

    cost_flash = calculate_token_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert cost_flash == pytest.approx(0.375, rel=1e-3)

    # 로컬 모델: 비용 0
    assert calculate_token_cost("ollama", 5000, 1000) == 0.0
    assert calculate_token_cost("gemma4:latest", 5000, 1000) == 0.0


def test_budget_tracker_daily_limit_exceeded(monkeypatch):
    tracker = CostBudgetTracker()
    monkeypatch.setattr(settings, "LLM_BUDGET_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_DAILY_COST_BUDGET_USD", 5.0)
    monkeypatch.setattr(settings, "LLM_MONTHLY_COST_BUDGET_USD", 100.0)

    tracker.reset_for_test(daily_cost=4.99)
    tracker.check_budget_available()

    tracker.reset_for_test(daily_cost=5.00)
    with pytest.raises(CostBudgetExceededError) as exc_info:
        tracker.check_budget_available()
    assert exc_info.value.period == "daily"


def test_budget_tracker_zero_limit_blocks_all(monkeypatch):
    # R1-C: 0은 무제한이 아니라 0달러 한도(전면 차단)
    tracker = CostBudgetTracker()
    monkeypatch.setattr(settings, "LLM_BUDGET_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_DAILY_COST_BUDGET_USD", 0.0)

    tracker.reset_for_test(daily_cost=0.0)
    with pytest.raises(CostBudgetExceededError) as exc_info:
        tracker.check_budget_available()
    assert exc_info.value.period == "daily"


def test_budget_tracker_disabled(monkeypatch):
    tracker = CostBudgetTracker()
    monkeypatch.setattr(settings, "LLM_BUDGET_ENABLED", False)
    monkeypatch.setattr(settings, "LLM_DAILY_COST_BUDGET_USD", 0.0)

    tracker.reset_for_test(daily_cost=999.0)
    # LLM_BUDGET_ENABLED=False일 때만 무제한 통과
    tracker.check_budget_available()


def test_negative_budget_consistency(monkeypatch):
    # R1-C: 음수 한도는 release_gate에서 모순 감지
    monkeypatch.setattr(settings, "LLM_BUDGET_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_DAILY_COST_BUDGET_USD", -1.0)
    problems = check_config_consistency(settings)
    assert any("음수" in p for p in problems)


@pytest.mark.asyncio
async def test_budget_unverifiable_fail_closed(monkeypatch):
    # A02-5: DB 조회 불가 시 fail-closed
    tracker = CostBudgetTracker()
    monkeypatch.setattr(settings, "LLM_BUDGET_ENABLED", True)

    async def fail_fetch(*args, **kwargs):
        raise BudgetUnverifiableError("DB connection dropped")

    monkeypatch.setattr(tracker, "_fetch_usage_from_db", fail_fetch)
    tracker._invalidate_cache()

    with pytest.raises(BudgetUnverifiableError):
        await tracker.check_budget_available_async()
