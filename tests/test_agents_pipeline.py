"""멀티에이전트 파이프라인 전체 동작 검증 테스트 (Mock LLM 기반 네트워크 0원 보장)."""

import pytest

from agents.pipeline import run_turn
from core.db import AsyncSessionLocal


class MockLLMDispatcher:
    """역할(role)별로 사전에 준비된 응답을 돌려주는 Mock LLM."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls = []

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.calls.append({"user": user, "system": system})
        for key, resp in self.responses.items():
            if key in system or key in user:
                return resp
        # 기본값
        return self.responses.get("default", {})


@pytest.mark.asyncio
async def test_정상_상담_흐름_괘도출_대화_저널생성(monkeypatch):
    # RAG 검색 시 가짜 청크 반환하도록 monkeypatch
    from core.rag import RetrievedChunk

    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="test_c1",
                hexagram_id=1,
                line_number=1,
                source_type="line_comm",
                category="commentary",
                content="潛龍勿用 陽在下也",
                content_ko="잠긴 용은 쓰지 말아야 하니 양이 아래에 있음이다.",
                similarity=0.9,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_chunks", mock_search_chunks)

    mock_clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL", "signals": []}}),
        "intake": MockLLMDispatcher({
            "default": {
                "clarified_question": "새로운 프로젝트를 시작할 때의 마음가짐",
                "topic_category": "커리어/진로",
                "is_duplicate_question": False,
                "duplicate_session_ref": None,
            }
        }),
        "interpret": MockLLMDispatcher({
            "default": {
                "contextual_mapping": "현재는 힘을 비축하고 때를 기다려야 하는 잠룡의 시기입니다."
            }
        }),
        "counsel": MockLLMDispatcher({
            "default": {
                "message": "새로운 시작을 앞두고 조급한 마음이 들 수 있습니다. 지금 가장 준비해야 할 부분은 무엇일까요?",
                "needs_followup": True,
                "followup_question": "지금 가장 준비해야 할 부분은 무엇일까요?",
                "is_final": False,
            }
        }),
        "journal": MockLLMDispatcher({
            "default": {
                "summary": "새 프로젝트 착수를 앞둔 성찰 상담",
                "key_insights": "잠룡의 시기에는 조급함보다 내실을 다져야 함.",
                "action_items": "기초 역량 점검",
            }
        }),
    }

    async with AsyncSessionLocal() as session:
        # [Turn 1] 신규 세션 시작
        res1 = await run_turn(
            session,
            user_id="test_user_pipe",
            message="새 프로젝트 시작하는데 조언 부탁해",
            manual_lines=[7, 7, 7, 7, 7, 7],  # 건괘 (동효 없음)
            clients=mock_clients,
        )

        assert res1.turn_number == 1
        assert res1.hexagram_id == 1
        assert res1.needs_followup is True
        assert res1.is_final is False
        assert "조급한 마음" in res1.user_facing_message
        assert "BLOCK_CRISIS" not in res1.user_facing_message

        # [Turn 2] 후속 대화
        mock_clients["counsel"] = MockLLMDispatcher({
            "default": {
                "message": "스스로의 역량을 믿고 차분히 기초를 다지시길 응원합니다.",
                "needs_followup": False,
                "followup_question": None,
                "is_final": True,
            }
        })

        res2 = await run_turn(
            session,
            counsel_session_id=res1.session_id,
            user_id="test_user_pipe",
            message="기초부터 탄탄히 준비해보려고 합니다. 고마워요!",
            clients=mock_clients,
        )

        assert res2.turn_number == 2
        assert res2.is_final is True
        assert res2.journal_summary is not None
        assert "새 프로젝트" in res2.journal_summary


@pytest.mark.asyncio
async def test_위기_발화_즉시_차단_및_래치_유지():
    mock_clients = {
        "safety": MockLLMDispatcher({
            "default": {
                "category": "BLOCK_CRISIS",
                "signals": ["위기"],
                "reason": "자살/자해",
            }
        }),
    }

    async with AsyncSessionLocal() as session:
        # [Turn 1] 위기 발화
        res1 = await run_turn(
            session,
            user_id="crisis_user",
            message="사는 게 너무 지치고 다 끝내고 싶어요",
            clients=mock_clients,
        )

        assert res1.safety_category == "BLOCK_CRISIS"
        assert res1.hexagram_id is None  # 괘를 뽑지 않아야 함
        assert res1.is_final is True
        assert "109" in res1.user_facing_message
        assert "BLOCK_CRISIS" not in res1.user_facing_message

        # [Turn 2] 화제 전환 시도 -> 래치 유지로 괘 미도출 및 차단 지속
        mock_clients["safety"] = MockLLMDispatcher({
            "default": {
                "category": "NORMAL",  # Mock이 NORMAL을 줘도 래치에 의해 차단되어야 함
            }
        })

        res2 = await run_turn(
            session,
            counsel_session_id=res1.session_id,
            user_id="crisis_user",
            message="아까는 헛소리였고, 오늘 주식 살까요?",
            clients=mock_clients,
        )

        assert res2.safety_category == "BLOCK_CRISIS"
        assert res2.hexagram_id is None
        assert "109" in res2.user_facing_message


@pytest.mark.asyncio
async def test_재삼독_중복질문_감지_시_괘_미도출_및_회고_유도():
    from core.models.counsel import CounselSession
    import uuid

    prev_id = str(uuid.uuid4())

    mock_clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({
            "default": {
                "clarified_question": "이직해야 할까요?",
                "topic_category": "커리어/진로",
                "is_duplicate_question": True,
                "duplicate_session_ref": prev_id,
            }
        }),
    }

    from unittest.mock import AsyncMock, patch

    async with AsyncSessionLocal() as session:
        # 이전 세션 사전 생성
        prev_sess = CounselSession(
            id=prev_id,
            user_id="dup_user",
            raw_question="이직해야 할까요?",
            status="completed",
        )
        session.add(prev_sess)
        await session.commit()

        with patch("agents.pipeline._get_past_sessions", new_callable=AsyncMock) as mock_get_past:
            mock_get_past.return_value = [
                {"session_id": prev_id, "clarified_question": "이직해야 할까요?", "summary": "이직 고민"}
            ]

            res = await run_turn(
                session,
                user_id="dup_user",
                message="이직해야 할까요?",
                clients=mock_clients,
            )

            assert res.is_duplicate is True
            assert res.hexagram_id is None  # 괘를 다시 뽑지 않음
            assert "이전에 이미 같은 고민" in res.user_facing_message
            assert prev_id in res.user_facing_message

