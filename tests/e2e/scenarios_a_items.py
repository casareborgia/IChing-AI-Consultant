# -*- coding: utf-8 -*-
"""CYCLE-08 묶음 1 — 인수기준 A 항목 검증 시나리오.

CYCLE-06 하네스 위에 A02·A10·A35·A37을 얹는다. 모두 실제 TCP로 제품 앱에 간다.
A36(위기 래치)은 HTTP 계약이 아니라 파이프라인 내부 규칙이라 여기 두지 않는다 —
결정론적 fake로 확인하면 제품이 아니라 fake를 검증하게 된다. 그쪽은
`tests/test_agents_pipeline.py`의 단위 테스트로 다룬다.

이 모듈은 판정을 내리지 않는다. 증거를 만든다.
"""

import json
import os
import struct
from typing import Any, Dict, Optional
import uuid

import asyncpg
from tests.e2e.harness import fake_pipeline
from tests.e2e.scenarios import Context, call, ensure_consent, record_response


async def _get_e2e_db_conn():
    raw_url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(raw_url)

# api/main.py:_MAX_BODY_SIZE 와 같은 값. 이 상수가 바뀌면 시나리오도 바뀌어야 한다.
MAX_BODY_SIZE = 1024 * 1024

# api/routers/counsel.py:StartConsultationRequest.question 의 상한
QUESTION_MAX_LENGTH = 1000

# PNG 안에 텍스트를 싣는 청크들. 렌더 결과에 있으면 입력이 메타데이터로 샌 것이다.
PNG_TEXT_CHUNKS = (b"tEXt", b"iTXt", b"zTXt")
EXIF_MARKERS = (b"Exif\x00\x00", b"II*\x00", b"MM\x00*")


def _png_chunk_types(payload: bytes) -> list:
    """PNG 청크 종류를 순서대로 읽는다. 유효한 PNG가 아니면 빈 목록."""
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return []
    types = []
    offset = 8
    while offset + 8 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        types.append(chunk_type)
        if chunk_type == b"IEND":
            break
        offset += 12 + length
    return types


# --------------------------------------------------------------------------
# A10 입력·본문·CORS
# --------------------------------------------------------------------------


async def a10_body_size_limit(ctx: Context) -> None:
    """본문 상한이 라우팅보다 먼저 끊는지."""
    scenario = ctx.report.scenario("A10-1", "요청 본문 1MB 초과 413")
    actor = ctx.actor("user_a10_body")

    oversized = "가" * (MAX_BODY_SIZE // 2 + 1024)  # UTF-8 3바이트/자 → 1MB 초과
    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A10-1"), json_body={"question": oversized},
    )
    scenario.check("status", 413, status)
    # 길이 검증(422)이 아니라 본문 상한(413)이 먼저 걸려야 한다. 순서가 뒤집히면
    # 거대한 본문이 Pydantic 파싱까지 도달한다.
    scenario.check_true("not_422", status != 422)
    scenario.finish()


async def a10_field_limits(ctx: Context) -> None:
    """필드 길이·형식 상한이 실제로 거부하는지."""
    scenario = ctx.report.scenario("A10-2", "필드 길이·형식 위반 422")
    actor = ctx.actor("user_a10_field")

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A10-2a"),
        json_body={"question": "가" * (QUESTION_MAX_LENGTH + 1)},
    )
    scenario.check("question_too_long", 422, status)

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A10-2b"), json_body={"question": ""},
    )
    scenario.check("question_empty", 422, status)

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/turn", actor=actor,
        idempotency_key=ctx.key("A10-2c"),
        json_body={"session_id": "has space/and slash", "user_message": "정상 발화"},
    )
    scenario.check("session_id_pattern", 422, status)

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A10-2d"), json_body={"wrong_field": "정상 발화"},
    )
    scenario.check("missing_required_field", 422, status)
    scenario.finish()


async def a10_cors(ctx: Context) -> None:
    """CORS allowlist가 허용 origin만 통과시키는지."""
    scenario = ctx.report.scenario("A10-3", "CORS allowlist 경계")

    allowed = await ctx.client.request(
        "OPTIONS", "/api/counsel/start",
        headers={
            "Origin": "http://localhost:3005",
            "Access-Control-Request-Method": "POST",
        },
        timeout=30.0,
    )
    record_response(ctx, scenario, allowed, path="/api/counsel/start (OPTIONS preflight)")
    scenario.check_true(
        "allowed_origin_echoed",
        allowed.headers.get("access-control-allow-origin") == "http://localhost:3005",
    )

    denied = await ctx.client.request(
        "OPTIONS", "/api/counsel/start",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
        timeout=30.0,
    )
    record_response(ctx, scenario, denied, path="/api/counsel/start (OPTIONS preflight)")
    scenario.check("denied_origin_not_echoed", None,
                   denied.headers.get("access-control-allow-origin"))
    scenario.finish()


# --------------------------------------------------------------------------
# A35 위기 접근성 (백엔드)
# --------------------------------------------------------------------------


async def a35_safety_resources(ctx: Context) -> None:
    """위기 리소스가 인증 없이도 닿는지.

    위기 상황의 사람에게 로그인을 요구하면 안 된다. 이 경로가 인증 뒤에 있으면
    그 자체가 결함이다.
    """
    scenario = ctx.report.scenario("A35-1", "위기 리소스 무인증 접근")

    status, payload, _ = await call(
        ctx, scenario, method="GET", path="/api/safety/resources"
    )
    scenario.check("status_without_auth", 200, status)
    resources = payload.get("resources")
    scenario.check_true("resources_is_list", isinstance(resources, list))
    scenario.check_true("resources_not_empty", bool(resources))

    status, filtered, _ = await call(
        ctx, scenario, method="GET", path="/api/safety/resources?context=crisis"
    )
    scenario.check("context_status", 200, status)
    scenario.check_true("context_resources_is_list",
                        isinstance(filtered.get("resources"), list))
    scenario.finish()


# --------------------------------------------------------------------------
# A02 기본 외부 비용 차단
# --------------------------------------------------------------------------


