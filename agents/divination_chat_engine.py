# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 5턴 소크라테스식 코칭 챗봇 엔진 (Divination Chat Engine v1.0)
- v4.1 엔진의 '영문 지시문(Reasoning) + 고품격 국문 출력(Output)' 설계 패러다임을 이식했습니다.
- 사용자와 AI의 대화가 무한히 꼬리를 물고 늘어지는 현상(Endless Loop)을 방지하기 위해 5턴 제한의 엄격한 가드레일을 적용합니다.
- 성리학의 자성(自省)과 퇴계의 경(敬) 철학에 기반하여, 내담자 스스로 아집을 발견하고 실천적 다짐을 하도록 돕는 소크라테스식 코칭 발문을 생성합니다.
- 대화 턴별 자아비판 및 정밀화(Critique & Refinement) 프로토콜을 탑재하여 언제나 일관되고 품격 높은 상담 어조를 유지합니다.
"""

import json
from typing import Any, Dict, List, Optional


def adapt_to_report_payload(
    report_data: Optional[Dict[str, Any]] = None,
    interpretation_raw_text: str = "",
    contextual_mapping: str = "",
    focus_rule: Optional[Dict[str, Any]] = None,
    original_hex_name: str = "",
    transformed_hex_name: str = "",
) -> Dict[str, Any]:
    """
    다양한 형태의 리포트/해석 데이터(HexagramReportSchema 덤프, raw_text, focus_rule 등)를
    DivinationChatEngine 규격의 report_payload로 변환하는 안전한 어댑터입니다.
    """
    if not report_data:
        report_data = {}

    # 1. 이미 derivation_data 형태를 갖추고 있는 경우 바로 반환
    if "derivation_data" in report_data and "judgment_rules" in report_data:
        return report_data

    # 2. HexagramReportSchema 형태의 report_data 추출
    hex_casting = report_data.get("hexagram_casting", {})
    focus_and_body = report_data.get("focus_and_body_use", {})
    sec1 = report_data.get("section1_diagnosis", {})
    sec2 = report_data.get("section2_action", {})
    sec3 = report_data.get("section3_warning", {})
    sec4 = report_data.get("section4_future", {})
    final_summary = report_data.get("final_summary", "")

    orig_name = (
        hex_casting.get("original_name_full")
        or original_hex_name
        or "미상 본괘"
    )
    res_name = (
        hex_casting.get("transformed_name_full")
        or transformed_hex_name
        or orig_name
    )

    target_focus = (
        focus_and_body.get("primary_target_name")
        or (focus_rule.get("target_focus") if focus_rule else None)
        or sec2.get("target_name")
        or "핵심 괘효사"
    )

    local_target_text = (
        sec2.get("hanja_text")
        or sec2.get("interpretation")
        or (focus_rule.get("description") if focus_rule else None)
        or interpretation_raw_text
        or ""
    )

    agenda_items = []
    if sec1.get("interpretation"):
        agenda_items.append(f"현재 상황 진단: {sec1.get('interpretation')[:100]}...")
    if sec2.get("interpretation"):
        agenda_items.append(f"핵심 행동 지침: {sec2.get('interpretation')[:100]}...")
    if sec3.get("interpretation"):
        agenda_items.append(f"보조 경계 지침: {sec3.get('interpretation')[:100]}...")
    if final_summary:
        agenda_items.append(f"종합 결론: {final_summary[:100]}...")

    if not agenda_items and contextual_mapping:
        agenda_items.append(f"고민 매핑: {contextual_mapping}")

    return {
        "derivation_data": {
            "original_hexagram": {
                "name": orig_name,
                "summary": hex_casting.get("original_summary", ""),
            },
            "resulting_hexagram": {
                "name": res_name,
                "summary": hex_casting.get("transformed_summary", ""),
            },
        },
        "judgment_rules": {
            "target_focus": target_focus,
            "local_target_text": local_target_text,
            "local_target_line_name": target_focus,
            "description": focus_and_body.get("rule_description", ""),
        },
        "counseling_agenda": agenda_items,
    }


class DivinationChatEngine:
    def __init__(self):
        pass

    def get_next_turn_number(self, conversation_history: List[Dict[str, str]]) -> int:
        """
        현재 대화 기록을 바탕으로 다음 생성할 상담사의 턴수(1~5)를 계산합니다.
        상담사의 메시지 개수를 기준으로 턴수를 산정합니다.
        """
        counselor_messages = [
            msg for msg in conversation_history
            if msg.get("role") in ("counselor", "assistant")
        ]
        return len(counselor_messages) + 1

    def generate_chat_prompt(
        self,
        conversation_history: List[Dict[str, str]],
        user_question: str,
        report_payload: Dict[str, Any],
        turn_num_override: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        현재 대화 단계에 맞추어 소크라테스식 코칭 질문을 출력하기 위한 영문 지시 및 컨텍스트 프롬프트를 구성합니다.
        """
        turn_num = turn_num_override if turn_num_override is not None else self.get_next_turn_number(conversation_history)
        turn_num = max(1, min(turn_num, 5))
        
        # Extract metadata from report_payload safely
        derivation = report_payload.get("derivation_data", {})
        orig_hex = derivation.get("original_hexagram", {})
        res_hex = derivation.get("resulting_hexagram", {})
        rules = report_payload.get("judgment_rules", {})
        
        orig_name = orig_hex.get("name", "미상")
        res_name = res_hex.get("name", "미상")
        target_focus = rules.get("target_focus", "괘사")
        target_text = rules.get("local_target_text", "")
        target_line_name = rules.get("local_target_line_name", "괘사")
        
        agenda_items = report_payload.get("counseling_agenda", [])

        system_prompt = f"""You are an elite, Neo-Confucian I-Ching counseling master.
Your goal is to guide the client to self-reflect (자성 自省) and discover their own inner "righteous path" (도심 道心) rather than predicting fortunes or simply agreeing with their emotional complaints.
You must strictly follow a 5-step Socratic Counseling model, ensuring the conversation reaches a concrete "Action Pledge" by Turn 5.

[CRITICAL DIALOGUE DESIGN: THE 5-STEP SOCRATIC MODEL]
- TURN 1 [First Greeting & Firestarter]:
  * Action: Welcome the client warmly. Instantly reference the pre-counseling report's key metaphor ({target_focus}: "{target_text}") and link it to their modern struggle ("{user_question}").
  * Question: Ask an open-ended, penetrating Socratic question that invites them to map this ancient metaphor to their current real-world players/situation.
- TURN 2 [Deepening Reflection - Mirroring]:
  * Action: Mirror the client's previous response with profound dignity and empathy. Do NOT validate their biases, but highlight the hidden psychological tension or inner conflict they just expressed.
  * Question: Ask a deeper Socratic question that turns their focus inward to examine their own hidden desire, blind spot, or urge to control (the "Aha! Moment" setup).
- TURN 3 [Shifting Perspective - The Turning Point]:
  * Action: Acknowledge their honest confession. Introduce the target line's philosophical prescription (e.g., "reverence/敬", "utilizing sacrifice/利用祭祀", "preventive restraint/終日戒"). Explain how this attitude shifts the dynamic.
  * Question: Ask how they can apply this self-disciplining/receptive attitude of surrender or restraint in their modern situation, instead of their previous reactive behavior.
- TURN 4 [Integration of the Resulting Hexagram]:
  * Action: Validate their new perspective. Introduce the Resulting Hexagram ({res_name}) as their ultimate spiritual destination (e.g., "뇌수해 - Resolution/解", "택뢰수 - Following the natural flow/隨"). Describe the serene energy of this future state.
  * Question: Ask how they can actively transition or "let go" of their current struggle to enter this receptive state of wisdom.
- TURN 5 [Action Pledge Call - Hard Termination]:
  * Action: Celebrate their profound spiritual journey. Solemnly state that today's self-reflection must translate into immediate action (지행합일 知行合一).
  * Question: Ask them to declare EXACTLY ONE concrete, practical, and small action pledge they will execute TODAY. Explicitly tell them: "This pledge will be inscribed on your Action Pledge Card as your sacred commitment." Once they answer, the session will be terminated and the card will be issued.

[Output Language & Tone Guidelines]
- Language: Korean (한국어).
- Tone: Highly elegant, literary, deeply respectful, comforting yet razor-sharp honorifics (경어체). It must sound like a wise philosopher-counselor.
- Length: Keep your response concise (maximum 3-4 flowing sentences per turn). You are in a chat room, so long speeches will break the immersion.
- Crucial Rule: ALWAYS end your response with exactly ONE profound, open-ended question.
- Anti-Repetition Mandate: Do not repeat the exact same raw hexagram quotation across multiple turns unless you paraphrase it dynamically in a completely different context. If a line explanation or metaphor was already presented in Turn 1, do NOT repeat the same phrase verbatim in subsequent turns (especially Turn 3). Instead, translate its spirit into a fresh psychological perspective or actionable attitude.

[JSON Response Format]
Respond strictly in JSON:
{{
  "message": "<Counselor's response in elegant Korean, within 3-4 sentences, ending with exactly one Socratic question>",
  "needs_followup": <true for turns 1-4, false for turn 5>,
  "followup_question": "<the single ending Socratic question>",
  "is_final": <false for turns 1-4, true for turn 5>
}}"""

        user_prompt = f"""<divination_context>
- User's Original Struggle: "{user_question}"
- Original Hexagram (본괘): {orig_name}
- Resulting Hexagram (지괘): {res_name}
- Target Line of Reflection: {target_focus}
- Core Ancient Metaphor Text: {target_text} ({target_line_name})
- Pre-set Agenda Items: {json.dumps(agenda_items, ensure_ascii=False)}
</divination_context>

<current_stage>
- Next Turn to Generate: Turn {turn_num} of 5
- Turn Goal: {self._get_turn_goal_description(turn_num)}
</current_stage>

<conversation_history>
{json.dumps(conversation_history, ensure_ascii=False, indent=2)}
</conversation_history>

Generate the counselor's next response following the designated goal of Turn {turn_num} and the strict tone rules. Ensure it is written in Korean with exquisite literary prose. Return valid JSON."""

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    def _get_turn_goal_description(self, turn_num: int) -> str:
        goals = {
            1: "Turn 1: Warm greeting. Reference the target line's metaphor and map it to user struggle. Ask the first open Socratic question.",
            2: "Turn 2: Deepen reflection. Mirror the client's response with dignity, highlight psychological tension, and ask about their inner blind spot/desire.",
            3: "Turn 3: Perspective shift. Introduce the philosophical prescription of the target line (e.g., 제사/기다림/삼감) and ask how they can practice this inner discipline. Do NOT repeat the exact quotation from Turn 1; paraphrase it into an inner attitude of restraint.",
            4: "Turn 4: Integration. Validate their shift, introduce the Resulting Hexagram's wisdom/energy, and ask how they can let go of the struggle to align with this destination.",
            5: "Turn 5: Action Pledge Call. State that self-reflection must lead to immediate action (지행합일). Ask for EXACTLY ONE concrete action pledge for their Action Card."
        }
        return goals.get(turn_num, "Socratic conversation turn.")

    def generate_critique_prompt(
        self,
        draft_response: str,
        conversation_history: List[Dict[str, str]],
        report_payload: Dict[str, Any],
        turn_num_override: Optional[int] = None,
    ) -> str:
        """
        생성된 챗봇 답변 초안이 5단계 Socratic 모델 및 고격조 어조 기준에 부합하는지 비판적으로 검증하는 프롬프트를 생성합니다.
        """
        turn_num = turn_num_override if turn_num_override is not None else self.get_next_turn_number(conversation_history)
        turn_num = max(1, min(turn_num, 5))
        
        critique_prompt = f"""You are a senior dialog auditor and a Neo-Confucian classical scholar reviewing our AI Counselor's Turn {turn_num} response draft.
Critique the [Draft Response] strictly against the following 4 Quality Gates. Do not compliment; focus entirely on defects.

[4 Quality Gates of Socratic Dialogue]
1. [Socratic Turn Alignment]: Is the response perfectly aligned with the designated goal of Turn {turn_num} (e.g., Turn 1 = Metaphor/ struggle link; Turn 3 = Prescriptive restraint; Turn 5 = Direct pledge call)?
2. [No Clichés or Repetitions]: Does it contain robotic clichéd patterns such as "~의 기류 속에", "~이 핵심입니다", "~에 직면해 있습니다", or repeat the exact same raw hexagram quotation/phrasing across turns? Verbatim repetition of earlier turn quotations (e.g., repeating Turn 1 phrases in Turn 3) is strictly forbidden.
3. [Proportional & Concise Length]: Is the response concise (within 3-4 sentences)? In a real-time chat, paragraphs of text will destroy the user's attention.
4. [Single Profound Question]: Does it end with exactly ONE elegant, open-ended question designed to prompt deep self-reflection, rather than multiple or binary questions?

[Input Data]
- Next Turn to Verify: Turn {turn_num} of 5
- Target Metaphor: {report_payload.get("judgment_rules", {}).get("local_target_text", "")}
- Draft Response:
\"\"\"
{draft_response}
\"\"\"

[Output Format]
Write a ruthless audit report matching this structure (all in Korean):
- [Socratic Turn Alignment Audit]: (Pass/Fail and reason)
- [Cliché & Repetitive Pattern Check]: (List forbidden phrases or repetitions found, if any)
- [Conciseness & Length Audit]: (Pass/Fail and sentence count)
- [Single Question Check]: (Pass/Fail and validation of the ending question)
- [Overall Redirection Line]: (1-sentence strict direction for the rewrite)"""

        return critique_prompt

    def generate_refinement_prompt(
        self,
        draft_response: str,
        critique_result: str,
        conversation_history: List[Dict[str, str]],
        report_payload: Dict[str, Any],
        turn_num_override: Optional[int] = None,
    ) -> str:
        """
        자가 비판 결과를 수렴하여 대화 초안의 모든 상투성과 오류를 말끔히 지우고 완벽하게 리팩토링하는 프롬프트를 생성합니다.
        """
        turn_num = turn_num_override if turn_num_override is not None else self.get_next_turn_number(conversation_history)
        turn_num = max(1, min(turn_num, 5))
        
        refinement_prompt = f"""You are the master scribe of the I-Ching counseling team. 
Your task is to rewrite the AI Counselor's Turn {turn_num} response draft by fully integrating the issues raised in the [Auditor's Critique].

[Refinement Mandate]
1. Resolve every defect pointed out in the [Auditor's Critique] with 100% precision.
2. Ensure the rewritten response is incredibly elegant, concise (strictly under 4 sentences), flows like wind, and ends with exactly ONE sharp Socratic question.
3. Completely clean out any repetitive phrases, verbatim quotation echoes from earlier turns, jargon, or translation-like structures. Paraphrase the wisdom dynamically.

[Data for Reference]
- Auditor's Critique:
{critique_result}

- Original Draft:
\"\"\"
{draft_response}
\"\"\"

Generate ONLY the refined, flawless counselor response in elegant Korean. No explanations or preambles."""

        return refinement_prompt
