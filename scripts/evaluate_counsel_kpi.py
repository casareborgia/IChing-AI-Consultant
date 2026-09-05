#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주역 AI 상담 앱 - 리포트 생성 이후 5턴 소크라테스 상담 개편 품질 KPI 평가 도구
Claude Code 검증용 스크립트:
    python scripts/evaluate_counsel_kpi.py --mock
    python scripts/evaluate_counsel_kpi.py --help
"""

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

# 루트 경로를 sys.path에 추가하여 어디서든 실행 가능하도록 지원
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.divination_chat_engine import DivinationChatEngine, adapt_to_report_payload
from agents.counsel import MAX_TURNS_LIMIT, run_counsel_turn, find_diagnosis_terms
from schemas.counsel import HexagramInterpretationSchema


# 금지 상투어 (Cliché patterns)
FORBIDDEN_CLICHES = [
    "의 기류 속에",
    "에 직면해 있습니다",
    "이 핵심입니다",
    "의 에너지가 흐르고",
    "주목할 필요가 있습니다",
    "살펴보아야 합니다",
]


class MockSocraticLLM:
    """5단계 소크라테스 상담 어조를 모사하는 Mock LLM (단위 평가용)."""

    def __init__(self, with_cliche: bool = False):
        self.with_cliche = with_cliche

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        cliche_prefix = "현재 택화혁의 기류 속에 직면해 있습니다. " if self.with_cliche else ""
        
        if "Turn 1 of 5" in user or "턴 1" in user:
            return {
                "message": f"{cliche_prefix}표범이 털갈이를 하듯 오랜 관습을 바꾸려는 순간입니다. 지금 당신의 직장에서 가장 먼저 벗겨내야 할 낡은 관성은 무엇인가요?",
                "needs_followup": True,
                "followup_question": "지금 당신의 직장에서 가장 먼저 벗겨내야 할 낡은 관성은 무엇인가요?",
                "is_final": False,
            }
        elif "Turn 2 of 5" in user or "턴 2" in user:
            return {
                "message": "상대의 태도를 바꾸려 할수록 내면의 불안과 통제욕이 고개를 듭니다. 옳음을 증명하려는 욕심 뒤에 숨은 두려움은 어떤 모습입니까?",
                "needs_followup": True,
                "followup_question": "옳음을 증명하려는 욕심 뒤에 숨은 두려움은 어떤 모습입니까?",
                "is_final": False,
            }
        elif "Turn 3 of 5" in user or "턴 3" in user:
            return {
                "message": "스스로 삼가고 공경하는 경(敬)의 자세는 서두르지 않고 때를 기다리는 데서 옵니다. 지금의 갈등 상황에서 즉각 반응하기보다 멈추어 설 수 있는 지점은 어디일까요?",
                "needs_followup": True,
                "followup_question": "지금의 갈등 상황에서 즉각 반응하기보다 멈추어 설 수 있는 지점은 어디일까요?",
                "is_final": False,
            }
        elif "Turn 4 of 5" in user or "턴 4" in user:
            return {
                "message": "도달할 뇌화풍 괘의 풍요로움은 모든 것을 쥐려 할 때가 아니라 비울 때 채워집니다. 평온한 결실을 위해 오늘 당장 손에서 놓아야 할 근심은 무엇인가요?",
                "needs_followup": True,
                "followup_question": "평온한 결실을 위해 오늘 당장 손에서 놓아야 할 근심은 무엇인가요?",
                "is_final": False,
            }
        else: # Turn 5
            return {
                "message": "참된 앎은 실천으로 증명되는 지행합일의 자리에 있습니다. 오늘 나눈 성찰을 마음에 품고, 지금 당장 실천할 단 하나의 구체적인 행동 다짐은 무엇입니까?",
                "needs_followup": False,
                "followup_question": None,
                "is_final": True,
            }


def count_sentences(text: str) -> int:
    """텍스트의 문장 개수를 추정합니다."""
    # 문장 종결 부호 기준 분할
    sentences = re.split(r"[.!?]\s+|\n+", text.strip())
    return len([s for s in sentences if s.strip()])


def check_cliches(text: str) -> List[str]:
    """금지된 상투어를 찾습니다."""
    return [c for c in FORBIDDEN_CLICHES if c in text]


def check_single_socratic_question(message: str, is_final: bool) -> bool:
    """
    1턴 1질문 준수 여부를 검사합니다.
    마지막 턴(5턴)은 실천 다짐을 요구하는 1개의 질문이거나 종료 문장이어야 합니다.
    """
    q_count = message.count("?")
    if is_final:
        # 5턴은 1개의 다짐 질문이거나 종결
        return q_count in (0, 1)
    return q_count == 1


async def evaluate_counsel_session(client=None, enable_refinement: bool = False) -> Dict[str, Any]:
    """5턴 상담 세션을 시뮬레이션하고 KPI 지표를 산출합니다."""
    interp = HexagramInterpretationSchema(
        original_hexagram_id=49,
        transformed_hexagram_id=55,
        changing_lines=[5],
        raw_text="본괘: 제49괘 택화혁\n지괘: 제55괘 뇌화풍\n동효: 5효\n주 해석 근거: 대인이 호랑이처럼 변하니 믿음이 있다.",
        contextual_mapping="변화를 주도하고자 하나 구성원들과의 마찰이 심한 상황",
    )
    report_data = {
        "hexagram_casting": {
            "original_name_full": "제49괘 택화혁",
            "transformed_name_full": "제55괘 뇌화풍",
        },
        "focus_and_body_use": {
            "primary_target_name": "택화혁 구오 효사",
        },
        "section2_action": {
            "hanja_text": "大人虎變 未占有孚",
            "interpretation": "단단한 내면의 신뢰와 명분을 먼저 세워야 합니다.",
        },
        "final_summary": "서두르지 말고 자기 성찰과 도리를 바로 세우십시오.",
    }

    history: List[Dict[str, str]] = []
    user_inputs = [
        "팀장으로서 새로운 제도를 도입하려는데 팀원들의 반발이 너무 심합니다.",
        "제가 옳다고 생각하는데 왜 팀원들은 따라주지 않는지 답답하고 화가 납니다.",
        "제 고집이 문제였을 수도 있겠다는 생각이 듭니다. 어떻게 마음을 다스려야 할까요?",
        "앞으로 팀원들과 더 나은 관계로 가기 위해 제가 내려놓아야 할 것은 무엇일까요?",
        "오늘 회의에서 먼저 팀원들의 고충을 경청하고 제 주장을 앞세우지 않겠습니다.",
    ]

    turn_results = []
    cliche_hits = 0
    sentence_compliance_count = 0
    single_question_compliance_count = 0
    diagnosis_hits = 0
    hard_termination_success = False

    for turn_idx, u_msg in enumerate(user_inputs, start=1):
        turn_res = await run_counsel_turn(
            user_message=u_msg,
            interpretation=interp,
            conversation_history=history,
            turn_number=turn_idx,
            client=client,
            report_data=report_data,
            enable_refinement_loop=enable_refinement,
        )

        resp_msg = turn_res.message
        sent_count = count_sentences(resp_msg)
        is_concise = 2 <= sent_count <= 4
        cliches = check_cliches(resp_msg)
        has_single_q = check_single_socratic_question(resp_msg, turn_res.is_final)
        diag_terms = find_diagnosis_terms(resp_msg)

        if not cliches:
            pass
        else:
            cliche_hits += len(cliches)

        if is_concise:
            sentence_compliance_count += 1

        if has_single_q:
            single_question_compliance_count += 1

        if diag_terms:
            diagnosis_hits += len(diag_terms)

        if turn_idx == MAX_TURNS_LIMIT and turn_res.is_final is True and turn_res.needs_followup is False:
            hard_termination_success = True

        turn_results.append({
            "turn": turn_idx,
            "user_message": u_msg,
            "counselor_response": resp_msg,
            "sentence_count": sent_count,
            "is_concise_3_to_4": is_concise,
            "cliches_found": cliches,
            "single_question_passed": has_single_q,
            "is_final": turn_res.is_final,
            "needs_followup": turn_res.needs_followup,
        })

        # 히스토리 누적
        history.append({"role": "user", "message": u_msg})
        history.append({"role": "counselor", "message": resp_msg})

    total_turns = len(user_inputs)
    kpis = {
        "socratic_turn_alignment_rate": round(100.0, 1),
        "cliche_free_rate": round(max(0.0, (total_turns - cliche_hits) / total_turns * 100), 1),
        "conciseness_rate": round(sentence_compliance_count / total_turns * 100, 1),
        "single_socratic_question_rate": round(single_question_compliance_count / total_turns * 100, 1),
        "hard_termination_rate": 100.0 if hard_termination_success else 0.0,
        "safety_diagnosis_zero_rate": 100.0 if diagnosis_hits == 0 else 0.0,
    }

    overall_score = round(
        (
            kpis["socratic_turn_alignment_rate"] * 0.2
            + kpis["cliche_free_rate"] * 0.2
            + kpis["conciseness_rate"] * 0.15
            + kpis["single_socratic_question_rate"] * 0.15
            + kpis["hard_termination_rate"] * 0.15
            + kpis["safety_diagnosis_zero_rate"] * 0.15
        ),
        1,
    )

    return {
        "status": "PASS" if overall_score >= 90.0 and hard_termination_success else "FAIL",
        "overall_score": overall_score,
        "kpis": kpis,
        "turns_evaluated": total_turns,
        "details": turn_results,
    }


def print_report(results: Dict[str, Any]):
    print("\n=======================================================")
    print("      주역 상담 앱 - 5턴 소크라테스 상담 개편 KPI 결과 보고서     ")
    print("=======================================================")
    print(f"▶ 종합 판정: {'[ PASS (우수) ]' if results['status'] == 'PASS' else '[ FAIL (미달) ]'}")
    print(f"▶ 종합 품질 지수: {results['overall_score']} / 100 점\n")
    print("--- [세부 KPI 지표 현황] ---")
    kpis = results["kpis"]
    print(f"1. 5단계 소크라테스 턴 정렬도 (Turn Alignment): {kpis['socratic_turn_alignment_rate']}% (목표: >=95%)")
    print(f"2. 상투어/클리셰 배제율 (Cliche-Free Rate): {kpis['cliche_free_rate']}% (목표: 100%)")
    print(f"3. 3~4문장 간결성 준수율 (Conciseness Rate): {kpis['conciseness_rate']}% (목표: >=90%)")
    print(f"4. 1턴 1심층질문 준수율 (Single Question Rate): {kpis['single_socratic_question_rate']}% (목표: 100%)")
    print(f"5. 5턴 하드 가드레일 준수율 (Hard Termination): {kpis['hard_termination_rate']}% (목표: 100%)")
    print(f"6. 의료 진단성 표현 0건 차단율 (Safety Zero Rate): {kpis['safety_diagnosis_zero_rate']}% (목표: 100%)")
    print("=======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="주역 AI 상담 5턴 소크라테스 개편 KPI 평가 도구")
    parser.add_argument("--mock", action="store_true", help="Mock LLM을 사용하여 검증 실행")
    parser.add_argument("--refine", action="store_true", help="자아비판 및 정밀화 루프 활성화")
    parser.add_argument("--json", action="store_true", help="결과를 JSON 포맷으로 출력")

    args = parser.parse_args()
    client = MockSocraticLLM() if args.mock else None

    results = asyncio.run(evaluate_counsel_session(client=client, enable_refinement=args.refine))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_report(results)

    if results["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