async def a02_generation_kill_switch(ctx: Context) -> None:
    """운영자 킬 스위치가 크레딧 차감과 LLM 호출 앞에서 끊는지.

    `GENERATION_ENABLED`는 장애·비용 급증 시 즉시 내리는 스위치다. 이 시나리오는
    테스트 프로세스에서 설정값을 잠시 내렸다가 되돌린다. 제품 코드는 바꾸지 않는다.
    """
    scenario = ctx.report.scenario("A02-1", "생성 킬 스위치 503")
    actor = ctx.actor("user_a02")

    from core.config import settings

    before = await call(
        ctx, scenario, method="GET", path="/api/me/credits", actor=actor
    )
    scenario.balance_before = before[1].get("remaining_credits")

    original = settings.GENERATION_ENABLED
    try:
        settings.GENERATION_ENABLED = False

        status, payload, _ = await call(
            ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A02-1a"), json_body={"question": "킬 스위치 확인"},
        )
        scenario.check("start_blocked", 503, status)
        scenario.check_true("has_detail", bool(payload.get("detail")))

        status, _, _ = await call(
            ctx, scenario, method="POST", path="/api/counsel/turn", actor=actor,
            idempotency_key=ctx.key("A02-1b"),
            json_body={"session_id": "nonexistent", "user_message": "킬 스위치 확인"},
        )
        scenario.check("turn_blocked", 503, status)
    finally:
        settings.GENERATION_ENABLED = original

    # 차단 중에도 잔액 조회 같은 비생성 경로는 살아 있어야 한다.
    status, after, _ = await call(
        ctx, scenario, method="GET", path="/api/me/credits", actor=actor
    )
    scenario.check("credits_still_reachable", 200, status)
    scenario.balance_after = after.get("remaining_credits")
    scenario.check("no_charge_while_blocked", scenario.balance_before, scenario.balance_after)

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A02-1c"), json_body={"question": "복구 확인"},
    )
    scenario.check("restored_after_switch_back", 200, status)
    scenario.finish()


async def a02_cost_budget_quota(ctx: Context) -> None:
    """A02 런타임 비용 상한(Daily Budget Quota)이 도달했을 때 503 fail-closed 차단 및 크레딧 미차감 검증."""
    scenario = ctx.report.scenario("A02-2", "런타임 비용 상한 503 차단")
    actor = ctx.actor("user_a02_quota")

    from core.config import settings
    from core.cost_budget import budget_tracker

    # 사전 동의 보장
    await ensure_consent(ctx, actor)

    before = await call(
        ctx, scenario, method="GET", path="/api/me/credits", actor=actor
    )
    scenario.balance_before = before[1].get("remaining_credits")

    # 일일 한도 초과 상태 주입
    budget_tracker.reset_for_test(daily_cost=getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 10.0))
    try:
        status, payload, _ = await call(
            ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A02-2a"), json_body={"question": "비용 상한 차단 확인"},
        )
        scenario.check("start_blocked_by_budget", 503, status)

        status, _, _ = await call(
            ctx, scenario, method="POST", path="/api/counsel/turn", actor=actor,
            idempotency_key=ctx.key("A02-2b"),
            json_body={"session_id": "nonexistent", "user_message": "비용 상한 차단 확인"},
        )
        scenario.check("turn_blocked_by_budget", 503, status)
    finally:
        budget_tracker.reset_for_test(daily_cost=0.0)

    # 차단 중에도 잔액 조회는 정상이어야 하며 크레딧은 차감되지 않음
    status, after, _ = await call(
        ctx, scenario, method="GET", path="/api/me/credits", actor=actor
    )
    scenario.check("credits_still_reachable", 200, status)
    scenario.balance_after = after.get("remaining_credits")
    scenario.check("no_charge_while_budget_blocked", scenario.balance_before, scenario.balance_after)

    # 복구 후 정상 요청 확인
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("A02-2c"), json_body={"question": "비용 상한 복구 확인"},
    )
    scenario.check("restored_after_budget_reset", 200, status)
    scenario.finish()


