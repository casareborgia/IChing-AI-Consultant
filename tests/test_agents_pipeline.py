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

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

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
async def test_주역_자체를_묻는_질문에는_괘를_뽑지_않는다(monkeypatch):
    """묻는 사람은 괘를 뽑은 적이 없다.

    그런데도 뽑아서 답하면 "지금 보신 괘는…"처럼 사실이 아닌 전제를 사용자에게
    돌려주게 된다. 실제 대화록에서 그렇게 나가고 있었다.
    """
    from core.hexagram_engine import cast_hexagram

    def _no_cast(*args, **kwargs):
        raise AssertionError("정보 질문인데 괘를 뽑았습니다")

    monkeypatch.setattr("agents.interpret.cast_hexagram", _no_cast)

    clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "request_type": "question",
            "clarified_question": "대흉이 무슨 뜻인지",
            "topic_category": "주역 문의",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }}),
        "counsel": MockLLMDispatcher({"default": {
            "message": "대흉은 지금 이 길이 위험하다는 신호입니다. 물어보고 싶은 고민이 있으시면 그때 괘를 헤아려 드리겠습니다.",
            "needs_followup": True,
            "followup_question": "어떤 고민이 있으신가요?",
            "is_final": False,
        }}),
    }

    async with AsyncSessionLocal() as session:
        res = await run_turn(
            session, user_id="meta_user",
            message="괘에 대흉이라고 나오면 그건 무슨 뜻인가요?",
            clients=clients,
        )

    assert res.hexagram_id is None, "정보 질문에는 괘가 없어야 한다"
    assert res.changing_lines is None
    assert "대흉은" in res.user_facing_message


@pytest.mark.asyncio
async def test_사연이_섞이면_상담으로_본다(monkeypatch):
    """'대흉이 뭔가요? 제 인생도 끝난 걸까요'는 정보 질문이 아니다."""
    from core.rag import RetrievedChunk

    async def mock_search(*args, **kwargs):
        return [RetrievedChunk(
            chunk_id="c", hexagram_id=1, line_number=None, source_type="guasa_comm",
            category="annotation", content="원문", content_ko="번역", similarity=0.7,
        )]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search)

    clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "request_type": "counsel",
            "clarified_question": "지금 상황이 끝난 것인지",
            "topic_category": "내면/심리",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }}),
        "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "매핑"}}),
        "counsel": MockLLMDispatcher({"default": {
            "message": "끝이라고 느끼시는군요. 무엇이 그렇게 느끼게 하나요?",
            "needs_followup": True, "followup_question": "무엇이 그렇게 느끼게 하나요?",
            "is_final": False,
        }}),
    }

    async with AsyncSessionLocal() as session:
        res = await run_turn(
            session, user_id="mixed_user",
            message="대흉이 뭔가요? 제 인생도 끝난 걸까요",
            manual_lines=[7, 7, 7, 7, 7, 7],
            clients=clients,
        )

    assert res.hexagram_id == 1, "사연이 섞이면 상담이므로 괘를 뽑는다"


@pytest.mark.asyncio
async def test_위기_이후_새_세션에서도_괘를_뽑지_않는다():
    """래치는 사람 단위여야 한다.

    위기 판정은 세션을 닫으므로, 다음 발화는 새 세션으로 들어온다. 래치가 세션
    안에만 있으면 위기를 겪은 사람이 몇 분 뒤 다시 말을 걸었을 때 평범한 괘가
    그대로 나간다.
    """
    crisis_clients = {
        "safety": MockLLMDispatcher({"default": {
            "category": "BLOCK_CRISIS", "signals": ["위기"], "reason": "자해",
        }}),
    }

    async with AsyncSessionLocal() as session:
        res1 = await run_turn(
            session, user_id="latch_user",
            message="이제 그만하고 싶어요. 다 정리했습니다.",
            clients=crisis_clients,
        )
        assert res1.safety_category == "BLOCK_CRISIS"
        assert res1.is_final is True  # 세션이 닫힌다

        # 세션 ID 없이(= 새 세션으로) 다시 말을 건다. 스크리너는 NORMAL을 준다.
        res2 = await run_turn(
            session, user_id="latch_user",
            message="아까는 헛소리였고, 이직 얘기나 할까요?",
            clients={"safety": MockLLMDispatcher({"default": {"category": "NORMAL"}})},
        )

        assert res2.session_id != res1.session_id, "새 세션이어야 이 테스트가 의미가 있다"
        assert res2.safety_category == "BLOCK_CRISIS"
        assert res2.hexagram_id is None
        assert "109" in res2.user_facing_message


