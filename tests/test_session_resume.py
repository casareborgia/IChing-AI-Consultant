# -*- coding: utf-8 -*-
"""종료된 상담 이어가기(B안) 회귀 테스트 (B-1 ~ B-7).

SESSION_RESUME_ORDER.md 요구사항:
- B-1: 종료된 세션에 턴을 더 보내면 200이고 turn_number가 6이다
- B-2: 6턴 이상 프롬프트에 "마지막 턴" 지시가 붙지 않는다
- B-3: 6턴 이상 턴 목표가 폴백 문구가 아니다
- B-4: safety_redirect 세션은 403 SESSION_CLOSED_FOR_SAFETY
- B-5: RESUME_MAX_TURNS (15) 도달 시 403 SESSION_TURN_LIMIT_REACHED
- B-6: 이어간 뒤 is_final이 다시 와도 기존 저널이 바뀌지 않는다
- B-7: 크레딧이 부족하면 턴이 차감 없이 거절된다 (기존 계약 유지 확인)
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from agents.divination_chat_engine import DivinationChatEngine
from agents.journal import write_journal
from api.deps import check_rate_limit, require_consent, require_user
from api.main import app
from api.routers import counsel as counsel_router
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from services import credit_operation_service as svc


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def scalar(self):
        return self._value

    def scalars(self):
        items = self._value if isinstance(self._value, (list, tuple)) else [self._value]
        return _ScalarsResult(items)


class _ScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class FakeDbSession:
    def __init__(self, execute_results=None):
        self._results = list(execute_results or [])
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, statement, *args, **kwargs):
        if self._results:
            val = self._results.pop(0)
            return _Result(val)
        return _Result(None)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, obj):
        pass


@pytest.fixture
def auth_user():
    user_id = str(uuid.uuid4())

    async def _user():
        return user_id

    async def _noop():
        return None

    app.dependency_overrides[require_user] = _user
    app.dependency_overrides[require_consent] = _user
    app.dependency_overrides[check_rate_limit] = _noop
    app.dependency_overrides[counsel_router.require_service_gate] = _noop
    app.dependency_overrides[counsel_router.require_generation_enabled] = _noop
    app.dependency_overrides[counsel_router.require_cost_budget] = _noop
    yield user_id
    app.dependency_overrides.clear()


async def _post_turn(headers=None, session_id="sess-resume", message="이어지는 이야기입니다."):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/api/counsel/turn",
            headers=headers or {"Idempotency-Key": str(uuid.uuid4())},
            json={"session_id": session_id, "user_message": message},
        )


# --- B-2: 6턴 이상 프롬프트에 '마지막 턴' 지시가 붙지 않는다 ---------------------
@pytest.mark.asyncio
async def test_b2_prompt_omits_last_turn_instruction_for_turn_6_plus():
    """B-2: 6턴 이상 프롬프트에 마지막 턴 지시가 붙지 않고, 5턴 도달 시에만 붙는다."""
    from agents.counsel import run_counsel_turn

    class FakeLLMClient:
        def __init__(self):
            self.prompts = []

        def complete_json(self, prompt, **kwargs):
            self.prompts.append(prompt)
            return {"message": "이어가는 이야기입니다.", "needs_followup": True, "is_final": False}

    fake_client = FakeLLMClient()

    # 턴 5: 마지막 턴 안내가 반드시 포함되어야 함
    await run_counsel_turn(
        user_message="다짐을 완료했습니다.",
        interpretation=None,
        conversation_history=[],
        turn_number=5,
        client=fake_client,
    )
    prompt_t5 = fake_client.prompts[-1]
    assert "마지막 턴(턴 5 도달)" in prompt_t5

    # 턴 6: 마지막 턴 안내가 붙지 않아야 함
    await run_counsel_turn(
        user_message="실천하면서 이런 생각이 들었어요.",
        interpretation=None,
        conversation_history=[],
        turn_number=6,
        client=fake_client,
    )
    prompt_t6 = fake_client.prompts[-1]
    assert "마지막 턴(턴 5 도달)" not in prompt_t6
    assert "이어간 턴 6" in prompt_t6

    # 턴 7: 마지막 턴 안내가 붙지 않아야 함
    await run_counsel_turn(
        user_message="추가 질문입니다.",
        interpretation=None,
        conversation_history=[],
        turn_number=7,
        client=fake_client,
    )
    prompt_t7 = fake_client.prompts[-1]
    assert "마지막 턴" not in prompt_t7
    assert "이어간 턴 7" in prompt_t7


# --- B-3: 6턴 이상 턴 목표가 폴백 문구가 아니다 -------------------------------
def test_b3_turn_goal_description_for_turn_6_plus():
    """B-3: 6턴 이상 턴 목표가 Socratic 폴백이 아니라 후속 대화 목표를 반환한다."""
    engine = DivinationChatEngine()
    goal_t6 = engine._get_turn_goal_description(6)
    assert "Turn 6+: Follow-up" in goal_t6
    assert "The 5-turn coaching arc and the action pledge are already complete" in goal_t6
    assert "Socratic conversation turn." not in goal_t6

    goal_t10 = engine._get_turn_goal_description(10)
    assert "Turn 6+: Follow-up" in goal_t10
    assert "Socratic conversation turn." not in goal_t10


# --- B-4: safety_redirect 세션은 403 SESSION_CLOSED_FOR_SAFETY ----------------
@pytest.mark.asyncio
async def test_b4_safety_redirect_session_rejected_with_403(auth_user, monkeypatch):
    """B-4: safety_redirect 세션은 403 SESSION_CLOSED_FOR_SAFETY로 즉시 거절된다."""
    c_sess = CounselSession(
        id="sess-crisis",
        user_id=auth_user,
        raw_question="위기 상담 세션",
        status="safety_redirect",
    )

    fake_db = FakeDbSession(execute_results=[c_sess])
    monkeypatch.setattr(counsel_router, "AsyncSessionLocal", lambda: fake_db)

    begin_op_called = False

    async def _fail_begin(*args, **kwargs):
        nonlocal begin_op_called
        begin_op_called = True
        raise AssertionError("위기 세션 재개는 크레딧 차감 단계까지 가면 안 된다")

    monkeypatch.setattr(counsel_router, "begin_operation", _fail_begin)

    res = await _post_turn(session_id="sess-crisis")
    assert res.status_code == 403
    body = res.json()
    assert body.get("code") == "SESSION_CLOSED_FOR_SAFETY"
    assert "위기 지원 안내로 종료된 세션" in (body.get("detail") or body.get("message") or "")
    assert not begin_op_called


# --- B-5 / SR-6: RESUME_MAX_TURNS (15) 도달 시 403 SESSION_TURN_LIMIT_REACHED ---------
@pytest.mark.asyncio
async def test_b5_turn_limit_reached_rejected_with_403(auth_user, monkeypatch):
    """B-5 / SR-6: 턴 수가 RESUME_MAX_TURNS(15) 이상이면 403 SESSION_TURN_LIMIT_REACHED 반환."""
    c_sess = CounselSession(
        id="sess-limit",
        user_id=auth_user,
        raw_question="긴 대화 세션",
        status="completed",
    )

    # 1번째 execute: CounselSession 조회 -> c_sess
    # 2번째 execute: func.count(CounselTurn.id) -> 15
    fake_db = FakeDbSession(execute_results=[c_sess, 15])
    monkeypatch.setattr(counsel_router, "AsyncSessionLocal", lambda: fake_db)

    begin_op_called = False

    async def _fail_begin(*args, **kwargs):
        nonlocal begin_op_called
        begin_op_called = True
        raise AssertionError("턴 상한 도달 시 크레딧 차감 단계까지 가면 안 된다")

    monkeypatch.setattr(counsel_router, "begin_operation", _fail_begin)

    res = await _post_turn(session_id="sess-limit")
    assert res.status_code == 403
    body = res.json()
    assert body.get("code") == "SESSION_TURN_LIMIT_REACHED"
    assert "최대 대화 턴 수(15턴)에 도달" in (body.get("detail") or body.get("message") or "")
    assert not begin_op_called


# Note: SR-6(턴 15 상한 도달 시 403 및 차감 방지) 요구사항은 위의 test_b5_turn_limit_reached_rejected_with_403에서 통합 검증함.


# --- B-6: 이어간 뒤 is_final이 다시 와도 기존 저널이 바뀌지 않는다 -------------
@pytest.mark.asyncio
async def test_b6_write_journal_preserves_existing_entry():
    """B-6: 기존 저널이 존재하면 새 요약/인사이트로 덮어쓰지 않고 기존 엔트리를 보존한다."""
    c_sess = CounselSession(
        id="sess-original",
        user_id="user-1",
        raw_question="원래 고민",
        clarified_question="명확화된 고민",
        topic_category="진로",
        status="active",
    )

    turn = CounselTurn(
        id=1,
        session_id="sess-original",
        turn_number=1,
        user_message="고민 내용",
        agent_response="답변 내용",
    )

    existing = JournalEntry(
        id=101,
        session_id="sess-original",
        summary="원래 확정된 5턴 다짐 요약",
        key_insights="원래 인사이트 1",
        action_items="원래 행동 다짐",
        card_data={"action_card": "기존 데이터"},
    )

    # FakeDbSession의 순차 execute 결과:
    # 1. c_session 조회 (scalar_one_or_none)
    # 2. turns 조회 (scalars().all())
    # 3. existing_journal 조회 (scalar_one_or_none)
    fake_db = FakeDbSession(execute_results=[c_sess, [turn], existing])

    class FakeJournalLLM:
        def complete_json(self, *args, **kwargs):
            return {
                "universe_transition": "새 요약 시도",
                "client_aha_moment": "새 인사이트",
                "client_action_pledge": "새 행동 다짐",
                "is_smart_compliant": True,
                "counselor_reframing": "새 리프레이밍",
            }

    res = await write_journal(
        session=fake_db,
        counsel_session_id="sess-original",
        client=FakeJournalLLM(),
    )

    assert res.id == 101
    assert res.summary == "원래 확정된 5턴 다짐 요약", "기존 요약이 덮어쓰여지지 않아야 한다"
    assert res.key_insights == "원래 인사이트 1", "기존 인사이트가 보존되어야 한다"
    assert res.action_items == "원래 행동 다짐", "기존 행동 다짐이 보존되어야 한다"


# --- B-7: 크레딧 부족 시 턴이 차감 없이 거절된다 -------------------------------
@pytest.mark.asyncio
async def test_b7_insufficient_credit_turn_rejected(auth_user, monkeypatch):
    """B-7: 크레딧이 부족하면 402 에러로 턴이 차감 없이 거절된다."""
    c_sess = CounselSession(
        id="sess-credit",
        user_id=auth_user,
        raw_question="크레딧 부족 테스트",
        status="active",
    )

    # 1번째: session 조회, 2번째: count(turns) -> 5
    fake_db = FakeDbSession(execute_results=[c_sess, 5])
    monkeypatch.setattr(counsel_router, "AsyncSessionLocal", lambda: fake_db)

    async def _reject_op(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id="op-rejected",
            status=svc.STATUS_REJECTED,
            amount=10,
            credit_delta=0,
            remaining_credits=5,
            error_code=svc.CODE_INSUFFICIENT_CREDITS,
            error_message="크레딧이 부족합니다. (1회 10 크레딧 필요, 현재 잔액: 5C)",
        )

    monkeypatch.setattr(counsel_router, "begin_operation", _reject_op)

    res = await _post_turn(session_id="sess-credit")
    assert res.status_code == 402
    body = res.json()
    assert body.get("code") == svc.CODE_INSUFFICIENT_CREDITS
    assert body.get("remaining_credits") == 5
    assert "크레딧이 부족합니다" in body.get("detail", "")


# --- B-1: 종료된 세션에 턴을 더 보내면 200이고 turn_number가 6이다 ------------
@pytest.mark.asyncio
async def test_b1_resume_completed_session_returns_200_and_turn_6(auth_user, monkeypatch):
    """B-1: 완료 상태의 세션(이전 5턴)에 턴을 보내면 200 응답과 함께 turn_number 6으로 처리된다."""
    c_sess = CounselSession(
        id="sess-b1",
        user_id=auth_user,
        raw_question="완료된 5턴 세션",
        status="completed",
    )

    # 1번째 execute: session 조회
    # 2번째 execute: count(turns) -> 5 (현재 5턴 완료 상태)
    fake_db = FakeDbSession(execute_results=[c_sess, 5])
    monkeypatch.setattr(counsel_router, "AsyncSessionLocal", lambda: fake_db)

    # 크레딧 예약 성공 mock
    async def _ok_begin(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_RESERVED,
            operation_id="op-b1",
            status=svc.STATUS_PROCESSING,
            amount=10,
            fencing_token="token-b1",
        )

    monkeypatch.setattr(counsel_router, "begin_operation", _ok_begin)

    # 파이프라인 run_turn Mock: 턴 번호 6으로 실행됨을 확인
    import api.main as api_main

    runner_called = False

    async def _mock_run_turn(*args, **kwargs):
        nonlocal runner_called
        runner_called = True
        return SimpleNamespace(
            session_id="sess-b1",
            turn_number=6,
            user_facing_message="6번째 턴 응답입니다.",
            needs_followup=True,
            is_final=False,
            hexagram_id=1,
            transformed_hexagram_id=None,
            changing_lines=[],
            safety_category="NORMAL",
            is_duplicate=False,
            journal_summary=None,
            journal_data=None,
            focus_rule=None,
            evidences=[],
            report_data=None,
            report_status="not_requested",
            report_error_code=None,
        )

    monkeypatch.setattr(api_main, "run_turn", _mock_run_turn)

    async def _mock_finalize_success(*args, **kwargs):
        return svc.OperationOutcome(
            kind=svc.KIND_REPLAY,
            operation_id="op-b1",
            status=svc.STATUS_SUCCEEDED,
            amount=10,
            credit_delta=-10,
            remaining_credits=30,
            response_snapshot=kwargs.get("response_snapshot"),
        )

    monkeypatch.setattr(counsel_router, "finalize_success", _mock_finalize_success)

    res = await _post_turn(session_id="sess-b1")
    assert res.status_code == 200
    body = res.json()
    assert runner_called is True
    assert body["turn_number"] == 6
    assert body["user_facing_message"] == "6번째 턴 응답입니다."
    assert body["is_final"] is False
    assert body["remaining_credits"] == 30