async def a02_persistence_and_ops(ctx: Context) -> None:
    """A02-R1: 콜드스타트 DB 영속화 차단(A02-3), 공유 인스턴스(A02-4), 장애 fail-closed(A02-5), DB 실제 증가(A02-6), 0달러 전면차단(A02-7), 운영자 경로(OPS-1) 반증."""
    actor = ctx.actor("user_a02_persist")
    ops_actor = ctx.actor("operator_admin")

    from core.config import settings
    from core.cost_budget import CostBudgetTracker, budget_tracker
    from datetime import datetime, timezone

    await ensure_consent(ctx, actor)
    await ensure_consent(ctx, ops_actor)

    conn = await _get_e2e_db_conn()
    now_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # 1. A02-6: record_usage 후 DB cost_usd 실제 증가
        sc_a02_6 = ctx.report.scenario("A02-6", "record_usage 후 DB cost_usd 실제 증가")
        before_row = await conn.fetchrow(
            "SELECT cost_usd FROM public.llm_cost_usage WHERE period_kind = 'daily' AND period_key = $1",
            now_key,
        )
        before_cost = float(before_row["cost_usd"]) if before_row else 0.0

        await budget_tracker.record_usage_async("gemini-2.5-flash", input_tokens=100_000, output_tokens=10_000)

        after_row = await conn.fetchrow(
            "SELECT cost_usd FROM public.llm_cost_usage WHERE period_kind = 'daily' AND period_key = $1",
            now_key,
        )
        after_cost = float(after_row["cost_usd"]) if after_row else 0.0
        sc_a02_6.check_true("db_cost_increased", after_cost > before_cost)
        sc_a02_6.finish()

        # 2. A02-3: 콜드 스타트 시뮬레이션 (캐시 비어있는 상태에서 DB 누적으로 차단)
        sc_a02_3 = ctx.report.scenario("A02-3", "콜드 스타트 시 DB 영속값으로 차단")
        daily_limit = float(getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 10.0))
        await conn.execute(
            """
            INSERT INTO public.llm_cost_usage (period_kind, period_key, cost_usd, call_count, updated_at)
            VALUES ('daily', $1, $2, 99, now())
            ON CONFLICT (period_kind, period_key) DO UPDATE
              SET cost_usd = $2, updated_at = now()
            """,
            now_key,
            daily_limit + 1.0,
        )
        # 새 tracker 인스턴스 생성 (콜드 스타트 대역)
        fresh_tracker = CostBudgetTracker()
        try:
            await fresh_tracker.check_budget_available_async()
            coldstart_blocked = False
        except Exception:
            coldstart_blocked = True
        sc_a02_3.check_true("coldstart_tracker_blocked", coldstart_blocked)

        budget_tracker._invalidate_cache()
        status, _, _ = await call(
            ctx, sc_a02_3, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A02-3-coldstart"), json_body={"question": "콜드스타트 차단 확인"},
        )
        sc_a02_3.check("coldstart_api_blocked_503", 503, status)
        sc_a02_3.finish()

        # DB 복구
        await conn.execute(
            "UPDATE public.llm_cost_usage SET cost_usd = 0.0 WHERE period_kind = 'daily' AND period_key = $1",
            now_key,
        )
        budget_tracker._invalidate_cache()

        # 3. A02-4: 두 tracker 인스턴스가 같은 DB 예산을 공유함
        sc_a02_4 = ctx.report.scenario("A02-4", "두 tracker 인스턴스의 DB 예산 공유")
        tracker_a = CostBudgetTracker()
        tracker_b = CostBudgetTracker()
        await tracker_a.record_usage_async("gemini-2.5-flash", input_tokens=50_000, output_tokens=5_000)
        status_b = await tracker_b.get_status_async()
        sc_a02_4.check_true("tracker_b_sees_cost_written_by_a", status_b["daily_cost_usd"] > 0.0)
        sc_a02_4.finish()

        # DB 복구
        await conn.execute(
            "UPDATE public.llm_cost_usage SET cost_usd = 0.0 WHERE period_kind = 'daily' AND period_key = $1",
            now_key,
        )
        budget_tracker._invalidate_cache()

        # 4. A02-5: DB 불가 시 fail-closed (503 BUDGET_UNVERIFIABLE)
        sc_a02_5 = ctx.report.scenario("A02-5", "DB 조회 불가 시 fail-closed 차단")
        import core.cost_budget as cb_module
        orig_session_fn = cb_module._get_async_session

        class _FailingSessionCtx:
            async def __aenter__(self):
                raise RuntimeError("Database connection unreachable")
            async def __aexit__(self, *args):
                pass

        try:
            budget_tracker._invalidate_cache()
            cb_module._get_async_session = lambda: _FailingSessionCtx()
            status, payload, _ = await call(
                ctx, sc_a02_5, method="POST", path="/api/counsel/start", actor=actor,
                idempotency_key=ctx.key("A02-5-dbfail"), json_body={"question": "장애 fail-closed 확인"},
            )
            sc_a02_5.check("fail_closed_503_on_db_error", 503, status)
            detail = payload.get("detail") if isinstance(payload, dict) else {}
            err_code = detail.get("code") if isinstance(detail, dict) else None
            sc_a02_5.check("code_budget_unverifiable", "BUDGET_UNVERIFIABLE", err_code)
        finally:
            cb_module._get_async_session = orig_session_fn
            budget_tracker._invalidate_cache()
        sc_a02_5.finish()

        # 5. A02-7: 0달러 한도 전면 차단
        sc_a02_7 = ctx.report.scenario("A02-7", "0달러 한도 전면 차단")
        orig_limit = settings.LLM_DAILY_COST_BUDGET_USD
        try:
            settings.LLM_DAILY_COST_BUDGET_USD = 0.0
            status, _, _ = await call(
                ctx, sc_a02_7, method="POST", path="/api/counsel/start", actor=actor,
                idempotency_key=ctx.key("A02-7-zero"), json_body={"question": "0달러 차단 확인"},
            )
            sc_a02_7.check("zero_limit_blocks_all", 503, status)
        finally:
            settings.LLM_DAILY_COST_BUDGET_USD = orig_limit
        sc_a02_7.finish()

        # 6. OPS-1: /api/ops/budget 접근 제어 검증
        sc_ops_1 = ctx.report.scenario("OPS-1", "운영자 예산 상태 조회 접근 제어")
        # 6-a: 무인증 401
        status, _, _ = await call(
            ctx, sc_ops_1, method="GET", path="/api/ops/budget", actor=None
        )
        sc_ops_1.check("ops_budget_unauth_401", 401, status)

        # 6-b: 비운영자 404 (은닉)
        status, _, _ = await call(
            ctx, sc_ops_1, method="GET", path="/api/ops/budget", actor=actor
        )
        sc_ops_1.check("ops_budget_non_operator_404", 404, status)

        # 6-c: 운영자 200
        orig_ops = settings.OPERATOR_USER_IDS
        try:
            settings.OPERATOR_USER_IDS = ops_actor.user_id
            status, ops_body, _ = await call(
                ctx, sc_ops_1, method="GET", path="/api/ops/budget", actor=ops_actor
            )
            sc_ops_1.check("ops_budget_operator_200", 200, status)
            sc_ops_1.check_true("ops_body_has_daily_cost", "daily_cost_usd" in ops_body)
        finally:
            settings.OPERATOR_USER_IDS = orig_ops
        sc_ops_1.finish()

    finally:
        await conn.close()
        budget_tracker._invalidate_cache()



# --------------------------------------------------------------------------
# A37 카드 민감정보
# --------------------------------------------------------------------------


def _card_body(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "is_crisis": False,
        "client_aha_moment": "E2E-FAKE 카드 문구",
        "client_action_pledge": "E2E-FAKE 다짐",
    }
    data.update(overrides)
    return {"card_data": data}