@pytest.mark.asyncio
async def test_다른_사용자는_래치에_걸리지_않는다(monkeypatch):
    from core.rag import RetrievedChunk

    async def mock_search(*args, **kwargs):
        return [RetrievedChunk(
            chunk_id="c", hexagram_id=1, line_number=None, source_type="guasa_comm",
            category="annotation", content="원문", content_ko="번역", similarity=0.7,
        )]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search)

    async with AsyncSessionLocal() as session:
        await run_turn(
            session, user_id="latch_user_a", message="다 끝내고 싶어요",
            clients={"safety": MockLLMDispatcher({"default": {"category": "BLOCK_CRISIS"}})},
        )

        res = await run_turn(
            session, user_id="latch_user_b", message="이직해야 할까요?",
            manual_lines=[7, 7, 7, 7, 7, 7],
            clients={
                "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
                "intake": MockLLMDispatcher({"default": {
                    "clarified_question": "이직해야 할까요?", "topic_category": "커리어",
                    "is_duplicate_question": False, "duplicate_session_ref": None,
                }}),
                "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "매핑"}}),
                "counsel": MockLLMDispatcher({"default": {
                    "message": "함께 살펴봅니다.", "needs_followup": True,
                    "followup_question": "무엇이 걸리시나요?", "is_final": False,
                }}),
            },
        )
        assert res.safety_category == "NORMAL"
        assert res.hexagram_id == 1


@pytest.mark.asyncio
async def test_래치_시간이_지나면_풀린다(monkeypatch):
    """창 밖의 오래된 위기까지 붙들지는 않는다."""
    from core.config import settings

    async with AsyncSessionLocal() as session:
        await run_turn(
            session, user_id="latch_user_old", message="다 끝내고 싶어요",
            clients={"safety": MockLLMDispatcher({"default": {"category": "BLOCK_CRISIS"}})},
        )

        # 창을 0으로 두면 세션 단위 래치만 남는다
        monkeypatch.setattr(settings, "CRISIS_LATCH_HOURS", 0)
        from agents.pipeline import _has_recent_crisis

        assert await _has_recent_crisis(session, "latch_user_old") is False


async def _seed_previous_reading(session, prev_id: str, user_id: str, hexagram_id: int = 5,
                                 summary: str = "이직 고민"):
    """지난번 상담(괘를 얻고 저널까지 남긴 세션)을 만들어 둔다."""
    from core.models.counsel import CounselSession, CounselTurn, JournalEntry

    session.add(CounselSession(
        id=prev_id, user_id=user_id, raw_question="이직해야 할까요?",
        clarified_question="이직해야 할까요?", status="completed",
    ))
    session.add(CounselTurn(
        session_id=prev_id, turn_number=1,
        original_hexagram_id=hexagram_id, transformed_hexagram_id=None, changing_lines=[],
        user_message="이직해야 할까요?", agent_response="그때의 상담 답변",
        needs_followup=False, is_final=True,
    ))
    if summary:
        session.add(JournalEntry(
            session_id=prev_id, summary=summary, key_insights="그때의 통찰",
        ))
    await session.commit()


def _dup_clients(prev_id: str, counsel_resp=None):
    from unittest.mock import AsyncMock  # noqa: F401  (호출부에서 patch에 쓴다)

    return {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "clarified_question": "이직해야 할까요?",
            "topic_category": "커리어/진로",
            "is_duplicate_question": True,
            "duplicate_session_ref": prev_id,
        }}),
        "counsel": MockLLMDispatcher({"default": counsel_resp or {
            "message": "그때의 괘를 다시 펼쳐 봅니다.",
            "needs_followup": True,
            "followup_question": "무엇이 달라졌나요?",
            "is_final": False,
        }}),
    }


