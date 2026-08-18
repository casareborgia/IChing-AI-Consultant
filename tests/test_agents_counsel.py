"""상담 에이전트 단위 테스트 (네트워크 없음)."""

import pytest

from agents.counsel import MAX_RAG_SEARCHES, MAX_TURNS_LIMIT, run_counsel_turn
from core.rag import RetrievedChunk
from schemas.counsel import EvidenceItem, HexagramInterpretationSchema

INTERP = HexagramInterpretationSchema(
    original_hexagram_id=1,
    transformed_hexagram_id=None,
    changing_lines=[],
    raw_text="본괘: 제1괘 중천건\n주 해석 근거:\n- 본괘 괘사: 크게 형통하고 곧게 함이 이롭다.",
    contextual_mapping="새로 시작하려는 마음",
)


class AlwaysFailLLM:
    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        raise ConnectionError("API 연결 실패")


class NeverEndsLLM:
    """끝낼 생각이 없는 모델. 상한이 없으면 세션이 끝나지 않는다."""

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        return {
            "message": "조금 더 이야기해 볼까요?",
            "needs_followup": True,
            "followup_question": "무엇이 가장 걸리시나요?",
            "is_final": False,
        }


@pytest.mark.asyncio
async def test_턴_상한에_닿으면_모델이_뭐라_하든_마무리된다():
    res = await run_counsel_turn(
        "계속 이야기하고 싶어요", INTERP, turn_number=MAX_TURNS_LIMIT, client=NeverEndsLLM()
    )
    assert res.is_final is True
    assert res.needs_followup is False
    assert res.followup_question is None


@pytest.mark.asyncio
async def test_LLM이_실패해도_턴_상한은_적용된다():
    """상한 판단이 try 안에 있으면 호출 실패 시 상한이 통째로 무시된다.

    그러면 모델이 계속 죽는 동안 세션이 13턴, 14턴으로 끝없이 이어진다 —
    막으려던 무한 루프가 실패 경로로 되살아난다.
    """
    res = await run_counsel_turn(
        "계속 이야기하고 싶어요", INTERP, turn_number=MAX_TURNS_LIMIT, client=AlwaysFailLLM()
    )
    assert res.is_final is True
    assert res.needs_followup is False


@pytest.mark.asyncio
async def test_상한_전에는_실패해도_대화를_잇는다():
    res = await run_counsel_turn("...", INTERP, turn_number=2, client=AlwaysFailLLM())
    assert res.is_final is False
    assert res.needs_followup is True


class SeparatedQuestionLLM:
    """질문을 별도 필드에만 담는 모델. 실제로 이렇게 나왔다."""

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        return {
            "message": "지금 마음이 두 갈래로 나뉘어 있는 것 같습니다. 그 망설임은 성급함이 아니라 신중함일 수 있어요.",
            "needs_followup": True,
            "followup_question": "무엇이 가장 마음에 걸리시나요?",
            "is_final": False,
        }


class InlineQuestionLLM:
    """질문을 답변 안에 자연스럽게 넣는 모델 (바람직한 형태)."""

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        return {
            "message": "그 망설임은 신중함일 수 있어요. 지금 가장 걸리는 건 무엇인가요?",
            "needs_followup": True,
            "followup_question": "지금 가장 걸리는 건 무엇인가요?",
            "is_final": False,
        }


@pytest.mark.asyncio
async def test_되묻기가_사용자_문장_안에_반드시_들어간다():
    """followup_question은 화면에 나가지 않는다. message에 없으면 되묻기가 사라진다."""
    res = await run_counsel_turn("...", INTERP, turn_number=1, client=SeparatedQuestionLLM())
    assert "?" in res.message
    assert "무엇이 가장 마음에 걸리시나요?" in res.message


@pytest.mark.asyncio
async def test_이미_질문이_있으면_덧붙이지_않는다():
    res = await run_counsel_turn("...", INTERP, turn_number=1, client=InlineQuestionLLM())
    assert res.message.count("지금 가장 걸리는 건 무엇인가요?") == 1


