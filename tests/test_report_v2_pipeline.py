"""파이프라인이 판본 플래그를 어떻게 다루는가, 실패가 무엇을 보존하는가.

폐기 DB가 필요하다(`TEST_DATABASE_URL`). 실제 LLM은 부르지 않는다.
"""

import json

import pytest

from agents.pipeline import run_turn
from core.config import settings
from core.db import AsyncSessionLocal
from core.models.counsel import CounselSession, CounselTurn
from core.report_versions import (
    CODE_REPORT_UNAVAILABLE,
    REPORT_LEGACY,
    REPORT_V2,
    report_schema_version,
)
from sqlalchemy import select
from tests.fixtures.report_v2_builder import VALID_DRAFT


class RoleLLM:
    """역할별 고정 응답. 리포트 역할만 별도로 갈아 끼운다."""

    def __init__(self, response, *, fail=False):
        self.response = response
        self.fail = fail
        self.calls = 0

    def complete_json(self, user: str, *, system: str = "", **kwargs):
        self.calls += 1
        if self.fail:
            raise TimeoutError("업스트림 상세 — 공개되면 안 된다")
        return self.response


def base_clients(report_client):
    return {
        "safety": RoleLLM({"category": "NORMAL", "signals": []}),
        "intake": RoleLLM({
            "clarified_question": "일이 막혀 있을 때 어디서부터 손을 댈지",
            "topic_category": "직장/진로",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }),
        "interpret": RoleLLM({"contextual_mapping": "막힌 것을 하나씩 다루는 국면입니다."}),
        "report": report_client,
        "counsel": RoleLLM({
            "message": "지금 가장 걸리는 것은 무엇인가요?",
            "needs_followup": True,
            "followup_question": "지금 가장 걸리는 것은 무엇인가요?",
            "is_final": False,
        }),
        "journal": RoleLLM({
            "summary": "막힌 상황을 나누어 다루기",
            "key_insights": "작게 나누면 시작할 자리가 생긴다.",
            "action_items": "걸린 것 하나 적기",
        }),
    }


LEGACY_REPORT_RESPONSE = {
    "section1_diagnosis": "지금은 막힌 것을 다루어야 하는 자리입니다.",
    "section2_action": "걸려 있는 것을 하나씩 떼어내십시오.",
    "section3_warning": "조급함을 경계하십시오.",
    "section4_future": "지금의 국면이 이어집니다.",
    "final_summary": "작게 나누어 다루는 것이 이번의 방법입니다.",
}


@pytest.fixture
def report_flag():
    """플래그를 바꾸고 반드시 되돌린다."""
    original = settings.REPORT_SCHEMA_VERSION

    def _set(value):
        settings.REPORT_SCHEMA_VERSION = value

    yield _set
    settings.REPORT_SCHEMA_VERSION = original


