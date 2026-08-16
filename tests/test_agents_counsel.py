"""상담 에이전트 단위 테스트 (네트워크 없음)."""

import pytest

from agents.counsel import MAX_TURNS_LIMIT, run_counsel_turn
from schemas.counsel import HexagramInterpretationSchema

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