@pytest.mark.asyncio
async def test_마무리_턴에는_질문을_붙이지_않는다():
    class ClosingLLM:
        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            return {
                "message": "스스로 정리하셨다니 다행입니다. 언제든 다시 오셔도 좋습니다.",
                "needs_followup": False,
                "followup_question": "무엇이 가장 걸리시나요?",
                "is_final": True,
            }

    res = await run_counsel_turn("고맙습니다", INTERP, turn_number=3, client=ClosingLLM())
    assert "무엇이 가장 걸리시나요?" not in res.message


@pytest.mark.asyncio
async def test_CAUTION_문구는_한_번만_붙는다():
    res = await run_counsel_turn(
        "요즘 너무 지쳐요", INTERP, turn_number=1, client=NeverEndsLLM(), caution_append=True
    )
    assert "참고 안내" in res.message
    assert res.message.count("참고 안내") == 1


def test_금지_목록이_프롬프트와_코드에서_어긋나지_않는다():
    """코드가 막는 단어와 프롬프트가 금지한 단어가 갈라지면 안 된다.

    안전 문구를 코드에 복사해 뒀다가 프롬프트 파일과 갈라진 전례가 있었다.
    """
    from pathlib import Path
    from agents.counsel import DIAGNOSIS_TERMS

    md = (Path(__file__).resolve().parent.parent / "prompts" / "counsel.md").read_text(encoding="utf-8")
    빠진_것 = [w for w in DIAGNOSIS_TERMS if w not in md]
    assert not 빠진_것, f"코드는 막는데 프롬프트에 없는 단어: {빠진_것}"


@pytest.mark.asyncio
async def test_진단성_표현이_나오면_다시_쓰게_한다():
    class DiagnosisThenCleanLLM:
        def __init__(self):
            self.calls = 0

        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            self.calls += 1
            if self.calls == 1:
                return {"message": "우울증인지 아닌지는 제가 판단할 수 없습니다. 어떠신가요?",
                        "needs_followup": True, "followup_question": "어떠신가요?", "is_final": False}
            return {"message": "그 이름을 붙이는 일은 전문가의 몫입니다. 언제부터였나요?",
                    "needs_followup": True, "followup_question": "언제부터였나요?", "is_final": False}

    llm = DiagnosisThenCleanLLM()
    res = await run_counsel_turn("제가 우울증일까요?", INTERP, turn_number=1, client=llm)
    assert llm.calls == 2, "한 번은 다시 쓰게 해야 한다"
    assert "우울증" not in res.message


@pytest.mark.asyncio
async def test_재생성도_실패하면_안전한_문장으로_바꾼다():
    class AlwaysDiagnosisLLM:
        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            return {"message": "우울증일 수 있습니다.", "needs_followup": True,
                    "followup_question": "어떠신가요?", "is_final": False}

    res = await run_counsel_turn("제가 우울증일까요?", INTERP, turn_number=1, client=AlwaysDiagnosisLLM())
    assert "우울증" not in res.message
    assert "전문가의 몫" in res.message


# ── 대화 중 재검색 (Agentic RAG, 설계 원칙 3) ─────────────────────────────


def _chunk(ko="때를 기다리는 것이 이롭다는 뜻입니다.", hanja="需者飮食之道也"):
    return RetrievedChunk(
        chunk_id="c1", hexagram_id=5, line_number=3, source_type="line_comm",
        category="annotation", content=hanja, content_ko=ko, similarity=0.82,
    )


class SearchingLLM:
    """근거가 모자라다며 재검색을 요청하는 모델.

    `requests`번 검색을 요청한 뒤 답을 쓴다. 프롬프트를 모아두므로 검색 결과가
    실제로 다음 호출에 들어갔는지 확인할 수 있다.
    """

    def __init__(self, requests: int = 1):
        self.requests = requests
        self.prompts = []

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.prompts.append(user)
        if len(self.prompts) <= self.requests:
            return {"message": "", "needs_followup": True, "followup_question": None,
                    "is_final": False, "search_query": f"질의{len(self.prompts)}"}
        return {"message": "찾아본 해설로 보면 지금은 기다림의 자리입니다.",
                "needs_followup": True, "followup_question": "무엇이 가장 걸리시나요?",
                "is_final": False, "search_query": None}