@pytest.mark.asyncio
async def test_재삼독이면_새로_뽑지_않고_지난_괘를_물려받는다():
    import uuid
    from unittest.mock import AsyncMock, patch

    prev_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        await _seed_previous_reading(session, prev_id, "dup_user", hexagram_id=5)

        with patch("agents.pipeline._get_past_sessions", new_callable=AsyncMock) as past:
            past.return_value = [
                {"session_id": prev_id, "clarified_question": "이직해야 할까요?", "summary": "이직 고민"}
            ]
            res = await run_turn(
                session, user_id="dup_user", message="이직해야 할까요?",
                clients=_dup_clients(prev_id),
            )

        assert res.is_duplicate is True
        assert res.hexagram_id == 5, "지난번 괘를 그대로 이어받아야 한다"
        assert res.needs_followup is True
        assert res.is_final is False
        # 내부 식별자가 사용자 문장에 새어 나오면 안 된다
        assert prev_id not in res.user_facing_message
        # 지난번 괘와 그때의 요약을 보여준다
        assert "제5괘" in res.user_facing_message
        assert "이직 고민" in res.user_facing_message


@pytest.mark.asyncio
async def test_재삼독_이후_대화가_이어진다_같은_문구_반복_금지():
    """되묻기에 답하면 상담이 이어져야 한다.

    예전에는 괘 없는 턴이 남아 다음 턴이 다시 재삼독 분기로 들어갔고,
    사용자가 무슨 말을 하든 똑같은 안내가 무한히 반복됐다.
    """
    import uuid
    from unittest.mock import AsyncMock, patch

    prev_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        await _seed_previous_reading(session, prev_id, "dup_user2", hexagram_id=5)
        clients = _dup_clients(prev_id)

        with patch("agents.pipeline._get_past_sessions", new_callable=AsyncMock) as past:
            past.return_value = [
                {"session_id": prev_id, "clarified_question": "이직해야 할까요?", "summary": "이직 고민"}
            ]
            res1 = await run_turn(
                session, user_id="dup_user2", message="이직해야 할까요?", clients=clients,
            )
            res2 = await run_turn(
                session, counsel_session_id=res1.session_id, user_id="dup_user2",
                message="그때랑 크게 달라진 건 없어요.", clients=clients,
            )

        assert res2.user_facing_message != res1.user_facing_message, "같은 문구가 반복되면 안 된다"
        assert res2.is_duplicate is False, "두 번째 턴은 상담이지 재삼독 안내가 아니다"
        assert res2.hexagram_id == 5, "괘는 지난번 것 그대로여야 한다"
        assert res2.turn_number == 2
        assert "그때의 괘를 다시 펼쳐" in res2.user_facing_message


@pytest.mark.asyncio
async def test_지목된_세션에_괘가_없으면_정상적으로_뽑는다(monkeypatch):
    """보여줄 지난 괘가 없으면 막을 이유가 없다."""
    import uuid
    from unittest.mock import AsyncMock, patch

    from core.models.counsel import CounselSession
    from core.rag import RetrievedChunk

    async def mock_search(*args, **kwargs):
        return [RetrievedChunk(
            chunk_id="c", hexagram_id=1, line_number=None, source_type="guasa_comm",
            category="annotation", content="원문", content_ko="번역", similarity=0.7,
        )]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search)
    prev_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        # 괘 없이 되묻기만 하다 끝난 세션
        session.add(CounselSession(
            id=prev_id, user_id="dup_user3", raw_question="이직해야 할까요?", status="active",
        ))
        await session.commit()

        clients = _dup_clients(prev_id)
        clients["interpret"] = MockLLMDispatcher({"default": {"contextual_mapping": "매핑"}})

        with patch("agents.pipeline._get_past_sessions", new_callable=AsyncMock) as past:
            past.return_value = [
                {"session_id": prev_id, "clarified_question": "이직해야 할까요?", "summary": ""}
            ]
            res = await run_turn(
                session, user_id="dup_user3", message="이직해야 할까요?",
                manual_lines=[7, 7, 7, 7, 7, 7], clients=clients,
            )

        assert res.is_duplicate is False
        assert res.hexagram_id == 1, "보여줄 지난 괘가 없으면 정상적으로 뽑는다"


