"""Google ADK 기반 멀티에이전트 아키텍처 및 워크플로우 단위 테스트."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agents.adk import (
    IChingADKWorkflow,
    create_safety_agent,
    create_intake_agent,
    create_interpret_agent,
    create_counsel_agent,
    create_journal_agent,
    execute_safety_agent,
    execute_intake_agent,
)
from agents.tools import (
    cast_hexagram_tool,
    lookup_hexagram_text_tool,
    search_iching_commentaries_tool,
    lookup_past_sessions_tool,
)
from core.db import AsyncSessionLocal
from core.rag import RetrievedChunk
from tests.test_agents_pipeline import MockLLMDispatcher


@pytest.mark.asyncio
async def test_adk_agents_initialization():
    """모든 ADK 에이전트가 올바른 메타데이터와 지침으로 초기화되는지 검증."""
    safety = create_safety_agent()
    intake = create_intake_agent()
    interpret = create_interpret_agent()
    counsel = create_counsel_agent()
    journal = create_journal_agent()

    assert safety.name == "safety"
    assert safety.output_schema is not None
    assert intake.name == "intake"
    assert len(intake.tools) > 0
    assert interpret.name == "interpret"
    assert len(interpret.tools) >= 3
    assert counsel.name == "counsel"
    assert journal.name == "journal"


@pytest.mark.asyncio
async def test_adk_tools_execution():
    """ADK 표준 도구들의 정상 작동 검증."""
    async with AsyncSessionLocal() as session:
        # 1. 괘 산출 도구
        cast_res = await cast_hexagram_tool(manual_lines=[7, 7, 7, 7, 7, 7])
        assert cast_res.original_hexagram_id == 1
        assert len(cast_res.changing_lines) == 0

        # 2. 확정 원문 조회 도구
        evidence = await lookup_hexagram_text_tool(session, cast_res)
        assert evidence.original.name_full == "중천건"
        assert evidence.target_hexagram_id == 1

        # 3. 과거 세션 조회 도구
        past = await lookup_past_sessions_tool(session, user_id="non_existent_user")
        assert isinstance(past, list)
        assert len(past) == 0


@pytest.mark.asyncio
async def test_adk_workflow_full_run(monkeypatch):
    """ADK 워크플로우를 통한 전체 상담 파이프라인 턴 실행 검증."""
    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="test_adk_c1",
                hexagram_id=1,
                line_number=1,
                source_type="line_comm",
                category="commentary",
                content="潛龍勿用 陽在下也",
                content_ko="잠긴 용은 쓰지 말아야 하니 양이 아래에 있음이다.",
                similarity=0.95,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

    mock_clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL", "signals": []}}),
        "intake": MockLLMDispatcher({
            "default": {
                "clarified_question": "새로운 도전을 앞두고 조언을 구합니다.",
                "topic_category": "진로",
                "is_duplicate_question": False,
                "duplicate_session_ref": None,
            }
        }),
        "interpret": MockLLMDispatcher({
            "default": {
                "contextual_mapping": "새로운 시작 단계에서는 조급함을 버리고 준비해야 합니다."
            }
        }),
        "counsel": MockLLMDispatcher({
            "default": {
                "message": "새로운 도전을 준비하면서 가장 염려되는 점은 무엇인가요?",
                "needs_followup": True,
                "followup_question": "가장 염려되는 점은 무엇인가요?",
                "is_final": False,
            }
        }),
        "journal": MockLLMDispatcher({
            "default": {
                "summary": "새로운 도전 상담",
                "key_insights": "차분한 준비의 필요성",
                "action_items": "계획 수립",
            }
        }),
    }

    workflow = IChingADKWorkflow()

    async with AsyncSessionLocal() as session:
        result = await workflow.run_turn(
            session=session,
            user_message="새로운 프로젝트를 시작하려는데 마음이 불안합니다.",
            manual_lines=[7, 7, 7, 7, 7, 7],
            clients=mock_clients,
        )

        assert result.session_id is not None
        assert result.turn_number == 1
        assert result.hexagram_id == 1
        assert result.needs_followup is True
        assert "가장 염려되는 점" in result.user_facing_message