@pytest.mark.asyncio
async def test_근거가_모자라면_다시_찾아_그_해설로_답한다():
    """첫 검색은 정리된 첫 질문으로 돌았다. 대화가 옮겨가면 거기에 답이 없다."""
    calls = []

    async def retrieve(query):
        calls.append(query)
        return [_chunk()]

    llm = SearchingLLM(requests=1)
    # 근거를 묻는 말이 아니다 — 코드가 먼저 찾는 경로를 타지 않고, 모델이 스스로
    # 더 찾겠다고 한 경우만 본다.
    res = await run_counsel_turn(
        "관계 이야기인 줄 알았는데 시기의 문제인 것 같아요.", INTERP, client=llm, retrieve=retrieve
    )

    assert calls == ["질의1"]
    assert len(llm.prompts) == 2, "검색 후 다시 물어야 한다"
    assert "때를 기다리는 것이 이롭다" in llm.prompts[1], "찾은 해설이 다음 호출에 들어가야 한다"
    assert "기다림의 자리" in res.message


@pytest.mark.asyncio
async def test_재검색은_상한을_넘지_않는다():
    """'조금만 더 찾아보자'가 반복되면 한 턴이 무한정 길어진다."""
    calls = []

    async def retrieve(query):
        calls.append(query)
        return [_chunk()]

    llm = SearchingLLM(requests=99)  # 끝없이 더 찾자고 한다
    res = await run_counsel_turn("왜요?", INTERP, client=llm, retrieve=retrieve)

    assert len(calls) == MAX_RAG_SEARCHES
    assert len(llm.prompts) == MAX_RAG_SEARCHES + 1
    assert res.message.strip(), "상한에 닿아도 빈 답변이 나가면 안 된다"


@pytest.mark.asyncio
async def test_괘가_없는_턴에는_다시_찾지_않는다():
    """주역 자체를 묻는 턴에는 좁힐 괘가 없다. 좁히지 않은 검색은 하지 않는다."""
    llm = SearchingLLM(requests=99)
    res = await run_counsel_turn("대흉이 무슨 뜻인가요?", None, client=llm, retrieve=None)

    assert len(llm.prompts) == 1
    assert res.message.strip()


@pytest.mark.asyncio
async def test_다시_찾은_해설도_한글만_넘어간다():
    """한문은 근거 보존용이지 모델에게 줄 값이 아니다. 번역이 비면 건너뛴다."""
    async def retrieve(query):
        return [_chunk(), _chunk(ko="", hanja="雲上於天需")]

    llm = SearchingLLM(requests=1)
    await run_counsel_turn("왜요?", INTERP, client=llm, retrieve=retrieve)

    주입된_해설 = llm.prompts[1]
    assert "需者飮食之道也" not in 주입된_해설
    assert "雲上於天需" not in 주입된_해설, "번역이 비었다고 한문으로 대신하면 안 된다"
    assert "때를 기다리는 것이 이롭다" in 주입된_해설


@pytest.mark.asyncio
async def test_찾은_해설이_없으면_더_찾지_않는다():
    calls = []

    async def retrieve(query):
        calls.append(query)
        return []

    llm = SearchingLLM(requests=99)
    res = await run_counsel_turn("왜요?", INTERP, client=llm, retrieve=retrieve)

    assert len(calls) == 1, "같은 괘 안에서 빈 결과가 나오면 질의를 바꿔도 나아지지 않는다"
    assert "찾은 해설이 없습니다" in llm.prompts[1]
    assert res.message.strip()


