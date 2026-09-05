# -*- coding: utf-8 -*-
"""DivinationChatEngine 및 5턴 소크라테스식 코칭 상담 엔진 단위 테스트."""

import pytest
from agents.divination_chat_engine import DivinationChatEngine, adapt_to_report_payload
from agents.counsel import MAX_TURNS_LIMIT, run_counsel_turn
from schemas.counsel import HexagramInterpretationSchema


INTERP_SAMPLE = HexagramInterpretationSchema(
    original_hexagram_id=49,
    transformed_hexagram_id=55,
    changing_lines=[5],
    raw_text="본괘: 제49괘 택화혁\n지괘: 제55괘 뇌화풍\n동효: 5효\n주 해석 근거:\n- 본괘 구오: 대인이 표범처럼 변하니 점치지 않아도 믿음이 있다.",
    contextual_mapping="낡은 방식을 버리고 새로운 조직 문화를 정착시키려는 시도",
)


def test_turn_number_calculation():
    """상담사 메시지 수에 따라 턴 번호가 1~5로 정확히 산정되는지 확인."""
    engine = DivinationChatEngine()
    
    # 0개 상담사 메시지 -> 1턴
    history_0 = []
    assert engine.get_next_turn_number(history_0) == 1

    # 1개 상담사 메시지 -> 2턴
    history_1 = [
        {"role": "user", "message": "안녕하세요"},
        {"role": "counselor", "message": "반갑습니다. 어떤 고민이 있으신가요?"}
    ]
    assert engine.get_next_turn_number(history_1) == 2

    # 4개 상담사 메시지 -> 5턴 (마지막 턴)
    history_4 = [
        {"role": "counselor", "message": "1"},
        {"role": "counselor", "message": "2"},
        {"role": "counselor", "message": "3"},
        {"role": "counselor", "message": "4"},
    ]
    assert engine.get_next_turn_number(history_4) == 5


def test_adapt_to_report_payload():
    """다양한 입력 형태가 DivinationChatEngine 규격의 report_payload로 올바르게 어댑팅되는지 확인."""
    raw_report = {
        "hexagram_casting": {
            "original_name_full": "제49괘 택화혁",
            "transformed_name_full": "제55괘 뇌화풍",
            "original_summary": "변혁과 개혁의 상징",
        },
        "focus_and_body_use": {
            "primary_target_name": "택화혁 괘 구오 효사",
            "rule_description": "동효 1개 채택",
        },
        "section2_action": {
            "hanja_text": "大人虎變 未占有孚",
            "interpretation": "단단한 내면의 신뢰를 먼저 구축해야 합니다.",
        },
        "final_summary": "성급함을 피하고 내실을 바로잡으십시오."
    }
    
    payload = adapt_to_report_payload(report_data=raw_report)
    assert payload["derivation_data"]["original_hexagram"]["name"] == "제49괘 택화혁"
    assert payload["derivation_data"]["resulting_hexagram"]["name"] == "제55괘 뇌화풍"
    assert "구오" in payload["judgment_rules"]["target_focus"]
    assert "大人虎變" in payload["judgment_rules"]["local_target_text"]
    assert len(payload["counseling_agenda"]) >= 1


def test_generate_chat_prompt_structure():
    """5단계 Socratic 모델의 프롬프트가 system_prompt와 user_prompt로 완벽히 생성되는지 확인."""
    engine = DivinationChatEngine()
    payload = adapt_to_report_payload(
        interpretation_raw_text=INTERP_SAMPLE.raw_text,
        contextual_mapping=INTERP_SAMPLE.contextual_mapping,
    )
    
    prompts = engine.generate_chat_prompt(
        conversation_history=[],
        user_question="부서원들과의 소통 방식에서 갈등이 큽니다.",
        report_payload=payload,
        turn_num_override=1,
    )
    
    sys_prompt = prompts["system_prompt"]
    user_prompt = prompts["user_prompt"]
    
    assert "Neo-Confucian I-Ching counseling master" in sys_prompt
    assert "5-step Socratic Counseling model" in sys_prompt
    assert "TURN 1 [First Greeting & Firestarter]" in sys_prompt
    assert "TURN 5 [Action Pledge Call - Hard Termination]" in sys_prompt
    assert "Korean" in sys_prompt
    
    assert "<divination_context>" in user_prompt
    assert "Turn 1 of 5" in user_prompt
    assert "부서원들과의 소통 방식" in user_prompt


def test_critique_and_refinement_prompts():
    """자가 비판(Critique) 및 정밀화(Refinement) 프롬프트 4 Quality Gates 준수 확인."""
    engine = DivinationChatEngine()
    payload = adapt_to_report_payload(
        interpretation_raw_text=INTERP_SAMPLE.raw_text,
    )
    
    draft = "현재 택화혁 괘의 기류 속에 직면해 있습니다. 무엇이 고민이신가요?"
    critique = engine.generate_critique_prompt(draft, [], payload, turn_num_override=1)
    
    assert "[4 Quality Gates of Socratic Dialogue]" in critique
    assert "[Socratic Turn Alignment]" in critique
    assert "[No Clichés or Repetitions]" in critique
    assert "[Proportional & Concise Length]" in critique
    assert "[Single Profound Question]" in critique
    
    refinement = engine.generate_refinement_prompt(draft, "클리셰 발견: ~의 기류 속에 제거 필요", [], payload, turn_num_override=1)
    assert "master scribe" in refinement
    assert "Auditor's Critique" in refinement


@pytest.mark.asyncio
async def test_5턴_하드_터미네이션_보장():
    """5턴째에는 후속 질문 없이 is_final=True, needs_followup=False로 종료되는지 확인."""
    class DummyLLM:
        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            return {
                "message": "오늘의 성찰을 마음에 새기고 실천으로 나아가시길 바랍니다.",
                "needs_followup": True,
                "followup_question": "또 궁금한 점이 있으신가요?",
                "is_final": False,
            }

    res = await run_counsel_turn(
        "오늘부터 매일 아침 경청하겠습니다.",
        INTERP_SAMPLE,
        turn_number=5,
        client=DummyLLM(),
    )
    
    assert res.is_final is True
    assert res.needs_followup is False
    assert res.followup_question is None
    assert MAX_TURNS_LIMIT == 5


@pytest.mark.asyncio
async def test_refinement_loop_적용_테스트():
    """enable_refinement_loop=True 일 때 정밀화된 문장으로 최종 반환되는지 확인."""
    class MockRefiningLLM:
        def __init__(self):
            self.call_count = 0

        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            return {
                "message": "초안: 택화혁의 기류 속에 직면해 있습니다. 무엇이 걸리시나요?",
                "needs_followup": True,
                "followup_question": "무엇이 걸리시나요?",
                "is_final": False,
            }

        def complete(self, prompt: str, *, system: str = "", **kwargs) -> str:
            if "senior dialog auditor" in system:
                return "[Cliché & Repetitive Pattern Check]: '택화혁의 기류 속에' 상투어 지적"
            # Master scribe의 정밀화 응답
            return "마음의 허물을 벗겨내고 새로운 변화를 맞이할 때입니다. 지금 당신 안에서 가장 먼저 내려놓아야 할 집착은 무엇입니까?"

    llm = MockRefiningLLM()
    res = await run_counsel_turn(
        "어떻게 변화를 시작해야 할까요?",
        INTERP_SAMPLE,
        turn_number=1,
        client=llm,
        enable_refinement_loop=True,
    )

    assert "마음의 허물을 벗겨내고" in res.message
    assert "택화혁의 기류 속에" not in res.message
    assert "?" in res.message
