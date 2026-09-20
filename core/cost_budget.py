# -*- coding: utf-8 -*-
"""AI 호출 런타임 비용 상한 및 예산 추적 모듈 (A02-R1 영속화 보정판).

- PostgreSQL(llm_cost_usage 테이블)을 단일 진실 공급원(Single Source of Truth)으로 사용
- Cloud Run scale-to-zero 콜드 스타트 및 다중 인스턴스 환경에서도 예산 누적 보존
- 원자적 DB 누적(INSERT ... ON CONFLICT DO UPDATE)을 통한 경합 안전성 확보
- 읽기 캐시 TTL 10초 적용으로 DB 오버헤드 최소화 (쓰기는 캐시 없이 상시 DB 기록)
- DB 접근 불가 시 fail-closed 차단 (503 BUDGET_UNVERIFIABLE)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from threading import Lock
import time
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

from core.config import settings

logger = logging.getLogger(__name__)


class CostBudgetExceededError(Exception):
    """일일 또는 월간 AI 비용 예산 한도 초과 예외."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        budget_limit: float,
        period: str = "daily",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.current_cost = current_cost
        self.budget_limit = budget_limit
        self.period = period


class BudgetUnverifiableError(Exception):
    """DB 장애 등으로 예산 상태를 검증할 수 없을 때 발생하는 fail-closed 예외."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or message


# 1M 토큰당 가격 (USD 기준, 2026년 기준가)
# (input_price_per_1m, output_price_per_1m)
MODEL_TOKEN_PRICING: Dict[str, Tuple[float, float]] = {
    # Gemini 2.5 Flash
    "gemini-2.5-flash-lite": (0.05, 0.20),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    # Anthropic Claude
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    # 로컬 모델 (비용 0)
    "ollama": (0.0, 0.0),
    "lmstudio": (0.0, 0.0),
    "gemma4:latest": (0.0, 0.0),
}

DEFAULT_TOKEN_PRICING: Tuple[float, float] = (0.50, 2.00)


def calculate_token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """모델명과 토큰 수에 기반한 추정 비용(USD)을 계산합니다.

    R1-D: 키 길이 내림차순으로 매칭하여 하위 모델명이 상위 모델명에 잘못 매칭되지 않도록 합니다.
    """
    model_lower = (model or "").lower()
    pricing = None

    # 키 길이 내림차순 정렬 매칭
    sorted_keys = sorted(MODEL_TOKEN_PRICING.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in model_lower:
            pricing = MODEL_TOKEN_PRICING[key]
            break

    if pricing is None:
        pricing = DEFAULT_TOKEN_PRICING

    input_cost = (input_tokens / 1_000_000.0) * pricing[0]
    output_cost = (output_tokens / 1_000_000.0) * pricing[1]
    return round(input_cost + output_cost, 6)


def _get_async_session():
    """비동기 DB 세션을 생성합니다."""
    from core.db import AsyncSessionLocal

    return AsyncSessionLocal()


class CostBudgetTracker:
    """PostgreSQL 기반 영속 런타임 비용 상한 추적기 (읽기 캐시 TTL 10초)."""

    CACHE_TTL_SECONDS: float = 10.0

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_cache_time: float = 0.0
        self._cached_date: str = ""
        self._cached_month: str = ""
        self._cached_daily_cost: float = 0.0
        self._cached_daily_calls: int = 0
        self._cached_monthly_cost: float = 0.0
        self._cached_monthly_calls: int = 0

    def _get_utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _invalidate_cache(self) -> None:
        with self._lock:
            self._last_cache_time = 0.0

    async def _fetch_usage_from_db(self, date_key: str, month_key: str) -> Tuple[float, int, float, int]:
        """DB에서 일일/월간 누적 비용과 호출 수를 조회합니다."""
        sql = text(
            """
            SELECT period_kind, cost_usd, call_count
            FROM public.llm_cost_usage
            WHERE (period_kind = 'daily' AND period_key = :date_key)
               OR (period_kind = 'monthly' AND period_key = :month_key)
            """
        )
        try:
            async with _get_async_session() as session:
                result = await session.execute(sql, {"date_key": date_key, "month_key": month_key})
                rows = result.fetchall()

            daily_cost, daily_calls = 0.0, 0
            monthly_cost, monthly_calls = 0.0, 0

            for kind, cost, count in rows:
                if kind == "daily":
                    daily_cost = float(cost or 0.0)
                    daily_calls = int(count or 0)
                elif kind == "monthly":
                    monthly_cost = float(cost or 0.0)
                    monthly_calls = int(count or 0)

            return daily_cost, daily_calls, monthly_cost, monthly_calls
        except Exception as e:
            logger.error("A02 DB 예산 조회 실패 (fail-closed 차단 발동): %s", e)
            raise BudgetUnverifiableError("예산 상태를 확인할 수 없습니다.", detail=str(e)) from e

    async def get_current_usage_async(self) -> Tuple[float, int, float, int, str, str]:
        """읽기 캐시를 참조하거나 만료 시 DB에서 최신 사용량을 가져옵니다."""
        now = self._get_utc_now()
        date_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")
        now_ts = time.time()

        with self._lock:
            if (
                (now_ts - self._last_cache_time) < self.CACHE_TTL_SECONDS
                and self._cached_date == date_key
                and self._cached_month == month_key
            ):
                return (
                    self._cached_daily_cost,
                    self._cached_daily_calls,
                    self._cached_monthly_cost,
                    self._cached_monthly_calls,
                    date_key,
                    month_key,
                )

        daily_cost, daily_calls, monthly_cost, monthly_calls = await self._fetch_usage_from_db(date_key, month_key)

        with self._lock:
            self._cached_date = date_key
            self._cached_month = month_key
            self._cached_daily_cost = daily_cost
            self._cached_daily_calls = daily_calls
            self._cached_monthly_cost = monthly_cost
            self._cached_monthly_calls = monthly_calls
            self._last_cache_time = now_ts

        return daily_cost, daily_calls, monthly_cost, monthly_calls, date_key, month_key

    async def check_budget_available_async(self, estimated_cost: float = 0.0) -> None:
        """비동기 DB/캐시 기반 예산 한도 검사.

        R1-C:
        - LLM_BUDGET_ENABLED=False일 때만 무제한 통과.
        - 한도가 0이면 0달러 한도(전면 차단).
        - 초과 시 CostBudgetExceededError(503) 발생.
        """
        if not getattr(settings, "LLM_BUDGET_ENABLED", True):
            return

        daily_cost, _, monthly_cost, _, _, _ = await self.get_current_usage_async()

        daily_limit = float(getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 10.0))
        if (daily_cost + estimated_cost) >= daily_limit:
            logger.warning(
                "A02 일일 LLM 비용 상한 초과: 현재 $%.4f + 예상 $%.4f >= 한도 $%.2f",
                daily_cost,
                estimated_cost,
                daily_limit,
            )
            raise CostBudgetExceededError(
                "AI 호출 비용 예산 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
                current_cost=daily_cost,
                budget_limit=daily_limit,
                period="daily",
            )

        monthly_limit = float(getattr(settings, "LLM_MONTHLY_COST_BUDGET_USD", 100.0))
        if (monthly_cost + estimated_cost) >= monthly_limit:
            logger.warning(
                "A02 월간 LLM 비용 상한 초과: 현재 $%.4f + 예상 $%.4f >= 한도 $%.2f",
                monthly_cost,
                estimated_cost,
                monthly_limit,
            )
            raise CostBudgetExceededError(
                "AI 호출 비용 예산 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
                current_cost=monthly_cost,
                budget_limit=monthly_limit,
                period="monthly",
            )

    def check_budget_available(self, estimated_cost: float = 0.0) -> None:
        """동기 인터페이스 (core/llm.py 클라이언트 내부용).

        캐시된 값을 우선 검사하며, 캐시가 만료된 경우 비동기 루프에서 실행합니다.
        """
        if not getattr(settings, "LLM_BUDGET_ENABLED", True):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 이미 실행 중인 이벤트 루프 안이면 현재 캐시 기반으로 빠른 검사 수행
            with self._lock:
                daily_cost = self._cached_daily_cost
                monthly_cost = self._cached_monthly_cost
                daily_limit = float(getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 10.0))
                monthly_limit = float(getattr(settings, "LLM_MONTHLY_COST_BUDGET_USD", 100.0))

                if (daily_cost + estimated_cost) >= daily_limit:
                    logger.warning("A02 일일 비용 상한 초과 (동기 캐시 체크): $%.4f >= $%.2f", daily_cost, daily_limit)
                    raise CostBudgetExceededError(
                        "AI 호출 비용 예산 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
                        current_cost=daily_cost,
                        budget_limit=daily_limit,
                        period="daily",
                    )
                if (monthly_cost + estimated_cost) >= monthly_limit:
                    logger.warning("A02 월간 비용 상한 초과 (동기 캐시 체크): $%.4f >= $%.2f", monthly_cost, monthly_limit)
                    raise CostBudgetExceededError(
                        "AI 호출 비용 예산 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
                        current_cost=monthly_cost,
                        budget_limit=monthly_limit,
                        period="monthly",
                    )
        else:
            asyncio.run(self.check_budget_available_async(estimated_cost))

    async def record_usage_async(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider: Optional[str] = None,
    ) -> float:
        """원자적 DB UPSERT로 사용량을 누적합니다 (쓰기는 절대 캐시하지 않음)."""
        if provider in ("ollama", "lmstudio"):
            cost = 0.0
        else:
            cost = calculate_token_cost(model, input_tokens, output_tokens)

        now = self._get_utc_now()
        date_key = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")

        sql = text(
            """
            INSERT INTO public.llm_cost_usage (period_kind, period_key, cost_usd, call_count, updated_at)
            VALUES (:kind, :key, :cost, 1, now())
            ON CONFLICT (period_kind, period_key) DO UPDATE
              SET cost_usd = public.llm_cost_usage.cost_usd + EXCLUDED.cost_usd,
                  call_count = public.llm_cost_usage.call_count + 1,
                  updated_at = now()
            RETURNING cost_usd, call_count
            """
        )

        try:
            async with _get_async_session() as session:
                daily_res = await session.execute(sql, {"kind": "daily", "key": date_key, "cost": cost})
                daily_row = daily_res.fetchone()
                monthly_res = await session.execute(sql, {"kind": "monthly", "key": month_key, "cost": cost})
                monthly_row = monthly_res.fetchone()
                await session.commit()

            with self._lock:
                if daily_row:
                    self._cached_daily_cost = float(daily_row[0])
                    self._cached_daily_calls = int(daily_row[1])
                if monthly_row:
                    self._cached_monthly_cost = float(monthly_row[0])
                    self._cached_monthly_calls = int(monthly_row[1])
                self._cached_date = date_key
                self._cached_month = month_key
                self._last_cache_time = time.time()

            logger.debug(
                "A02 LLM 사용량 영속화 성공: 모델=%s, 비용=$%.6f, 일일누적=$%.4f",
                model,
                cost,
                self._cached_daily_cost,
            )
        except Exception as e:
            logger.error("A02 LLM 사용량 DB 기록 실패: %s", e)
            # 쓰기 실패 시에도 인메모리 캐시는 최선을 다해 가산
            with self._lock:
                self._cached_daily_cost = round(self._cached_daily_cost + cost, 6)
                self._cached_daily_calls += 1
                self._cached_monthly_cost = round(self._cached_monthly_cost + cost, 6)
                self._cached_monthly_calls += 1

        return cost

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        provider: Optional[str] = None,
    ) -> float:
        """동기 호출 래퍼."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 실행 중인 루프가 있으면 백그라운드 태스크로 즉시 예약
            asyncio.create_task(self.record_usage_async(model, input_tokens, output_tokens, provider))
            if provider in ("ollama", "lmstudio"):
                return 0.0
            return calculate_token_cost(model, input_tokens, output_tokens)
        else:
            return asyncio.run(self.record_usage_async(model, input_tokens, output_tokens, provider))

    async def get_status_async(self) -> Dict[str, Any]:
        """운영자용 상태 조회 비동기 메서드."""
        daily_cost, daily_calls, monthly_cost, monthly_calls, date_key, month_key = await self.get_current_usage_async()
        daily_limit = float(getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 10.0))
        monthly_limit = float(getattr(settings, "LLM_MONTHLY_COST_BUDGET_USD", 100.0))

        return {
            "date": date_key,
            "month": month_key,
            "daily_cost_usd": daily_cost,
            "daily_limit_usd": daily_limit,
            "daily_calls": daily_calls,
            "monthly_cost_usd": monthly_cost,
            "monthly_limit_usd": monthly_limit,
            "monthly_calls": monthly_calls,
            "budget_enabled": getattr(settings, "LLM_BUDGET_ENABLED", True),
        }

    def reset_for_test(
        self,
        daily_cost: float = 0.0,
        monthly_cost: float = 0.0,
        daily_calls: int = 0,
        monthly_calls: int = 0,
    ) -> None:
        """테스트 전용: 캐시 상태 즉시 주입."""
        with self._lock:
            now = self._get_utc_now()
            self._cached_date = now.strftime("%Y-%m-%d")
            self._cached_month = now.strftime("%Y-%m")
            self._cached_daily_cost = daily_cost
            self._cached_monthly_cost = monthly_cost
            self._cached_daily_calls = daily_calls
            self._cached_monthly_calls = monthly_calls
            self._last_cache_time = time.time() + 3600.0  # 테스트 중 캐시 유지


# 싱글톤 전역 인스턴스
budget_tracker = CostBudgetTracker()