class NoSearchLLM:
    """`search_query`를 쓸 줄 모르는 모델. 로컬 gemma4가 실제로 그랬다."""

    def __init__(self):
        self.prompts = []

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.prompts.append(user)
        return {"message": "지금은 기다림의 자리로 봅니다.", "needs_followup": True,
                "followup_question": "무엇이 걸리시나요?", "is_final": False}


@pytest.mark.asyncio
async def test_근거를_물으면_모델이_요청하지_않아도_찾는다():
    """프롬프트에 '근거를 물으면 반드시 찾으라'고 적어도 모델은 안 찾았다.

    여섯 턴 중 0회였다. 근거 투명성이 이 앱의 차별점인데 확률에 맡길 수 없어
    코드가 붙든다 — 진단어를 코드로 옮긴 것과 같은 판단이다.
    """
    calls = []

    async def retrieve(query):
        calls.append(query)
        return [_chunk()]

    llm = NoSearchLLM()
    history = [
        {"role": "user", "message": "이직을 할지 고민이에요"},
        {"role": "counselor", "message": "지금은 때를 살피는 자리로 보입니다."},
    ]
    res = await run_counsel_turn(
        "왜 그렇게 보시나요?", INTERP, conversation_history=history,
        client=llm, retrieve=retrieve,
    )

    assert len(calls) == 1
    assert calls[0] == "지금은 때를 살피는 자리로 보입니다.", (
        "근거를 대야 할 대상은 직전에 상담사가 한 말이다. "
        "'왜 그렇게 보시나요'로 검색하면 의미 검색에 넣을 것이 없다"
    )
    assert "때를 기다리는 것이 이롭다" in llm.prompts[0], "찾은 해설이 첫 호출부터 들어가야 한다"
    assert res.message.strip()


@pytest.mark.asyncio
async def test_평범한_발화에는_강제로_찾지_않는다():
    """매 턴 찾으면 호출이 배로 늘고 지연도 그만큼 는다."""
    calls = []

    async def retrieve(query):
        calls.append(query)
        return [_chunk()]

    llm = NoSearchLLM()
    await run_counsel_turn("요즘 일이 손에 안 잡혀요.", INTERP, client=llm, retrieve=retrieve)

    assert calls == []
    assert len(llm.prompts) == 1


@pytest.mark.asyncio
async def test_코드가_먼저_찾은_것도_상한에_포함된다():
    calls = []

    async def retrieve(query):
        calls.append(query)
        return [_chunk()]

    llm = SearchingLLM(requests=99)  # 코드가 한 번 찾은 뒤에도 계속 더 찾자고 한다
    await run_counsel_turn("무슨 근거로 그렇게 보시나요?", INTERP, client=llm, retrieve=retrieve)

    assert len(calls) == MAX_RAG_SEARCHES, "강제 검색이 상한 밖에 있으면 상한이 무의미해진다"


class PromptCaptureLLM:
    """프롬프트를 붙들어 두는 대역. 무엇이 모델 손에 들어갔는지를 본다."""

    def __init__(self):
        self.prompts = []

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.prompts.append(user)
        return {
            "message": "그 마음을 조금 더 들여다볼까요?",
            "needs_followup": True,
            "followup_question": None,
            "is_final": False,
            "search_query": None,
        }


@pytest.mark.asyncio
async def test_매핑이_비면_상황_매핑_절이_통째로_빠진다():
    """후속 턴에서 이 자리에 사용자의 사연이 들어가던 일이 있었다.

    상담사는 "[상황 매핑 초안]"이라는 이름표가 붙은 내담자의 사연을 괘의 해석으로
    알고 읽었다. 이제 매핑이 없으면 절 자체를 내지 않는다 — 머리만 남겨 빈 절을
    내보내도 모델이 바로 위 대화에서 그 자리를 메우기 때문이다.
    """
    llm = PromptCaptureLLM()
    빈매핑 = INTERP.model_copy(update={"contextual_mapping": "   "})

    await run_counsel_turn("사람 때문에 남는 게 맞을까요", 빈매핑, turn_number=2, client=llm)

    prompt = llm.prompts[0]
    assert "[상황 매핑 초안]" not in prompt
    assert "주 해석 근거" in prompt, "확정 근거는 그대로 가야 한다"