@pytest.mark.asyncio
async def test_후속턴은_같은_괘를_유지하고_다시_뽑지_않는다(monkeypatch):
    """세션이 이어지는 동안 괘가 바뀌면 안 된다 (재삼독 금지).

    후속 턴에서 cast_hexagram()을 새로 부르면 매 턴 다른 괘가 나오고,
    상담사는 A괘의 괘사를 들고 B괘 이야기를 하게 된다.
    """
    from core.rag import RetrievedChunk

    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=3, line_number=None, source_type="guasa_comm",
                category="annotation", content="원문", content_ko="번역", similarity=0.8,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

    # 후속 턴에서 괘를 다시 뽑으려 하면 즉시 실패시킨다
    def _no_recast(*args, **kwargs):
        raise AssertionError("후속 턴에서 cast_hexagram()이 호출되었습니다 — 괘를 다시 뽑고 있습니다")

    counsel_resp = {
        "message": "지금 상황을 함께 짚어봅니다.",
        "needs_followup": True,
        "followup_question": "무엇이 가장 걸리시나요?",
        "is_final": False,
    }
    mock_clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "clarified_question": "지금 시작해도 될지",
            "topic_category": "결단",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }}),
        "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "시작의 어려움"}}),
        "counsel": MockLLMDispatcher({"default": counsel_resp}),
    }

    async with AsyncSessionLocal() as session:
        # 3번 준괘(屯), 동효 1·5효로 고정해서 시작한다
        res1 = await run_turn(
            session,
            user_id="same_hex_user",
            message="지금 시작해도 될까요?",
            manual_lines=[9, 8, 8, 8, 6, 8],
            clients=mock_clients,
        )
        first_hex = res1.hexagram_id
        first_trans = res1.transformed_hexagram_id
        first_lines = res1.changing_lines

        monkeypatch.setattr("core.hexagram_engine.cast_single_line", _no_recast)

        for _ in range(3):
            res = await run_turn(
                session,
                counsel_session_id=res1.session_id,
                user_id="same_hex_user",
                message="조금 더 이야기하고 싶어요.",
                clients=mock_clients,
            )
            assert res.hexagram_id == first_hex
            assert res.transformed_hexagram_id == first_trans
            assert res.changing_lines == first_lines


@pytest.mark.asyncio
async def test_되묻기_이후_답변에서_괘가_실제로_도출된다(monkeypatch):
    """ASK로 세션이 먼저 생겨도, 이어지는 답변에서 intake·interpret이 돌아야 한다.

    세션 유무로 갈랐을 때는 이 턴이 해석 단계를 통째로 건너뛰고
    뽑은 적 없는 1번 괘로 상담이 나갔다.
    """
    from core.rag import RetrievedChunk

    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=2, line_number=None, source_type="guasa_comm",
                category="annotation", content="원문", content_ko="번역", similarity=0.8,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

    ask_client = MockLLMDispatcher({"default": {
        "category": "ASK",
        "ask": "어떤 일을 말씀하시는 걸까요?",
        "signals": [],
    }})
    mock_clients = {
        "safety": ask_client,
        "intake": MockLLMDispatcher({"default": {
            "clarified_question": "회사를 계속 다녀야 할지",
            "topic_category": "커리어/진로",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }}),
        "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "머무름과 떠남"}}),
        "counsel": MockLLMDispatcher({"default": {
            "message": "떠남과 머무름 사이에서 마음이 오가시는군요.",
            "needs_followup": True,
            "followup_question": "무엇이 가장 걸리시나요?",
            "is_final": False,
        }}),
    }

    async with AsyncSessionLocal() as session:
        res1 = await run_turn(
            session,
            user_id="ask_user",
            message="그것 때문에 요즘 계속 생각이 많아요",
            clients=mock_clients,
        )
        assert res1.safety_category == "ASK"
        assert res1.hexagram_id is None
        assert "어떤 일을 말씀하시는" in res1.user_facing_message

        # 사용자가 되물음에 답한다 -> 이번에는 괘가 나와야 한다
        mock_clients["safety"] = MockLLMDispatcher({"default": {"category": "NORMAL"}})
        res2 = await run_turn(
            session,
            counsel_session_id=res1.session_id,
            user_id="ask_user",
            message="회사를 계속 다닐지 고민이에요",
            manual_lines=[8, 8, 8, 8, 8, 8],  # 곤괘(2)
            clients=mock_clients,
        )

        assert res2.hexagram_id == 2, "되묻기 이후 턴에서 괘가 실제로 도출되어야 한다"
        assert "떠남과 머무름" in res2.user_facing_message


