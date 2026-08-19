"""후속 턴 반증 하네스(`scripts/compare_hexagram_effect_turns.py`)의 자가 검증.

이 하네스가 재는 것은 딱 하나다 — 매핑·근거 주석이 **후속 턴에서도 살아 있는가.**
그걸 재려면 하네스 자신의 "질문" 필드가 턴 번호마다 누적돼야 한다(그래야
measure_boilerplate가 지금까지 나온 사연 전체를 상용구 후보에서 뺀다). 이 성질이
깨지면 이전 턴에서 상담사가 그대로 옮긴 사연 어절이 "상투구"로 잘못 잡힌다.

`근거_텍스트()`는 DB 없이 재고, 세션 진행(턴 키·누적 질문·안전 이탈 시 중단)은
Mock LLM으로 실제 파이프라인(`run_turn`)을 태워 잰다 — Postgres가 필요하다.
"""

from types import SimpleNamespace

import pytest

from scripts.compare_hexagram_effect_turns import STORY_TURNS, 근거_텍스트, 세션_한판


def test_근거_텍스트는_확정_근거와_주석을_합친다():
    res = SimpleNamespace(
        raw_text="본괘: 제39괘 수산건\n주 해석 근거:\n- [2효] 왕의 신하로서…",
        evidences=[
            {"content": "어려움을 무릅쓰는 것은 제 한 몸의 이해를 넘어선 일이다."},
            {"content": ""},  # 빈 내용은 그대로 이어붙여도 무방하다 — join이 걸러낸다
        ],
    )
    text = 근거_텍스트(res)
    assert "수산건" in text
    assert "어려움을 무릅쓰는 것" in text


def test_근거_텍스트는_근거가_없어도_터지지_않는다():
    res = SimpleNamespace(raw_text=None, evidences=None)
    assert 근거_텍스트(res) == ""


class MockLLMDispatcher:
    """`tests/test_agents_pipeline.py`와 같은 방식의 역할별 Mock."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls = []

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.calls.append({"user": user, "system": system})
        for key, resp in self.responses.items():
            if key in system or key in user:
                return resp
        return self.responses.get("default", {})


def _clients():
    counsel_responses = {
        "default": {
            "message": "그 마음을 조금 더 들여다볼까요?",
            "needs_followup": True, "followup_question": None, "is_final": False,
        }
    }
    return {
        "safety": MockLLMDispatcher({"default": {"category": "NORMAL"}}),
        "intake": MockLLMDispatcher({"default": {
            "clarified_question": STORY_TURNS[0][0],
            "topic_category": "커리어/진로",
            "is_duplicate_question": False, "duplicate_session_ref": None,
        }}),
        "interpret": MockLLMDispatcher({"default": {"contextual_mapping": "매핑"}}),
        "counsel": MockLLMDispatcher(counsel_responses),
        "journal": MockLLMDispatcher({"default": {
            "summary": "요약", "key_insights": "통찰", "action_items": None,
        }}),
    }


@pytest.mark.asyncio
async def test_턴마다_질문이_누적되고_근거가_세_턴_모두에_있다(monkeypatch):
    """이게 이 하네스의 존재 이유다.

    3턴을 돌리면 1턴의 "질문"은 1턴 발화뿐이어야 하고, 3턴의 "질문"은 1~3턴 발화를
    전부 담아야 한다. 이 누적이 없으면 measure_boilerplate가 1턴에서 상담사가
    되짚은 사연 어절을 후속 턴의 "상투구"로 오진한다.
    """
    from core.rag import RetrievedChunk

    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=39, line_number=None, source_type="guasa_comm",
                category="annotation", content="원문", content_ko="번역", similarity=0.8,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

    결과 = await 세션_한판(0, "수산건 1·2효", [6, 6, 7, 8, 7, 8], _clients())

    assert set(결과.keys()) == {1, 2, 3}
    for turn_idx, row in 결과.items():
        assert row["배치"] == "수산건 1·2효"
        assert row["근거"].strip(), f"{turn_idx}턴에 확정 근거가 없다"

    assert 결과[1]["질문"] == STORY_TURNS[0][0]
    assert 결과[2]["질문"] == f"{STORY_TURNS[0][0]}\n{STORY_TURNS[0][1]}"
    assert 결과[3]["질문"] == "\n".join(STORY_TURNS[0])


@pytest.mark.asyncio
async def test_안전_판정이_튀면_그_턴부터_결과가_끊긴다(monkeypatch):
    """정상 범위(NORMAL·CAUTION)를 벗어난 턴은 괘 상담이 아니라 안내문이 나간다.

    그 턴을 근거 도달도에 넣으면 안내문을 답변으로 채점하게 된다.
    """
    from core.rag import RetrievedChunk

    async def mock_search_chunks(*args, **kwargs):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=39, line_number=None, source_type="guasa_comm",
                category="annotation", content="원문", content_ko="번역", similarity=0.8,
            )
        ]

    monkeypatch.setattr("agents.interpret.search_balanced", mock_search_chunks)

    clients = _clients()
    # 2턴째 안전 판정이 ASK로 튀도록 두 번째 응답을 넣는다. safety는 role별로
    # 한 클라이언트를 세 턴 내내 재사용하므로, 첫 호출은 NORMAL을 내고 이후는
    # ASK를 내게 호출 횟수로 가른다.
    safety = clients["safety"]

    def _safety_by_call(user, *, system="", **kwargs):
        safety.calls.append({"user": user, "system": system})
        if len(safety.calls) == 1:
            return {"category": "NORMAL"}
        return {"category": "ASK", "ask": "조금 더 말씀해 주시겠어요?"}

    safety.complete_json = _safety_by_call

    결과 = await 세션_한판(0, "수산건 1·2효", [6, 6, 7, 8, 7, 8], clients)

    assert set(결과.keys()) == {1}, "ASK로 튄 2턴부터는 결과에 없어야 한다"