@pytest.mark.asyncio
async def test_재검색으로_붙인_주석만_근거로_돌려준다():
    """화면의 근거 패널이 이 값을 받는다.

    찾기만 하고 프롬프트에 못 넣은 것, 번역이 빈 것은 답변에 영향을 준 적이 없으므로
    근거가 아니다. 그런 것을 근거라고 보여주면 패널이 거짓말을 한다.
    """
    async def retrieve(query: str):
        return [
            RetrievedChunk(
                chunk_id="c1", hexagram_id=39, line_number=2, source_type="line_comm",
                category="annotation", content="원문",
                content_ko="왕의 신하가 어려움 속에 애쓰는 것은 제 몸을 위한 일이 아니다.",
                similarity=0.8,
            ),
            RetrievedChunk(
                chunk_id="c2", hexagram_id=39, line_number=2, source_type="benui_line",
                category="annotation", content="원문", content_ko="   ", similarity=0.7,
            ),
        ]

    res = await run_counsel_turn(
        "왜 그렇게 보시나요", INTERP,
        conversation_history=[{"role": "counselor", "message": "지금은 나아갈 때가 아니라고 봅니다."}],
        turn_number=2, client=PromptCaptureLLM(), retrieve=retrieve,
    )

    assert [e.source_title for e in res.evidences] == ["효사 주석(2효)"]
    assert res.evidences[0].hexagram_id == 39
    assert res.evidences[0].line_number == 2


@pytest.mark.asyncio
async def test_재검색이_없는_턴은_근거가_비어_있다():
    """근거가 없으면 없다고 해야 한다. 화면은 이때 패널을 띄우지 않는다."""
    res = await run_counsel_turn("조금 더 이야기하고 싶어요", INTERP, turn_number=2,
                                 client=PromptCaptureLLM())
    assert res.evidences == []


@pytest.mark.asyncio
async def test_근거_주석이_상담사_프롬프트에_들어간다():
    """예전에는 해석 에이전트가 검색한 주석이 상담사까지 오지 않았다.

    매핑 초안을 만드는 데만 쓰고 버렸고(파이프라인이 받아놓고 넘기지 않았다),
    상담사 손에는 압축된 효사 한 줄만 남았다. 풀 것이 없으면 모델은 괘 이름의
    통념으로 물러나고, 통념은 여러 괘가 공유하므로 어느 괘를 뽑아도 같은 말이 나온다.
    """
    llm = PromptCaptureLLM()
    with_evidence = INTERP.model_copy(update={"evidences": [
        EvidenceItem(
            source_type="line_comm", source_title="효사 주석(2효)",
            content="어려움을 무릅쓰는 것은 제 한 몸의 이해를 넘어선 일이기 때문이다.",
            hexagram_id=39, line_number=2,
        ),
        EvidenceItem(
            source_type="guasa_comm", source_title="괘사 주석",
            content="갈 수 있는 방향과 갈 수 없는 방향을 가리는 것이 이 괘의 일이다.",
            hexagram_id=39, line_number=None,
        ),
    ]})

    await run_counsel_turn("어떻게 보아야 할까요", with_evidence, turn_number=1, client=llm)

    prompt = llm.prompts[0]
    assert "[근거 주석 (한글)]" in prompt
    assert "제 한 몸의 이해를 넘어선 일" in prompt
    assert prompt.index("효사 주석(2효)") < prompt.index("괘사 주석"), "초점 효 주석이 앞에 와야 한다"
    assert prompt.index("[근거 주석") < prompt.index("[상황 매핑 초안]")


@pytest.mark.asyncio
async def test_근거_주석이_없으면_그_블록도_내지_않는다():
    llm = PromptCaptureLLM()
    await run_counsel_turn("어떻게 보아야 할까요", INTERP, turn_number=1, client=llm)
    assert "[근거 주석" not in llm.prompts[0]