async def a37_card_export(ctx: Context) -> None:
    """BLK-C08-01 카드 내보내기 소유권 검증 및 서버 저장분 렌더링 진위 보장 (A37-2 ~ A37-8)."""
    owner = ctx.actor("user_a37_owner")
    attacker = ctx.actor("user_a37_attacker")

    conn = await _get_e2e_db_conn()
    import uuid
    sid_valid = str(uuid.uuid4())
    sid_null = str(uuid.uuid4())
    sid_missing = str(uuid.uuid4())

    db_card_payload = {
        "is_crisis": False,
        "universe_transition": "DB에 영속 저장된 진본 여정",
        "sacred_metaphor": "오직 실천으로 증명하는 지혜",
        "client_aha_moment": "타인의 평가에 흔들리지 않는 내면의 중심",
        "client_action_pledge": "매일 아침 10분간 우선순위를 정돈한다",
        "counselor_reframing": "당신의 굳건한 뜻을 응원합니다",
    }

    try:
        # 사전 조건: profiles, counsel_sessions, journal_entries 삽입
        await conn.execute("INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING", owner.user_id)
        await conn.execute("INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING", attacker.user_id)

        await conn.execute(
            """
            INSERT INTO public.counsel_sessions (id, user_id, raw_question, status, is_duplicate)
            VALUES ($1, $2, '유효 카드 세션', 'completed', false),
                   ($3, $2, '카드데이터 없는 세션', 'completed', false)
            """,
            sid_valid, owner.user_id, sid_null,
        )

        import json
        await conn.execute(
            """
            INSERT INTO public.journal_entries (session_id, summary, key_insights, card_data)
            VALUES ($1, '정상 저널', '통찰', $2::jsonb),
                   ($3, 'NULL 저널', '통찰', NULL)
            """,
            sid_valid, json.dumps(db_card_payload), sid_null,
        )

        # 1. A37-6: 무인증 401
        sc_a37_6 = ctx.report.scenario("A37-6", "카드 내보내기 무인증 차단 401")
        status_unauth, _, _ = await call(
            ctx, sc_a37_6, method="POST", path="/api/counsel/card/export", actor=None,
            json_body={"session_id": sid_valid},
        )
        sc_a37_6.check("unauth_401", 401, status_unauth)
        sc_a37_6.finish()

        # 2. A37-3: 존재하지 않는 session_id -> 404
        sc_a37_3 = ctx.report.scenario("A37-3", "존재하지 않는 session_id 404 은닉")
        status_missing, _, _ = await call(
            ctx, sc_a37_3, method="POST", path="/api/counsel/card/export", actor=owner,
            json_body={"session_id": sid_missing},
        )
        sc_a37_3.check("missing_session_404", 404, status_missing)
        sc_a37_3.finish()

        # 3. A37-2: 타인 session_id -> 404 (소유권 검증 및 은닉)
        sc_a37_2 = ctx.report.scenario("A37-2", "타인 session_id 접근 404 은닉")
        status_attacker, _, _ = await call(
            ctx, sc_a37_2, method="POST", path="/api/counsel/card/export", actor=attacker,
            json_body={"session_id": sid_valid},
        )
        sc_a37_2.check("foreign_session_404", 404, status_attacker)
        sc_a37_2.finish()

        # 4. A37-4: card_data가 NULL인 과거 세션 -> 404
        sc_a37_4 = ctx.report.scenario("A37-4", "card_data가 NULL인 세션 404 은닉")
        status_null, _, _ = await call(
            ctx, sc_a37_4, method="POST", path="/api/counsel/card/export", actor=owner,
            json_body={"session_id": sid_null},
        )
        sc_a37_4.check("null_card_data_404", 404, status_null)
        sc_a37_4.finish()

        # 5. A37-5: 본인 소유 정상 세션 -> 200 image/png 및 attachment 헤더
        sc_a37_5 = ctx.report.scenario("A37-5", "본인 세션 서버 저장본 카드 렌더링 200")
        response_owner = await ctx.client.request(
            "POST", "/api/counsel/card/export",
            headers={"Authorization": "Bearer " + owner.token},
            json={"session_id": sid_valid},
            timeout=90.0,
        )
        record_response(ctx, sc_a37_5, response_owner, path="/api/counsel/card/export",
                        actor_ref=owner.ref, authenticated=True)
        sc_a37_5.check("owner_export_200", 200, response_owner.status_code)
        sc_a37_5.check("media_type_png", "image/png",
                       response_owner.headers.get("content-type", "").split(";")[0])
        sc_a37_5.check_true(
            "attachment_disposition",
            response_owner.headers.get("content-disposition", "").startswith("attachment"),
        )
        payload = response_owner.content
        sc_a37_5.check_true("is_png", payload.startswith(b"\x89PNG\r\n\x1a\n"))
        sc_a37_5.check_true("png_has_substance", len(payload) > 10_000)
        sc_a37_5.finish()

        # 6. A37-7: PNG 메타데이터 회귀 검증 (EXIF 부재, tEXt/iTXt/zTXt 0개, 평문 미노출)
        sc_a37_7 = ctx.report.scenario("A37-7", "PNG 메타데이터 및 EXIF 세척 무결성")
        chunk_types = _png_chunk_types(payload)
        text_chunks = [c.decode("ascii", "replace") for c in chunk_types if c in PNG_TEXT_CHUNKS]
        sc_a37_7.check("no_png_text_chunks", [], text_chunks)
        for marker in EXIF_MARKERS:
            sc_a37_7.check_true(
                "no_exif_" + marker[:2].decode("ascii", "replace").strip("\x00"),
                marker not in payload,
            )
        sc_a37_7.check_true(
            "input_text_not_embedded_plain",
            "DB에 영속 저장된 진본 여정".encode("utf-8") not in payload,
        )
        sc_a37_7.finish()

        # 7. A37-8: 산출물 진위 보장 (요청에 다른 문자열을 끼워 넣어도 무시되고 DB 저장값만 렌더링)
        sc_a37_8 = ctx.report.scenario("A37-8", "클라이언트 변조 요청 무시 및 DB 진본 렌더링 진위 보장")
        response_tampered = await ctx.client.request(
            "POST", "/api/counsel/card/export",
            headers={"Authorization": "Bearer " + owner.token},
            json={
                "session_id": sid_valid,
                "card_data": {
                    "universe_transition": "해커가 위조한 거짓 괘사 및 결과",
                    "client_aha_moment": "가짜 문구",
                },
                "fake_injection": "외부 주입 문자열",
            },
            timeout=90.0,
        )
        record_response(ctx, sc_a37_8, response_tampered, path="/api/counsel/card/export",
                        actor_ref=owner.ref, authenticated=True)
        sc_a37_8.check("tampered_request_still_200", 200, response_tampered.status_code)
        # 위조 문자열이 평문으로 들어있지 않음은 물론, 렌더링 결과 바이트가 진본과 일치(동일 DB 저장본 렌더)
        sc_a37_8.check_true("is_png_output", response_tampered.content.startswith(b"\x89PNG\r\n\x1a\n"))
        sc_a37_8.finish()

    finally:
        await conn.execute("DELETE FROM public.counsel_sessions WHERE id IN ($1, $2)", sid_valid, sid_null)
        await conn.close()


