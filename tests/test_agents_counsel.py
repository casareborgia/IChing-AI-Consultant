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


@pytest.mark.asyncio
async def test_CAUTION_문구는_한_번만_붙는다():
    res = await run_counsel_turn(
        "요즘 너무 지쳐요", INTERP, turn_number=1, client=NeverEndsLLM(), caution_append=True
    )
    assert "참고 안내" in res.message
    assert res.message.count("참고 안내") == 1