@pytest.fixture
def stub_rag(monkeypatch):
    from core.rag import RetrievedChunk

    async def _search(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=kwargs.get("hexagram_id") or 1,
                line_number=kwargs.get("line_number"), source_type="hex_comm",
                category="commentary", content="原文",
                content_ko="막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
                similarity=0.9,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", _search)
    monkeypatch.setattr("core.prompts.load_system_prompt", lambda name: f"STUB:{name}")


async def run_once(clients, *, message="일이 막혀 있습니다. 어디서부터 손을 대야 할까요?"):
    async with AsyncSessionLocal() as session:
        result = await run_turn(
            session,
            counsel_session_id=None,
            user_id=None,
            message=message,
            manual_lines=[7, 8, 8, 7, 8, 7],  # 화뢰서합 불변괘
            clients=clients,
        )
        await session.commit()
        return result


async def stored_session(session_id):
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(
                select(CounselSession).where(CounselSession.id == session_id)
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_default_flag_still_produces_legacy(report_flag, stub_rag):
    """기본 배포 동작을 보존한다. FE 통합 전에는 v2를 내려보내지 않는다."""
    report_flag(REPORT_LEGACY)
    result = await run_once(base_clients(RoleLLM(LEGACY_REPORT_RESPONSE)))

    assert result.report_status == "ready"
    assert report_schema_version(result.report_data) == REPORT_LEGACY
    assert "section2_action" in result.report_data


@pytest.mark.asyncio
async def test_flag_on_produces_v2(report_flag, stub_rag):
    report_flag(REPORT_V2)
    result = await run_once(base_clients(RoleLLM(VALID_DRAFT)))

    assert result.report_status == "ready"
    assert report_schema_version(result.report_data) == REPORT_V2
    assert result.report_data["academic_details"]["casting"]["original_hexagram_id"] == 21
    assert result.report_data["session_id"] == result.session_id


@pytest.mark.asyncio
async def test_stored_report_survives_a_flag_flip(report_flag, stub_rag):
    """플래그를 내려도 이미 저장된 v2는 지워지지도 구형으로 오인되지도 않는다."""
    report_flag(REPORT_V2)
    result = await run_once(base_clients(RoleLLM(VALID_DRAFT)))
    session_id = result.session_id

    report_flag(REPORT_LEGACY)
    row = await stored_session(session_id)

    assert row.report_status == "ready"
    assert report_schema_version(row.report_data) == REPORT_V2
    # JSONB 왕복이 값을 바꾸지 않는다.
    assert row.report_data == json.loads(json.dumps(result.report_data, ensure_ascii=False))


@pytest.mark.asyncio
async def test_legacy_generation_still_uses_the_common_focus_rule(report_flag, stub_rag):
    """v2 플래그가 꺼져 있다는 이유로 예전의 독자 고변점 계산이 되살아나지 않는다."""
    report_flag(REPORT_LEGACY)
    report_client = RoleLLM(LEGACY_REPORT_RESPONSE)
    result = await run_once(base_clients(report_client))

    focus = result.report_data["focus_and_body_use"]
    assert focus["changing_count"] == 0
    assert "본괘의 괘사" in focus["rule_description"]
    # 불변괘에 지괘를 말하지 않는다.
    assert "지괘가 없습니다" in focus["body_use_flow"]
    assert result.report_data["hexagram_casting"]["has_transformation"] is False


@pytest.mark.asyncio
async def test_report_failure_preserves_the_cast_and_the_counsel_answer(report_flag, stub_rag):
    """리포트 실패가 괘 재추첨이나 상담 중단을 부르지 않는다."""
    report_flag(REPORT_V2)
    result = await run_once(base_clients(RoleLLM(None, fail=True)))

    assert result.report_status == "failed"
    assert result.report_data is None
    # 괘는 그대로 있고 상담 답변도 나갔다.
    assert result.hexagram_id == 21
    assert result.changing_lines == []
    assert result.user_facing_message

    async with AsyncSessionLocal() as session:
        turn = (
            await session.execute(
                select(CounselTurn).where(CounselTurn.session_id == result.session_id)
            )
        ).scalars().first()
    assert turn.original_hexagram_id == 21


@pytest.mark.asyncio
async def test_failure_code_is_stable_and_carries_no_internal_detail(report_flag, stub_rag):
    report_flag(REPORT_V2)
    result = await run_once(base_clients(RoleLLM(None, fail=True)))

    # 예전에는 `type(exc).__name__`("TimeoutError")이 그대로 응답에 실렸다.
    assert result.report_error_code in ("REPORT_MODEL_FAILED", CODE_REPORT_UNAVAILABLE)
    assert "TimeoutError" not in (result.report_error_code or "")
    assert "업스트림" not in (result.report_error_code or "")


@pytest.mark.asyncio
async def test_v2_report_reaches_the_counsel_prompt(report_flag, stub_rag):
    """첫 턴에서 만든 리포트가 같은 턴의 상담 프롬프트에 실린다."""
    report_flag(REPORT_V2)
    counsel = RoleLLM({
        "message": "지금 가장 걸리는 것은 무엇인가요?",
        "needs_followup": True, "is_final": False,
    })
    clients = base_clients(RoleLLM(VALID_DRAFT))
    clients["counsel"] = counsel

    captured = []
    original = counsel.complete_json

    def spy(user, *, system="", **kwargs):
        captured.append(user)
        return original(user, system=system, **kwargs)

    counsel.complete_json = spy
    await run_once(clients)

    prompt = captured[0]
    assert "[확정 원전 근거" in prompt
    assert "[리포트가 제안한 행동" in prompt
    # 원문은 넘기지 않는다. 번역만 간다.
    #
    # 번역문 자체에 한자가 남아 있는 것은 별개의, 이미 알려진 데이터 문제다 —
    # 괘사 번역 45/64가 괘 이름을 한자로 달고 있다("噬嗑은 형통하니 …").
    # 저본 정비 없이는 이 자리에서 막을 수 없고, 이번 카드의 범위도 아니다.
    assert "噬嗑 亨 利用獄" not in prompt


@pytest.mark.asyncio
async def test_followup_turn_still_receives_the_stored_report(report_flag, stub_rag):
    """후속 턴에도 저장된 리포트와 실제 근거가 도착한다."""
    report_flag(REPORT_V2)
    first = await run_once(base_clients(RoleLLM(VALID_DRAFT)))

    counsel = RoleLLM({
        "message": "그 이야기를 조금 더 들려주시겠어요?",
        "needs_followup": True, "is_final": False,
    })
    clients = base_clients(RoleLLM(VALID_DRAFT))
    clients["counsel"] = counsel
    captured = []
    original = counsel.complete_json

    def spy(user, *, system="", **kwargs):
        captured.append(user)
        return original(user, system=system, **kwargs)

    counsel.complete_json = spy

    async with AsyncSessionLocal() as session:
        await run_turn(
            session,
            counsel_session_id=first.session_id,
            user_id=None,
            message="첫 번째 항목부터 해보려 합니다.",
            clients=clients,
        )
        await session.commit()

    prompt = captured[0]
    assert "[확정 원전 근거" in prompt
    assert "내담자가 선택하지 않았습니다" in prompt


@pytest.mark.asyncio
async def test_report_generation_does_not_add_a_counsel_turn(report_flag, stub_rag):
    """리포트는 상담 턴을 늘리지 않는다."""
    report_flag(REPORT_V2)
    result = await run_once(base_clients(RoleLLM(VALID_DRAFT)))

    async with AsyncSessionLocal() as session:
        turns = (
            await session.execute(
                select(CounselTurn).where(CounselTurn.session_id == result.session_id)
            )
        ).scalars().all()
    assert len(turns) == 1
    assert result.turn_number == 1