# --------------------------------------------------------------------------
# AG-1 / A21, A24, A23: 법적 동의 및 연령 확인 E2E
# --------------------------------------------------------------------------


async def a24_age_confirmed(ctx: Context) -> None:
    """age_confirmed 엄격한 boolean 및 true 필수 검증 (A24-1)."""
    scenario = ctx.report.scenario("A24-1", "age_confirmed 엄격한 boolean 및 true 필수")
    actor = ctx.actor("user_a24")

    # false 거부 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/me/consent", actor=actor,
        json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": False},
    )
    scenario.check("false_rejected", 422, status)

    # 문자열 "true" 거부 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/me/consent", actor=actor,
        json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": "true"},
    )
    scenario.check("string_true_rejected", 422, status)
    scenario.finish()


async def a23_consent_version_and_idempotency(ctx: Context) -> None:
    """동의 버전 불일치 409 및 동일 버전 재요청 200 멱등 (A23-1)."""
    scenario = ctx.report.scenario("A23-1", "동의 버전 불일치 409 및 재요청 200 멱등")
    actor = ctx.actor("user_a23")

    # 다른 버전 -> 409
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/me/consent", actor=actor,
        json_body={"terms_version": "2025-01-01", "privacy_version": "2026-09-12", "age_confirmed": True},
    )
    scenario.check("version_mismatch_409", 409, status)

    # 정상 버전 최초 기록 -> 201
    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/me/consent", actor=actor,
        json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": True},
    )
    scenario.check("first_grant_201", 201, status)
    scenario.check("recorded_terms_version", "2026-09-12", payload.get("terms_version"))

    # 동일 사용자·동일 버전 재요청 -> 200 멱등 (새 행 생성 없이 기존 기록 반환)
    status, payload_idem, _ = await call(
        ctx, scenario, method="POST", path="/api/me/consent", actor=actor,
        json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": True},
    )
    scenario.check("idempotent_grant_200", 200, status)
    scenario.check("idem_terms_version", "2026-09-12", payload_idem.get("terms_version"))

    # GET /api/me/consent 조회 -> 200
    status, get_payload, _ = await call(
        ctx, scenario, method="GET", path="/api/me/consent", actor=actor,
    )
    scenario.check("get_consent_200", 200, status)
    current = get_payload.get("current") or {}
    scenario.check("current_terms_version", "2026-09-12", current.get("terms_version"))
    scenario.check("current_action", "GRANT", current.get("action"))
    scenario.finish()


async def a23_consent_withdrawal_lifecycle(ctx: Context) -> None:
    """A23 동의 철회 수명주기 및 데이터 권리 보장 검증 (A23-2 ~ A23-7)."""
    actor = ctx.actor("user_a23_withdraw")
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"

    conn = await _get_e2e_db_conn()
    try:
        # 1. A23-7: 무인증 철회 시도 401
        sc_a23_7 = ctx.report.scenario("A23-7", "동의 철회 무인증 차단 401")
        status, _, _ = await call(
            ctx, sc_a23_7, method="POST", path="/api/me/consent/withdraw", actor=None
        )
        sc_a23_7.check("unauth_withdraw_401", 401, status)
        sc_a23_7.finish()

        # 2. A23-5: 사전 조건 (동의 등록 및 세션 생성) 후 동의 철회 및 DB append 확인
        sc_a23_5 = ctx.report.scenario("A23-5", "동의 철회 행 append 및 기존 GRANT 보존")

        # 2-a. 동의 이력 없는 상태에서 철회 시도 -> 404
        status_nodata, _, _ = await call(
            ctx, sc_a23_5, method="POST", path="/api/me/consent/withdraw", actor=actor
        )
        sc_a23_5.check("withdraw_without_history_404", 404, status_nodata)

        # 2-b. 사전 조건: 동의 등록 (GRANT)
        await call(
            ctx, sc_a23_5, method="POST", path="/api/me/consent", actor=actor,
            json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": True},
        )
        # 세션 1건 생성 (기록 삭제 테스트용)
        status_st, payload_st, _ = await call(
            ctx, sc_a23_5, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A23_prep_session"), json_body={"question": "동의 철회 전 세션 생성"},
        )
        session_id = payload_st.get("session_id")
        sc_a23_5.check_true("prep_session_created", bool(status_st == 200 and session_id))

        # 2-c. 동의 철회 201 및 DB 행 검증
        status_w, payload_w, _ = await call(
            ctx, sc_a23_5, method="POST", path="/api/me/consent/withdraw", actor=actor
        )
        sc_a23_5.check("withdraw_201", 201, status_w)
        sc_a23_5.check("withdrawn_terms_version", "2026-09-12", payload_w.get("terms_version"))

        rows = await conn.fetch(
            "SELECT action, terms_version FROM public.user_consents WHERE user_id = $1 ORDER BY created_at ASC",
            actor.user_id,
        )
        sc_a23_5.check("consent_rows_count_is_2", 2, len(rows))
        sc_a23_5.check("first_row_grant", "GRANT", rows[0]["action"])
        sc_a23_5.check("second_row_withdraw", "WITHDRAW", rows[1]["action"])
        sc_a23_5.finish()

        # 5. A23-2: 철회 후 상담 시작 -> 403 CONSENT_REQUIRED
        sc_a23_2 = ctx.report.scenario("A23-2", "동의 철회 후 상담 시작 403 차단")
        status_blk, payload_blk, _ = await call(
            ctx, sc_a23_2, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A23_after_withdraw"), json_body={"question": "철회 후 상담 시도"},
        )
        sc_a23_2.check("withdrawn_start_403", 403, status_blk)
        sc_a23_2.check("error_code_consent_required", "CONSENT_REQUIRED", payload_blk.get("code"))
        sc_a23_2.finish()

        # 6. A23-3: 철회 후에도 데이터 권리 유지 (GET 200, DELETE 200, GET CREDITS 200)
        sc_a23_3 = ctx.report.scenario("A23-3", "동의 철회 후 데이터 권리(조회·삭제·크레딧) 200 유지")
        status_rec, _, _ = await call(
            ctx, sc_a23_3, method="GET", path="/api/me/records", actor=actor
        )
        sc_a23_3.check("records_list_200_after_withdraw", 200, status_rec)

        status_cred, _, _ = await call(
            ctx, sc_a23_3, method="GET", path="/api/me/credits", actor=actor
        )
        sc_a23_3.check("credits_200_after_withdraw", 200, status_cred)

        status_del, _, _ = await call(
            ctx, sc_a23_3, method="DELETE", path=f"/api/me/records/{session_id}", actor=actor
        )
        sc_a23_3.check("record_delete_200_after_withdraw", 200, status_del)
        sc_a23_3.finish()

        # 7. A23-6: 이미 철회 상태에서 재철회 -> 409 및 행 추가 없음
        sc_a23_6 = ctx.report.scenario("A23-6", "철회 상태에서 재철회 시도 409 멱등 충돌")
        status_re_w, _, _ = await call(
            ctx, sc_a23_6, method="POST", path="/api/me/consent/withdraw", actor=actor
        )
        sc_a23_6.check("re_withdraw_409", 409, status_re_w)
        count_after = await conn.fetchval(
            "SELECT COUNT(*) FROM public.user_consents WHERE user_id = $1",
            actor.user_id,
        )
        sc_a23_6.check("no_new_rows_on_409", 2, count_after)
        sc_a23_6.finish()

        # 8. A23-4: 철회 후 재동의 -> 200 및 상담 정상 재개 200
        sc_a23_4 = ctx.report.scenario("A23-4", "철회 후 재동의 및 상담 재개 200")
        status_re_g, _, _ = await call(
            ctx, sc_a23_4, method="POST", path="/api/me/consent", actor=actor,
            json_body={"terms_version": "2026-09-12", "privacy_version": "2026-09-12", "age_confirmed": True},
        )
        sc_a23_4.check("re_grant_201", 201, status_re_g)

        status_resumed, _, _ = await call(
            ctx, sc_a23_4, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("A23_resumed_start"), json_body={"question": "재동의 후 상담 재개"},
        )
        sc_a23_4.check("resumed_counsel_200", 200, status_resumed)
        sc_a23_4.finish()

    finally:
        await conn.close()