@pytest.mark.asyncio
async def test_스크리닝_실패시_괘도_안뽑고_범위밖_문구도_안나간다():
    """통신 장애가 사용자에게 의료·법률 안내로 둔갑하면 안 된다."""

    class FailingLLM:
        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            raise ConnectionError("API 연결 실패")

    async with AsyncSessionLocal() as session:
        res = await run_turn(
            session,
            user_id="err_user",
            message="이직해야 할까요?",
            clients={"safety": FailingLLM()},
        )

        from agents.safety import get_template

        assert res.safety_category == "ERROR"
        assert res.hexagram_id is None          # 괘를 뽑지 않는다
        assert res.is_final is False            # 세션을 닫지 않는다
        assert res.user_facing_message == get_template("error")
        assert "변호사" not in res.user_facing_message
        assert "109" not in res.user_facing_message
        for label in ("BLOCK_CRISIS", "BLOCK_SCOPE", "ERROR"):
            assert label not in res.user_facing_message



@pytest.mark.asyncio
async def test_후속턴에서도_해설을_다시_찾고_괘로_좁힌다(monkeypatch):
    """설계 원칙 3 — RAG는 1회 검색으로 끝나지 않는다.

    첫 검색은 정리된 첫 질문으로 돈다. 후속 턴에 검색 경로가 없으면 상담사는
    세션 내내 그 한 번의 결과만 들고 이야기하게 되고, "왜 그렇게 보시나요"에
    답할 근거가 첫 턴 안에 갇힌다.

    좁히지 않은 검색이 한 번도 없어야 한다는 것도 같이 본다. 괘를 지정하지 않으면
    64괘 전체에서 끌어와 지금 뽑은 괘와 무관한 해설이 답변에 섞인다.
    """
    from core.rag import RetrievedChunk

    검색된_괘 = []

    async def mock_search_chunks(session, query, *, hexagram_id, **kwargs):
        검색된_괘.append(hexagram_id)
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=hexagram_id, line_number=None,
                source_type="guasa_comm", category="annotation",
                content="需者飮食之道也", content_ko="때를 기다리는 자리입니다.", similarity=0.8,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)
    monkeypatch.setattr("core.rag.search_balanced", mock_search_chunks)

    mock_clients = {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "clarified_question": "지금 시작해도 될지",
            "topic_category": "결단",
            "is_duplicate_question": False,
            "duplicate_session_ref": None,
        }}),
        "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "시작의 어려움"}}),
        # 해설을 받기 전에는 더 찾자고 하고, 받은 뒤에 답한다.
        # 키는 주입된 검색 결과에만 나오는 문자열이어야 한다 — "추가로 찾아본 해설"은
        # 프롬프트 파일에 설명으로도 들어 있어 첫 호출부터 매치된다.
        "counsel": MockLLMDispatcher({
            '질의: "기다림의 뜻"': {
                "message": "찾아본 해설로 보면 지금은 기다림의 자리입니다.",
                "needs_followup": True, "followup_question": "무엇이 걸리시나요?",
                "is_final": False, "search_query": None,
            },
            "default": {
                "message": "", "needs_followup": True, "followup_question": None,
                "is_final": False, "search_query": "기다림의 뜻",
            },
        }),
    }

    async with AsyncSessionLocal() as session:
        res1 = await run_turn(
            session,
            user_id="research_user",
            message="지금 시작해도 될까요?",
            manual_lines=[9, 8, 8, 8, 6, 8],
            clients=mock_clients,
        )
        첫턴_검색수 = len(검색된_괘)

        res2 = await run_turn(
            session,
            counsel_session_id=res1.session_id,
            user_id="research_user",
            message="왜 그렇게 보시나요?",
            clients=mock_clients,
        )

    assert len(검색된_괘) > 첫턴_검색수, "후속 턴에서 다시 찾지 않았다"
    assert all(h is not None for h in 검색된_괘), "괘로 좁히지 않은 검색이 있다"
    assert "기다림의 자리" in res2.user_facing_message, "다시 찾은 해설이 답변에 닿지 않았다"
    assert "需者飮食之道也" not in res2.user_facing_message
