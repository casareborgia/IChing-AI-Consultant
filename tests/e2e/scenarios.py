# -*- coding: utf-8 -*-
"""CYCLE-06 시나리오.

모든 요청은 실제 TCP로 제품 FastAPI 앱에 간다. ASGI in-process 지름길을 쓰지
않는다. 미들웨어·CORS·인증·rate limit이 실제로 지나간다.

시나리오마다 사용자를 새로 만든다. 이유는 두 가지다. rate limit 버킷이 섞이지
않고, 웰컴 크레딧 50C에서 출발하는 잔액 계산이 시나리오끼리 간섭하지 않는다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

from tests.e2e.harness import fake_pipeline, tokens
from tests.e2e.harness.recorder import HttpRecord, Report, ScenarioResult, safe_body

GENERIC_ERROR_MESSAGE = "일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
CONSULTATION_COST = 10
WELCOME_CREDITS = 50

# 500 응답 본문에 절대 나타나면 안 되는 조각.
FORBIDDEN_IN_ERROR_BODY = (
    "Traceback",
    "asyncpg",
    "sqlalchemy",
    "SQLAlchemy",
    "FakePipelineFailure",
    "iching_e2e_test",
    "postgresql",
    "password",
    "/Users/",
    "credit_operations",
)


@dataclass
class Actor:
    ref: str
    user_id: str
    token: str


class Context:
    def __init__(self, *, client: httpx.AsyncClient, report: Report, issuer: str, secret: str):
        self.client = client
        self.report = report
        self.issuer = issuer
        self.secret = secret
        self._key_refs: Dict[str, str] = {}

    def actor(self, ref: str) -> Actor:
        user_id = tokens.new_user_id()
        self.report.aliases.alias("user", user_id)
        return Actor(
            ref=ref,
            user_id=user_id,
            token=tokens.mint(secret=self.secret, issuer=self.issuer, subject=user_id),
        )

    def key(self, ref: str) -> str:
        """별칭이 붙은 idempotency key를 만든다. 보고서에는 별칭만 남는다."""
        raw = tokens.idempotency_key("e2e" + ref.replace("_", "-"))
        self._key_refs[raw] = ref
        return raw

    def key_ref(self, raw: Optional[str]) -> Optional[str]:
        return self._key_refs.get(raw or "")


async def ensure_consent(ctx: Context, actor: Actor) -> None:
    """테스트 시나리오 수행 전 일반 내담자 액터의 약관 동의를 보장한다 (FIX-2)."""
    if not hasattr(ctx, "_consented_actors"):
        ctx._consented_actors = set()
    if actor.user_id in ctx._consented_actors:
        return
    resp = await ctx.client.post(
        "/api/me/consent",
        headers={"Authorization": f"Bearer {actor.token}"},
        json={
            "terms_version": "2026-09-12",
            "privacy_version": "2026-09-12",
            "age_confirmed": True,
        },
        timeout=10.0,
    )
    if resp.status_code in (200, 201):
        ctx._consented_actors.add(actor.user_id)


async def call(
    ctx: Context,
    scenario: ScenarioResult,
    *,
    method: str,
    path: str,
    actor: Optional[Actor] = None,
    idempotency_key: Optional[str] = None,
    json_body: Optional[Dict[str, Any]] = None,
    bad_token: Optional[str] = None,
) -> Tuple[int, Dict[str, Any], httpx.Response]:
    if (
        actor
        and actor.ref != "user_a21_fresh"
        and path in ("/api/counsel/start", "/api/counsel/turn")
        and not bad_token
        and scenario.scenario_id not in ("S01", "S03", "A21-1", "A23-2")
    ):
        await ensure_consent(ctx, actor)

    headers: Dict[str, str] = {}
    token = bad_token if bad_token is not None else (actor.token if actor else None)
    if token:
        headers["Authorization"] = "Bearer " + token
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    response = await ctx.client.request(
        method, path, headers=headers, json=json_body, timeout=90.0
    )
    try:
        payload = response.json()
    except Exception:
        payload = {}

    ctx.report.record_http(
        HttpRecord(
            method=method,
            path=path if "operations/" not in path else "/api/counsel/operations/{id}",
            status=response.status_code,
            scenario=scenario.scenario_id,
            actor=actor.ref if actor else "anonymous",
            idempotency_key_ref=ctx.key_ref(idempotency_key),
            authenticated=bool(token),
            body=safe_body(payload),
        )
    )
    return response.status_code, payload if isinstance(payload, dict) else {}, response


def record_response(
    ctx: Context,
    scenario: ScenarioResult,
    response: httpx.Response,
    *,
    path: str,
    actor_ref: str = "anonymous",
    authenticated: bool = False,
) -> None:
    """이미 보낸 요청을 기계 기록에 남긴다.

    `call`을 쓸 수 없는 요청(OPTIONS preflight, 바이너리 응답)도 http_trace에
    들어가야 한다. 그렇지 않으면 보고된 요청 수가 실제보다 적어지고, 기계 기록이
    실행을 온전히 설명하지 못한다.
    """
    try:
        payload = response.json()
    except Exception:
        payload = {"_binary_or_empty": True, "_bytes": len(response.content)}

    ctx.report.record_http(
        HttpRecord(
            method=response.request.method,
            path=path,
            status=response.status_code,
            scenario=scenario.scenario_id,
            actor=actor_ref,
            idempotency_key_ref=None,
            authenticated=authenticated,
            body=safe_body(payload),
        )
    )


async def balance(ctx: Context, scenario: ScenarioResult, actor: Actor) -> Optional[int]:
    status, payload, _ = await call(
        ctx, scenario, method="GET", path="/api/me/credits", actor=actor
    )
    if status != 200:
        scenario.check("balance_query_status", 200, status)
        return None
    return payload.get("remaining_credits")


def op_ref(ctx: Context, scenario: ScenarioResult, operation_id: Optional[str]) -> Optional[str]:
    return ctx.report.aliases.alias("op", operation_id)


# --------------------------------------------------------------------------
# 개별 시나리오
# --------------------------------------------------------------------------


async def s01_service_gate_closed(ctx: Context) -> None:
    """제품 기본값에서 상담 경로가 fail-closed인지 먼저 증명한다.

    이 시나리오만 게이트 override 없이 돈다. 하네스가 뒤에서 게이트를 여는 것이
    정당한지 판단하려면, 끄기 전의 제품 기본 동작이 기록되어야 한다.
    """
    scenario = ctx.report.scenario("S01", "출시 게이트 기본값에서 상담 503")
    actor = ctx.actor("user_gate")
    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("S01"), json_body={"question": "E2E 게이트 확인"},
    )
    scenario.check("start_status", 503, status)
    scenario.check_true("has_detail", bool(payload.get("detail")))
    scenario.finish()


async def s02_missing_idempotency_key(ctx: Context) -> None:
    scenario = ctx.report.scenario("S02", "Idempotency-Key 누락 400")
    actor = ctx.actor("user_key")
    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        json_body={"question": "E2E 키 누락"},
    )
    scenario.check("status", 400, status)
    scenario.check("code", "IDEMPOTENCY_KEY_REQUIRED", payload.get("code"))

    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key="short", json_body={"question": "E2E 키 형식"},
    )
    scenario.check("invalid_status", 400, status)
    scenario.check("invalid_code", "IDEMPOTENCY_KEY_INVALID", payload.get("code"))
    scenario.finish()


async def s03_unauthenticated(ctx: Context) -> None:
    scenario = ctx.report.scenario("S03", "인증 누락·위조 토큰 401")
    status, _, response = await call(
        ctx, scenario, method="GET", path="/api/me/credits"
    )
    scenario.check("credits_no_auth", 401, status)
    scenario.check_true(
        "www_authenticate_header",
        response.headers.get("www-authenticate", "").lower().startswith("bearer"),
    )

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start",
        idempotency_key=ctx.key("S03a"), json_body={"question": "E2E 무인증"},
    )
    scenario.check("start_no_auth", 401, status)

    status, _, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/turn",
        idempotency_key=ctx.key("S03b"),
        json_body={"session_id": "nonexistent-session", "user_message": "E2E 무인증"},
    )
    scenario.check("turn_no_auth", 401, status)

    forged = tokens.mint_wrong_signature(issuer=ctx.issuer, subject=tokens.new_user_id())
    status, _, _ = await call(
        ctx, scenario, method="GET", path="/api/me/credits", bad_token=forged
    )
    scenario.check("forged_signature", 401, status)

    victim = ctx.actor("user_expired")
    expired = tokens.mint_expired(secret=ctx.secret, issuer=ctx.issuer, subject=victim.user_id)
    status, _, _ = await call(
        ctx, scenario, method="GET", path="/api/me/credits", bad_token=expired
    )
    scenario.check("expired_token", 401, status)
    scenario.finish()


async def s04_start_success(ctx: Context) -> Tuple[Actor, Optional[str]]:
    scenario = ctx.report.scenario("S04", "정상 start 200·10C 차감")
    actor = ctx.actor("user_start")
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"

    scenario.balance_before = await balance(ctx, scenario, actor)
    scenario.check("welcome_balance", WELCOME_CREDITS, scenario.balance_before)

    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("S04"), json_body={"question": "E2E 정상 시작"},
    )
    scenario.check("status", 200, status)
    scenario.check("operation_status", "SUCCEEDED", payload.get("operation_status"))
    scenario.check("credit_delta", -CONSULTATION_COST, payload.get("credit_delta"))
    scenario.check("remaining_credits", WELCOME_CREDITS - CONSULTATION_COST,
                   payload.get("remaining_credits"))
    scenario.check("turn_number", 1, payload.get("turn_number"))
    scenario.check("needs_followup", True, payload.get("needs_followup"))
    scenario.check("is_final", False, payload.get("is_final"))
    scenario.check("is_crisis", False, payload.get("is_crisis"))
    for field_name in ("session_id", "user_facing_message", "operation_id", "evidences"):
        scenario.check_true("has_" + field_name, field_name in payload)

    reference = op_ref(ctx, scenario, payload.get("operation_id"))
    scenario.transition(reference, payload.get("operation_status"), "POST /api/counsel/start")

    scenario.balance_after = await balance(ctx, scenario, actor)
    scenario.check("balance_after", WELCOME_CREDITS - CONSULTATION_COST, scenario.balance_after)
    scenario.finish()
    return actor, payload.get("session_id")


async def s05_s06_turns(ctx: Context, actor: Actor, session_id: Optional[str]) -> None:
    """같은 세션에서 needs_followup 턴과 최종 턴을 잇는다."""
    scenario = ctx.report.scenario("S05", "needs_followup=true 상태의 turn")
    if not session_id:
        scenario.result = "FAIL"
        scenario.failure_reason = "선행 start에서 session_id를 받지 못함"
        return

    fake_pipeline.FINAL_TURN_AT[actor.user_id] = 3
    scenario.balance_before = await balance(ctx, scenario, actor)

    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/turn", actor=actor,
        idempotency_key=ctx.key("S05"),
        json_body={"session_id": session_id, "user_message": "E2E 두 번째 턴"},
    )
    scenario.check("status", 200, status)
    scenario.check("turn_number", 2, payload.get("turn_number"))
    scenario.check("needs_followup", True, payload.get("needs_followup"))
    scenario.check("is_final", False, payload.get("is_final"))
    scenario.check("operation_status", "SUCCEEDED", payload.get("operation_status"))
    scenario.check("credit_delta", -CONSULTATION_COST, payload.get("credit_delta"))
    scenario.check("same_session", session_id, payload.get("session_id"))
    scenario.transition(
        op_ref(ctx, scenario, payload.get("operation_id")),
        payload.get("operation_status"), "POST /api/counsel/turn",
    )
    scenario.balance_after = payload.get("remaining_credits")
    scenario.finish()

    final = ctx.report.scenario("S06", "후속 turn 종료 (is_final)")
    final.balance_before = scenario.balance_after
    status, payload, _ = await call(
        ctx, final, method="POST", path="/api/counsel/turn", actor=actor,
        idempotency_key=ctx.key("S06"),
        json_body={"session_id": session_id, "user_message": "E2E 마지막 턴"},
    )
    final.check("status", 200, status)
    final.check("turn_number", 3, payload.get("turn_number"))
    final.check("needs_followup", False, payload.get("needs_followup"))
    final.check("is_final", True, payload.get("is_final"))
    final.check_true("journal_summary_present", bool(payload.get("journal_summary")))
    final.check("operation_status", "SUCCEEDED", payload.get("operation_status"))
    final.transition(
        op_ref(ctx, final, payload.get("operation_id")),
        payload.get("operation_status"), "POST /api/counsel/turn",
    )
    final.balance_after = payload.get("remaining_credits")
    final.check("balance_after", WELCOME_CREDITS - 3 * CONSULTATION_COST, final.balance_after)
    final.finish()


async def s07_in_progress_polling(ctx: Context) -> None:
    scenario = ctx.report.scenario("S07", "202 IN_PROGRESS polling 후 SUCCEEDED")
    actor = ctx.actor("user_poll")
    fake_pipeline.arm_block(actor.user_id)
    key = ctx.key("S07")
    body = {"question": "E2E 진행 중 폴링"}

    scenario.balance_before = await balance(ctx, scenario, actor)

    first = asyncio.create_task(
        call(ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
             idempotency_key=key, json_body=body)
    )

    entered = await asyncio.get_event_loop().run_in_executor(
        None, fake_pipeline.wait_until_entered, actor.user_id, 30.0
    )
    scenario.check_true("pipeline_entered", entered)

    status, payload, response = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body=body,
    )
    scenario.check("second_request_status", 202, status)
    scenario.check("code", "OPERATION_IN_PROGRESS", payload.get("code"))
    scenario.check_true("retry_after_header", bool(response.headers.get("retry-after")))
    scenario.check_true("retry_after_seconds", isinstance(payload.get("retry_after_seconds"), int))

    operation_id = payload.get("operation_id")
    reference = op_ref(ctx, scenario, operation_id)
    scenario.transition(reference, "PROCESSING", "POST /api/counsel/start (202)")

    if operation_id:
        status, poll, _ = await call(
            ctx, scenario, method="GET",
            path="/api/counsel/operations/{0}".format(operation_id), actor=actor,
        )
        scenario.check("poll_status", 200, status)
        scenario.check("poll_operation_status", "PROCESSING", poll.get("operation_status"))
        scenario.check("poll_result_null", None, poll.get("result"))
        scenario.transition(reference, poll.get("operation_status"),
                            "GET /api/counsel/operations/{id}")

    fake_pipeline.release_block(actor.user_id)
    status, payload, _ = await first
    scenario.check("first_request_status", 200, status)
    scenario.check("first_operation_status", "SUCCEEDED", payload.get("operation_status"))
    scenario.transition(reference, payload.get("operation_status"),
                        "POST /api/counsel/start (완료)")

    if operation_id:
        status, poll, _ = await call(
            ctx, scenario, method="GET",
            path="/api/counsel/operations/{0}".format(operation_id), actor=actor,
        )
        scenario.check("final_poll_status", 200, status)
        scenario.check("final_operation_status", "SUCCEEDED", poll.get("operation_status"))
        scenario.check("final_credit_delta", -CONSULTATION_COST, poll.get("credit_delta"))
        scenario.check_true("final_result_present", isinstance(poll.get("result"), dict))
        scenario.transition(reference, poll.get("operation_status"),
                            "GET /api/counsel/operations/{id}")

    scenario.balance_after = await balance(ctx, scenario, actor)
    scenario.check("balance_after", WELCOME_CREDITS - CONSULTATION_COST, scenario.balance_after)
    scenario.finish()


async def s08_s09_idempotency(ctx: Context) -> None:
    scenario = ctx.report.scenario("S08", "동일 idempotency key 재시도 (재생·중복차감 없음)")
    actor = ctx.actor("user_idem")
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"
    key = ctx.key("S08")
    body = {"question": "E2E 멱등 재시도"}

    scenario.balance_before = await balance(ctx, scenario, actor)
    status, first, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body=body,
    )
    scenario.check("first_status", 200, status)
    reference = op_ref(ctx, scenario, first.get("operation_id"))
    scenario.transition(reference, first.get("operation_status"), "최초 요청")

    status, replay, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body=body,
    )
    scenario.check("replay_status", 200, status)
    scenario.check("same_operation", first.get("operation_id"), replay.get("operation_id"))
    scenario.check("same_session", first.get("session_id"), replay.get("session_id"))
    scenario.check_opaque("same_message", first.get("user_facing_message"),
                          replay.get("user_facing_message"))
    scenario.check("same_delta", first.get("credit_delta"), replay.get("credit_delta"))
    scenario.check("same_remaining", first.get("remaining_credits"),
                   replay.get("remaining_credits"))
    scenario.transition(reference, replay.get("operation_status"), "동일 키 재시도")

    scenario.balance_after = await balance(ctx, scenario, actor)
    scenario.check("charged_once", WELCOME_CREDITS - CONSULTATION_COST, scenario.balance_after)
    scenario.finish()

    conflict = ctx.report.scenario("S09", "동일 키·다른 body 409")
    conflict.balance_before = scenario.balance_after
    status, payload, _ = await call(
        ctx, conflict, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body={"question": "E2E 다른 본문"},
    )
    conflict.check("status", 409, status)
    conflict.check("code", "IDEMPOTENCY_KEY_REUSED", payload.get("code"))
    conflict.check("same_operation_reported", first.get("operation_id"),
                   payload.get("operation_id"))
    conflict.balance_after = await balance(ctx, conflict, actor)
    conflict.check("no_extra_charge", scenario.balance_after, conflict.balance_after)
    conflict.finish()


async def s10_s11_s14_failure_paths(ctx: Context) -> Optional[str]:
    """실패 → RELEASED·0C → 동일 키 복구 → 오류 정보 비노출."""
    scenario = ctx.report.scenario("S10", "답변 없는 실패 시 RELEASED 및 0C")
    actor = ctx.actor("user_fail")
    fake_pipeline.BEHAVIORS[actor.user_id] = "fail"
    key = ctx.key("S10")
    body = {"question": "E2E 파이프라인 장애"}

    scenario.balance_before = await balance(ctx, scenario, actor)
    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body=body,
    )
    scenario.check("status", 500, status)
    scenario.check("code", "PIPELINE_FAILED", payload.get("code"))
    scenario.check_opaque("generic_message", GENERIC_ERROR_MESSAGE, payload.get("message"))
    scenario.check("remaining_credits", WELCOME_CREDITS, payload.get("remaining_credits"))

    operation_id = payload.get("operation_id")
    reference = op_ref(ctx, scenario, operation_id)
    scenario.transition(reference, "RELEASED", "POST /api/counsel/start (500)")

    if operation_id:
        status, poll, _ = await call(
            ctx, scenario, method="GET",
            path="/api/counsel/operations/{0}".format(operation_id), actor=actor,
        )
        scenario.check("poll_status", 200, status)
        scenario.check("released", "RELEASED", poll.get("operation_status"))
        scenario.check("zero_delta", 0, poll.get("credit_delta"))
        scenario.check("no_result", None, poll.get("result"))
        scenario.transition(reference, poll.get("operation_status"),
                            "GET /api/counsel/operations/{id}")

    scenario.balance_after = await balance(ctx, scenario, actor)
    scenario.check("no_charge", WELCOME_CREDITS, scenario.balance_after)
    scenario.finish()

    # --- S14: 같은 500 응답이 내부 정보를 흘리지 않는지 --------------------
    disclosure = ctx.report.scenario("S14", "내부 오류 정보 비노출")
    allowed = {"code", "message", "detail", "operation_id", "remaining_credits"}
    actual_fields = set(str(k) for k in payload.keys())
    disclosure.check("fields_within_contract", True, actual_fields.issubset(allowed))
    disclosure.check("field_names", sorted(allowed & actual_fields), sorted(actual_fields))
    serialized = repr(payload)
    for fragment in FORBIDDEN_IN_ERROR_BODY:
        disclosure.check_true("no_" + fragment.strip("/").lower(), fragment not in serialized)
    disclosure.check_opaque("message_equals_detail", payload.get("message"),
                            payload.get("detail"))
    disclosure.finish()

    # --- S11: 실패 후 동일 키 복구 ----------------------------------------
    recovery = ctx.report.scenario("S11", "실패 후 동일 키 복구")
    recovery.balance_before = scenario.balance_after
    status, replay, _ = await call(
        ctx, recovery, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=key, json_body=body,
    )
    recovery.check("replay_status", 500, status)
    recovery.check("replay_code", "PIPELINE_FAILED", replay.get("code"))
    recovery.check("replay_same_operation", operation_id, replay.get("operation_id"))
    recovery.transition(reference, "RELEASED", "동일 키 재시도 (재생)")

    mid = await balance(ctx, recovery, actor)
    recovery.check("still_no_charge", WELCOME_CREDITS, mid)

    # 새 키로 다시 시도하면 정상 진행된다. 실패한 키가 사용자를 영구히 막지 않는다.
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"
    status, retried, _ = await call(
        ctx, recovery, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("S11"), json_body=body,
    )
    recovery.check("new_key_status", 200, status)
    recovery.check("new_key_operation_status", "SUCCEEDED", retried.get("operation_status"))
    recovery.check("new_key_delta", -CONSULTATION_COST, retried.get("credit_delta"))
    recovery.transition(
        op_ref(ctx, recovery, retried.get("operation_id")),
        retried.get("operation_status"), "새 키 재시도",
    )
    recovery.balance_after = await balance(ctx, recovery, actor)
    recovery.check("charged_once_after_recovery",
                   WELCOME_CREDITS - CONSULTATION_COST, recovery.balance_after)
    recovery.finish()
    return operation_id


async def s12_cross_user(ctx: Context, foreign_operation_id: Optional[str]) -> None:
    scenario = ctx.report.scenario("S12", "타 사용자 operation 조회 차단")
    if not foreign_operation_id:
        scenario.result = "FAIL"
        scenario.failure_reason = "선행 시나리오에서 operation_id를 받지 못함"
        return

    intruder = ctx.actor("user_intruder")
    status, payload, _ = await call(
        ctx, scenario, method="GET",
        path="/api/counsel/operations/{0}".format(foreign_operation_id), actor=intruder,
    )
    scenario.check("status", 404, status)
    scenario.check_true("no_owner_leak", "user" not in repr(payload).lower())

    status, _, _ = await call(
        ctx, scenario, method="GET",
        path="/api/counsel/operations/{0}".format("00000000-0000-4000-8000-000000000000"),
        actor=intruder,
    )
    scenario.check("missing_operation_same_404", 404, status)
    scenario.finish()


async def s13_insufficient_credits(ctx: Context) -> None:
    scenario = ctx.report.scenario("S13", "크레딧 부족 402")
    actor = ctx.actor("user_broke")
    fake_pipeline.BEHAVIORS[actor.user_id] = "succeed"
    fake_pipeline.FINAL_TURN_AT[actor.user_id] = 99  # 매번 needs_followup

    scenario.balance_before = await balance(ctx, scenario, actor)
    spent = 0
    for index in range(WELCOME_CREDITS // CONSULTATION_COST):
        status, payload, _ = await call(
            ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
            idempotency_key=ctx.key("S13-{0}".format(index)),
            json_body={"question": "E2E 소진 {0}".format(index)},
        )
        if status != 200:
            scenario.check("drain_{0}_status".format(index), 200, status)
            break
        spent += CONSULTATION_COST

    scenario.check("drained_to_zero", 0, WELCOME_CREDITS - spent)

    status, payload, _ = await call(
        ctx, scenario, method="POST", path="/api/counsel/start", actor=actor,
        idempotency_key=ctx.key("S13-final"), json_body={"question": "E2E 잔액 없음"},
    )
    scenario.check("status", 402, status)
    scenario.check("code", "INSUFFICIENT_CREDITS", payload.get("code"))
    scenario.check("remaining_credits", 0, payload.get("remaining_credits"))
    scenario.transition(
        op_ref(ctx, scenario, payload.get("operation_id")), "REJECTED",
        "POST /api/counsel/start (402)",
    )
    scenario.balance_after = await balance(ctx, scenario, actor)
    scenario.check("balance_after", 0, scenario.balance_after)
    scenario.finish()


async def run_all(ctx: Context, *, app) -> None:
    """S01만 게이트 기본값에서 돌고, 나머지는 게이트를 연 뒤 돈다."""
    from tests.e2e.harness import testapp

    await s01_service_gate_closed(ctx)

    testapp.open_service_gate(app)
    ctx.report.notes.append(
        "S01 이후 require_service_gate 의존성을 테스트 동안 override했다. "
        "제품 소스는 변경하지 않았고 인증·rate limit·크레딧 경로는 실제 구현 그대로다."
    )

    await s02_missing_idempotency_key(ctx)
    await s03_unauthenticated(ctx)
    actor, session_id = await s04_start_success(ctx)
    await s05_s06_turns(ctx, actor, session_id)
    await s07_in_progress_polling(ctx)
    await s08_s09_idempotency(ctx)
    foreign_operation = await s10_s11_s14_failure_paths(ctx)
    await s12_cross_user(ctx, foreign_operation)
    await s13_insufficient_credits(ctx)

    # CYCLE-08 묶음 1 — 인수기준 A 항목 (A02·A10·A35·A37)
    from tests.e2e import scenarios_a_items

    await scenarios_a_items.run_all(ctx)