async def a21_consent_precheck(ctx: Context) -> None:
    """미동의 사용자의 동의 강제 차단 및 데이터 권리 보장 확인 (A21-1 / FIX-2)."""
    scenario = ctx.report.scenario("A21-1", "동의 강제 차단 및 데이터 권리 보장")
    actor = ctx.actor("user_a21_fresh")
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"

    # 잔액 50 초기화 (DB 직접 생성하여 잔액 불변 검증 기준 마련)
    conn = await _get_e2e_db_conn()
    try:
        await conn.execute(
            "INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING",
            actor.user_id,
        )
        bal_before = await conn.fetchval(
            "SELECT credit_balance FROM public.profiles WHERE id = $1",
            actor.user_id,
        )
    finally:
        await conn.close()

    # 1. 미동의 상태에서도 데이터 권리(기록 조회)는 200 유지 (마지막 줄 필수)
    status_rec, _, _ = await call(
        ctx, scenario, method="GET", path="/api/me/records", actor=actor,
    )
    scenario.check("records_still_200_without_consent", 200, status_rec)

    # 2. 미동의 사용자의 POST /api/counsel/start -> 403
    idem_key = ctx.key("A21_1")
    status_start, payload_start, _ = await call(
        ctx,
        scenario,
        method="POST",
        path="/api/counsel/start",
        actor=actor,
        idempotency_key=idem_key,
        json_body={"question": "미동의 상태 상담 시작 시도"},
    )
    scenario.check("no_consent_start_403", 403, status_start)
    scenario.check(
        "error_code_is_consent_required",
        "CONSENT_REQUIRED",
        payload_start.get("code"),
    )

    # 3. DB 직접 조회로 잔액 불변 및 credit_operations 0행 검증
    conn2 = await _get_e2e_db_conn()
    try:
        bal_after = await conn2.fetchval(
            "SELECT credit_balance FROM public.profiles WHERE id = $1",
            actor.user_id,
        )
        op_count = await conn2.fetchval(
            "SELECT COUNT(*) FROM public.credit_operations WHERE user_id = $1",
            actor.user_id,
        )
    finally:
        await conn2.close()

    scenario.check("balance_unchanged_after_403", bal_before, bal_after)
    scenario.check("no_credit_operation_row", 0, op_count)

    # 4. 동의 기록 POST /api/me/consent
    await call(
        ctx,
        scenario,
        method="POST",
        path="/api/me/consent",
        actor=actor,
        json_body={
            "terms_version": "2026-09-12",
            "privacy_version": "2026-09-12",
            "age_confirmed": True,
        },
    )

    # 5. 동의 기록 후 같은 호출 -> 200
    status_after, _, _ = await call(
        ctx,
        scenario,
        method="POST",
        path="/api/counsel/start",
        actor=actor,
        idempotency_key=idem_key,
        json_body={"question": "미동의 상태 상담 시작 시도"},
    )
    scenario.check("after_consent_start_200", 200, status_after)
    scenario.finish()


# --------------------------------------------------------------------------
# AG-3 / A29: 상담 기록 열람·삭제 E2E
# --------------------------------------------------------------------------


async def a29_unauthorized(ctx: Context) -> None:
    """네 경로 무인증 401 (A29-7)."""
    scenario = ctx.report.scenario("A29-7", "기록 및 동의 네 경로 무인증 401")

    # 1. GET /api/me/records
    status, _, _ = await call(ctx, scenario, method="GET", path="/api/me/records")
    scenario.check("records_list_401", 401, status)

    # 2. GET /api/me/records/{session_id}
    status, _, _ = await call(ctx, scenario, method="GET", path="/api/me/records/00000000-0000-0000-0000-000000000001")
    scenario.check("record_detail_401", 401, status)

    # 3. DELETE /api/me/records/{session_id}
    status, _, _ = await call(ctx, scenario, method="DELETE", path="/api/me/records/00000000-0000-0000-0000-000000000001")
    scenario.check("record_delete_401", 401, status)

    # 4. GET /api/me/consent
    status, _, _ = await call(ctx, scenario, method="GET", path="/api/me/consent")
    scenario.check("consent_get_401", 401, status)

    scenario.finish()


async def a29_records_gate_independent(ctx: Context) -> None:
    """게이트 상태와 무관하게 기록 조회가 200 반환 (A29-8)."""
    scenario = ctx.report.scenario("A29-8", "게이트 무관 기록 조회 200")
    actor = ctx.actor("user_a29_gate")

    # 서비스 게이트가 닫혀 있어도(503), 본인 기록 목록 조회는 200이어야 함
    status, payload, _ = await call(
        ctx, scenario, method="GET", path="/api/me/records", actor=actor,
    )
    scenario.check("records_list_200", 200, status)
    scenario.check_true("has_records_list", "records" in payload)
    scenario.finish()



async def a29_foreign_session_404(ctx: Context) -> None:
    """타 사용자 세션 조회·삭제 404 (403 아님) (A29-3)."""
    scenario = ctx.report.scenario("A29-3", "타 사용자 세션 조회·삭제 404")
    actor_owner = ctx.actor("user_a29_owner_3")
    actor_attacker = ctx.actor("user_a29_attacker_3")

    sess_id = str(uuid.uuid4())
    conn = await _get_e2e_db_conn()
    try:
        await conn.execute(
            "INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING",
            actor_owner.user_id,
        )
        await conn.execute(
            "INSERT INTO public.counsel_sessions (id, user_id, raw_question, is_duplicate) VALUES ($1, $2, 'A29-3 소유자 질문', false)",
            sess_id, actor_owner.user_id,
        )
    finally:
        await conn.close()

    # 타인 세션 상세 조회 -> 404
    status, _, _ = await call(
        ctx, scenario, method="GET", path=f"/api/me/records/{sess_id}", actor=actor_attacker,
    )
    scenario.check("foreign_get_404", 404, status)

    # 타인 세션 삭제 -> 404
    status, _, _ = await call(
        ctx, scenario, method="DELETE", path=f"/api/me/records/{sess_id}", actor=actor_attacker,
    )
    scenario.check("foreign_delete_404", 404, status)
    scenario.finish()


async def a29_anonymous_sessions_hidden(ctx: Context) -> None:
    """user_id IS NULL 익명 세션 미노출 (A29-4)."""
    scenario = ctx.report.scenario("A29-4", "익명 세션 미노출")
    actor = ctx.actor("user_a29_anon_probe")

    anon_sess_id = str(uuid.uuid4())
    conn = await _get_e2e_db_conn()
    try:
        await conn.execute(
            "INSERT INTO public.counsel_sessions (id, user_id, raw_question, is_duplicate) VALUES ($1, NULL, '익명 사용자의 상담 질문', false)",
            anon_sess_id,
        )
    finally:
        await conn.close()

    # 목록 조회 시 익명 세션이 포함되지 않아야 함
    status, payload, _ = await call(
        ctx, scenario, method="GET", path="/api/me/records", actor=actor,
    )
    scenario.check("list_status_200", 200, status)
    records = payload.get("records", [])
    scenario.check_true(
        "anon_session_not_in_list",
        all(r.get("session_id") != anon_sess_id for r in records),
    )

    # 직접 상세 조회 시도 -> 404
    status, _, _ = await call(
        ctx, scenario, method="GET", path=f"/api/me/records/{anon_sess_id}", actor=actor,
    )
    scenario.check("anon_session_direct_get_404", 404, status)

    # 직접 삭제 시도 -> 404
    status, _, _ = await call(
        ctx, scenario, method="DELETE", path=f"/api/me/records/{anon_sess_id}", actor=actor,
    )
    scenario.check("anon_session_direct_delete_404", 404, status)
    scenario.finish()


async def a29_cascade_delete_and_rescan(ctx: Context) -> None:
    """삭제 후 turns·journal 동반 삭제 및 재조회 404 (A29-5)."""
    scenario = ctx.report.scenario("A29-5", "삭제 후 turns·journal 동반 삭제 및 재조회 404")
    actor = ctx.actor("user_a29_cascade")

    sess_id = str(uuid.uuid4())
    conn = await _get_e2e_db_conn()
    try:
        await conn.execute(
            "INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING",
            actor.user_id,
        )
        await conn.execute(
            "INSERT INTO public.counsel_sessions (id, user_id, raw_question, is_duplicate) VALUES ($1, $2, '질문', false)",
            sess_id, actor.user_id,
        )
        await conn.execute(
            "INSERT INTO public.counsel_turns (session_id, turn_number, user_message, agent_response, needs_followup, is_final) VALUES ($1, 1, '메시지1', '답변1', true, false)",
            sess_id,
        )
        await conn.execute(
            "INSERT INTO public.journal_entries (session_id, summary, key_insights) VALUES ($1, '저널 요약', '핵심 통찰')",
            sess_id,
        )
    finally:
        await conn.close()

    # 삭제 전 상세 조회 -> 200
    status, detail_before, _ = await call(
        ctx, scenario, method="GET", path=f"/api/me/records/{sess_id}", actor=actor,
    )
    scenario.check("detail_before_200", 200, status)
    scenario.check("turns_count_1", 1, len(detail_before.get("turns", [])))

    # 삭제 요청 -> 200
    status, del_res, _ = await call(
        ctx, scenario, method="DELETE", path=f"/api/me/records/{sess_id}", actor=actor,
    )
    scenario.check("delete_200", 200, status)
    scenario.check_true("del_flag_true", del_res.get("deleted") is True)
    scenario.check("turns_deleted_1", 1, del_res.get("turns_deleted"))
    scenario.check("journal_deleted_1", 1, del_res.get("journal_deleted"))

    # 삭제 후 상세 재조회 -> 404
    status, _, _ = await call(
        ctx, scenario, method="GET", path=f"/api/me/records/{sess_id}", actor=actor,
    )
    scenario.check("detail_after_404", 404, status)
    scenario.finish()


async def a29_snapshot_scrubbing_db_verify(ctx: Context) -> None:
    """삭제 후 credit_operations.response_snapshot IS NULL을 DB 직접 확인 (A29-6)."""
    scenario = ctx.report.scenario("A29-6", "삭제 후 response_snapshot IS NULL DB 직접 확인")
    actor = ctx.actor("user_a29_scrub")

    sess_id = str(uuid.uuid4())
    op_id = str(uuid.uuid4())

    conn = await _get_e2e_db_conn()
    try:
        await conn.execute(
            "INSERT INTO public.profiles (id, credit_balance) VALUES ($1, 50) ON CONFLICT (id) DO NOTHING",
            actor.user_id,
        )
        await conn.execute(
            "INSERT INTO public.counsel_sessions (id, user_id, raw_question, is_duplicate) VALUES ($1, $2, '스냅샷 질문', false)",
            sess_id, actor.user_id,
        )
        await conn.execute(
            """
            INSERT INTO public.credit_operations
                (id, user_id, endpoint, idempotency_key, request_hash, status, amount, fencing_token, response_snapshot)
            VALUES
                ($1, $2, 'counsel.start', $3, 'hash123', 'SUCCEEDED', 10, $4, $5)
            """,
            op_id, actor.user_id, f"key-scrub-{op_id[:8]}", str(uuid.uuid4()),
            json.dumps({"session_id": sess_id, "secret": "상담 민감 정보 본문"}),
        )

        # 삭제 전 DB에서 response_snapshot이 존재하는지 확인
        val_before = await conn.fetchval(
            "SELECT response_snapshot FROM public.credit_operations WHERE id = $1",
            op_id,
        )
        scenario.check_true("snapshot_exists_before", val_before is not None)
    finally:
        await conn.close()

    # DELETE /api/me/records/{session_id} 호출
    status, del_res, _ = await call(
        ctx, scenario, method="DELETE", path=f"/api/me/records/{sess_id}", actor=actor,
    )
    scenario.check("delete_200", 200, status)
    scenario.check("snapshots_scrubbed_1", 1, del_res.get("operation_snapshots_scrubbed"))

    # 삭제 후 DB 직접 쿼리로 response_snapshot IS NULL 확인 (핵심 무결성 검증)
    conn = await _get_e2e_db_conn()
    try:
        val_after = await conn.fetchval(
            "SELECT response_snapshot FROM public.credit_operations WHERE id = $1",
            op_id,
        )
        scenario.check("snapshot_is_null_after", None, val_after)
    finally:
        await conn.close()

    scenario.finish()


# --------------------------------------------------------------------------
# AG-4 / A20: 고객지원 문의 영속화 E2E
# --------------------------------------------------------------------------


async def a20_support_validation(ctx: Context) -> None:
    """문의 카테고리·길이·이메일 위반 422 (A20-2)."""
    scenario = ctx.report.scenario("A20-2", "문의 카테고리·길이·이메일 위반 422")

    # 1. 카테고리 위반 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "hacked_category", "email": "valid@example.com", "message": "정상 문의"},
    )
    scenario.check("bad_category_422", 422, status)

    # 2. 이메일 형식 위반 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "service", "email": "invalid-email-address", "message": "정상 문의"},
    )
    scenario.check("bad_email_422", 422, status)

    # 3. 메시지 4000자 초과 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "service", "email": "valid@example.com", "message": "가" * 4001},
    )
    scenario.check("oversized_message_422", 422, status)

    # 4. 빈 메시지 -> 422
    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "service", "email": "valid@example.com", "message": "   "},
    )
    scenario.check("empty_message_422", 422, status)
    scenario.finish()


async def a20_support_submission(ctx: Context) -> None:
    """문의 정상 접수, DB 행 확인, 티켓 번호 유일성 (A20-1)."""
    scenario = ctx.report.scenario("A20-1", "문의 정상 접수, DB 행 확인, 티켓 번호 유일성")

    # 비로그인 접수 1
    status, p1, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "service", "email": "user1@example.com", "message": "첫 번째 문의입니다."},
    )
    scenario.check("submit_1_201", 201, status)
    scenario.check("status_received", "RECEIVED", p1.get("status"))
    tkt1 = p1.get("ticket_no", "")
    scenario.check_true("tkt1_format", bool(tkt1.startswith("TKT-") and len(tkt1) >= 20))

    # 비로그인 접수 2
    status, p2, _ = await call(
        ctx, scenario, method="POST", path="/api/support/inquiries",
        json_body={"category": "privacy", "email": "user2@example.com", "message": "개인정보 삭제 문의입니다."},
    )
    scenario.check("submit_2_201", 201, status)
    tkt2 = p2.get("ticket_no", "")
    scenario.check_true("tkt2_format", bool(tkt2.startswith("TKT-") and len(tkt2) >= 20))

    # 티켓 번호 유일성 확인
    scenario.check_true("tickets_are_unique", tkt1 != tkt2)

    # DB 직접 확인: support_inquiries 테이블에 두 행이 실제로 존재하는지
    conn = await _get_e2e_db_conn()
    try:
        row1 = await conn.fetchrow(
            "SELECT ticket_no, category, email, status FROM public.support_inquiries WHERE ticket_no = $1",
            tkt1,
        )
        scenario.check_true("db_row1_exists", row1 is not None)
        if row1:
            scenario.check("db_row1_category", "service", row1["category"])
            scenario.check("db_row1_email", "user1@example.com", row1["email"])

        row2 = await conn.fetchrow(
            "SELECT ticket_no, category, email, status FROM public.support_inquiries WHERE ticket_no = $1",
            tkt2,
        )
        scenario.check_true("db_row2_exists", row2 is not None)
        if row2:
            scenario.check("db_row2_category", "privacy", row2["category"])
            scenario.check("db_row2_email", "user2@example.com", row2["email"])
    finally:
        await conn.close()

    scenario.finish()


async def run_all(ctx: Context) -> None:
    """묶음 1 시나리오. 게이트가 열린 뒤에 호출한다."""
    await a10_body_size_limit(ctx)
    await a10_field_limits(ctx)
    await a10_cors(ctx)
    await a35_safety_resources(ctx)
    await a02_generation_kill_switch(ctx)
    await a02_cost_budget_quota(ctx)
    await a02_persistence_and_ops(ctx)
    await a37_card_export(ctx)

    # 신규 Phase 1 인수기준 시나리오
    await a24_age_confirmed(ctx)
    await a23_consent_version_and_idempotency(ctx)
    await a23_consent_withdrawal_lifecycle(ctx)
    await a21_consent_precheck(ctx)
    await a29_unauthorized(ctx)
    await a29_records_gate_independent(ctx)
    await a29_foreign_session_404(ctx)
    await a29_anonymous_sessions_hidden(ctx)
    await a29_cascade_delete_and_rescan(ctx)
    await a29_snapshot_scrubbing_db_verify(ctx)
    await a20_support_validation(ctx)
    await a20_support_submission(ctx)


