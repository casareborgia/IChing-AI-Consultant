"""v2 리포트 fixture 빌더.

**실제 생성기를 태워서 만든다.** 손으로 쓴 JSON을 fixture로 두면 스키마가 바뀌어도
조용히 통과하고, 프런트엔드는 실물과 다른 모양을 보게 된다. 여기서는 stub LLM만
끼우고 `run_report_v2_agent`를 그대로 돌린다.

CYCLE-03의 `mockScenarios.js`가 계약을 추측해 만들어졌다가 교체된 전례가 있어,
FE에 넘길 표본은 서버가 실제로 내보내는 값에서 뽑는다.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch

from agents.report_v2 import run_report_v2_agent
from core.hexagram_engine import cast_hexagram
from core.reading import HexagramEvidence, LineEvidence, ReadingEvidence
from schemas.counsel import EvidenceItem
from schemas.hexagram_engine import HexagramCastResult


# 실제 저본에서 가져온 표본. 화뢰서합(21)은 명세서의 불변괘 사례와 같은 괘다.
_HEX_TEXT = {
    21: ("화뢰서합", "噬嗑", "噬嗑 亨 利用獄", "서합은 형통하니, 옥사를 씀이 이롭다.",
         "象曰 雷電噬嗑 先王以 明罰勅法",
         "우레와 번개가 서합이니, 선왕이 이를 본받아 형벌을 밝히고 법령을 정돈하였다."),
}

_STUB_PROMPT = "STUB SYSTEM PROMPT v2"

FIXED_NOW = datetime(2026, 9, 12, 4, 30, 0, tzinfo=timezone.utc)


def _hexagram(hex_id: int) -> HexagramEvidence:
    if hex_id in _HEX_TEXT:
        name, hanja, judgment, judgment_ko, xiang, xiang_ko = _HEX_TEXT[hex_id]
        return HexagramEvidence(
            hexagram_id=hex_id,
            name_full=name,
            name_hanja=hanja,
            judgment_text=judgment,
            judgment_ko=judgment_ko,
            xiang_text=xiang,
            xiang_ko=xiang_ko,
        )
    return HexagramEvidence(
        hexagram_id=hex_id,
        name_full=f"제{hex_id}괘",
        name_hanja=f"卦{hex_id}",
        judgment_text=f"卦辭原文{hex_id}",
        judgment_ko=f"제{hex_id}괘의 괘사 번역입니다.",
        xiang_text=f"象曰 大象原文{hex_id}",
        xiang_ko=f"제{hex_id}괘 대상전 번역입니다.",
    )


def _line(hex_id: int, line_number: int, *, translated: bool = True) -> LineEvidence:
    return LineEvidence(
        hexagram_id=hex_id,
        line_number=line_number,
        position_name="용구/용육" if line_number == 7 else f"{line_number}효",
        statement_text=f"爻辭原文{hex_id}-{line_number}",
        statement_ko=(
            f"제{hex_id}괘 {line_number}효의 효사 번역입니다." if translated else ""
        ),
        small_xiang_text=f"象曰 小象{hex_id}-{line_number}",
        small_xiang_ko=f"제{hex_id}괘 {line_number}효 소상전 번역입니다.",
    )


def build_reading(
    values: List[int], *, translated_lines: bool = True
) -> ReadingEvidence:
    cast: HexagramCastResult = cast_hexagram(manual_lines=values)
    rule = cast.focus_rule
    target_hex_id = (
        cast.transformed_hexagram_id
        if rule.target_hexagram_type == "TRANSFORMED" and cast.transformed_hexagram_id
        else cast.original_hexagram_id
    )
    return ReadingEvidence(
        cast_result=cast,
        original=_hexagram(cast.original_hexagram_id),
        transformed=(
            _hexagram(cast.transformed_hexagram_id)
            if cast.transformed_hexagram_id
            else None
        ),
        focus_rule=rule,
        target_lines=[
            _line(target_hex_id, n, translated=translated_lines)
            for n in rule.target_line_numbers
        ],
        target_hexagram_id=target_hex_id,
    )


def sample_evidences(reading: ReadingEvidence) -> List[EvidenceItem]:
    orig = reading.cast_result.original_hexagram_id
    focus_lines = reading.focus_rule.target_line_numbers
    items = [
        EvidenceItem(
            source_type="hex_comm",
            source_title="정전(程傳)",
            content="턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
            hexagram_id=orig,
            line_number=None,
        ),
        EvidenceItem(
            source_type="hex_comm",
            source_title="본의(本義)",
            content="막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
            hexagram_id=orig,
            line_number=None,
        ),
    ]
    if focus_lines and focus_lines[0] <= 6:
        items.append(
            EvidenceItem(
                source_type="line_comm",
                source_title="정전(程傳) 효사 주석",
                content="그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
                hexagram_id=reading.target_hexagram_id,
                line_number=focus_lines[0],
            )
        )
    return items


# 검증을 통과하는 서술 초안. 한자·기법명·책임 전가 구조를 쓰지 않는다.
VALID_DRAFT: Dict[str, Any] = {
    "narrative": {
        "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
        "emotional_context": {
            "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. "
                          "당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다.",
            "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
            "user_fact_refs": ["U1"],
        },
        "perspective": {
            "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다.",
            "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
            "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
            "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
            "evidence_refs": ["E1"],
        },
        "value_direction": {
            "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
            "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. "
                         "작은 단위로 나누면 손을 댈 자리가 생깁니다.",
            "conditions_to_check": [
                "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
                "나누어 하는 방식이 이 상황에서 실제로 가능한지",
            ],
            "evidence_refs": ["E1"],
        },
        "micro_action_task": {
            "title": "걸린 것 하나만 적어 보기",
            "duration_minutes": 10,
            "when": "오늘 중 조용히 앉을 수 있는 때",
            "steps": [
                "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
                "그중 가장 작아 보이는 것 하나에 표시합니다.",
            ],
            "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
            "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
        },
    },
    "counseling_handoff": {
        "working_hypotheses": ["한 번에 해결하려는 부담이 시작을 늦추고 있는지"],
        "unconfirmed_points": ["실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."],
        "suggested_action_title": "걸린 것 하나만 적어 보기",
        "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    },
}


def stub_llm(*responses: Dict[str, Any]) -> Mock:
    llm = Mock()
    llm.model_name = "stub-model"
    llm.complete_json.side_effect = list(responses) or [VALID_DRAFT]
    return llm


def generate(
    values: List[int],
    *,
    question: str = "요즘 일이 막혀 있는 느낌입니다. 어디서부터 손을 대야 할까요?",
    session_id: str = "fixture-session-0001",
    translated_lines: bool = True,
    draft: Optional[Dict[str, Any]] = None,
    topic_category: str = "직장/진로",
) -> Dict[str, Any]:
    """생성기를 실제로 돌려 v2 리포트 dict를 만든다."""
    reading = build_reading(values, translated_lines=translated_lines)
    llm = stub_llm(draft or VALID_DRAFT)

    async def _run():
        with patch("agents.report_v2.load_system_prompt", return_value=_STUB_PROMPT):
            report = await run_report_v2_agent(
                question=question,
                session_id=session_id,
                reading=reading,
                evidences=sample_evidences(reading),
                topic_category=topic_category,
                client=llm,
                now=FIXED_NOW,
            )
        return report

    report = asyncio.run(_run())
    payload = report.model_dump(mode="json")
    # fixture는 대조용이다. 매번 달라지는 값을 고정한다.
    payload["report_id"] = "00000000-0000-4000-8000-000000000001"
    return payload


# --- fixture 목록 -----------------------------------------------------------

def v2_invariant() -> Dict[str, Any]:
    """불변괘. 명세서 사례와 같은 화뢰서합(21)이다."""
    return generate([7, 8, 8, 7, 8, 7])


def v2_single_changing() -> Dict[str, Any]:
    return generate([9, 7, 7, 7, 7, 7])


def v2_multi_changing() -> Dict[str, Any]:
    """동효 4개. 초점이 지괘로 넘어간다."""
    return generate([9, 9, 9, 9, 8, 7])


def v2_three_changing() -> Dict[str, Any]:
    """동효 3개. 본괘·지괘 괘사가 함께 실린다."""
    return generate([9, 8, 9, 8, 9, 8])


def v2_missing_translation() -> Dict[str, Any]:
    """효사 번역이 없는 경우. 번역 칸이 null로 남고 지어내지 않는다."""
    return generate([9, 7, 7, 7, 7, 7], translated_lines=False)


def legacy_report() -> Dict[str, Any]:
    """판본 표기가 없는 v1 리포트. 화면은 이것을 기존 경로로 열어야 한다."""
    return {
        "question_setting": {
            "question": "요즘 일이 막혀 있는 느낌입니다.",
            "mindset_rule": "재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 다시 뽑지 않고 그대로 이어집니다.",
        },
        "hexagram_casting": {
            "lines": [
                {"position": 1, "name": "1효 (초효)", "value": 7, "line_type_ko": "소양",
                 "symbol": "⚊", "is_changing": False, "note": "변하지 않는 양효"},
                {"position": 2, "name": "2효 (이효)", "value": 8, "line_type_ko": "소음",
                 "symbol": "⚋", "is_changing": False, "note": "변하지 않는 음효"},
                {"position": 3, "name": "3효 (삼효)", "value": 8, "line_type_ko": "소음",
                 "symbol": "⚋", "is_changing": False, "note": "변하지 않는 음효"},
                {"position": 4, "name": "4효 (사효)", "value": 7, "line_type_ko": "소양",
                 "symbol": "⚊", "is_changing": False, "note": "변하지 않는 양효"},
                {"position": 5, "name": "5효 (오효)", "value": 8, "line_type_ko": "소음",
                 "symbol": "⚋", "is_changing": False, "note": "변하지 않는 음효"},
                {"position": 6, "name": "6효 (상효)", "value": 7, "line_type_ko": "소양",
                 "symbol": "⚊", "is_changing": False, "note": "변하지 않는 양효"},
            ],
            "original_hex_id": 21,
            "original_name_full": "화뢰서합",
            "original_name_hanja": "噬嗑",
            "original_upper_trigram": "리(불)",
            "original_lower_trigram": "진(우레)",
            "original_summary": "서합은 형통하니, 옥사를 씀이 이롭다.",
            "has_transformation": False,
            "transformed_hex_id": None,
            "transformed_name_full": None,
            "transformed_name_hanja": None,
            "transformed_summary": None,
        },
        "focus_and_body_use": {
            "changing_count": 0,
            "rule_description": "변효가 없으므로 본괘의 괘사(卦辭)를 주 해석으로 삼습니다.",
            "primary_target_name": "화뢰서합 괘사",
            "body_use_flow": "동효가 없어 지괘가 없습니다. 체용(體用) 보완 규칙은 적용되지 않습니다.",
        },
        "section1_diagnosis": {
            "title": "① 현재 상황 진단 (본괘: 화뢰서합)", "target_name": "화뢰서합",
            "hanja_text": "噬嗑", "interpretation": "지금은 막힌 것을 다루어야 하는 자리입니다.",
        },
        "section2_action": {
            "title": "② 핵심 행동 지침 (주 해석 대상: 화뢰서합 괘사)",
            "target_name": "화뢰서합 괘사", "hanja_text": "噬嗑 亨 利用獄",
            "interpretation": "걸려 있는 것을 하나씩 떼어내십시오.",
        },
        "section3_warning": {
            "title": "③ 보조 경계 지침 (경계 지침)", "target_name": "경계 지침",
            "hanja_text": None, "interpretation": "한 번에 끝내려는 조급함을 경계하십시오.",
        },
        "section4_future": {
            "title": "④ 미래의 귀결 및 주의점 (본괘 유지)", "target_name": "화뢰서합",
            "hanja_text": None, "interpretation": "지금의 국면이 이어집니다.",
        },
        "final_summary": "작게 나누어 씹어 넘기는 것이 이번의 방법입니다.",
    }


def report_failed_envelope() -> Dict[str, Any]:
    """리포트 실패 시 응답 본문의 관련 필드만."""
    return {
        "report_data": None,
        "report_status": "failed",
        "report_error_code": "REPORT_NARRATIVE_INVALID",
    }


ALL_FIXTURES = {
    "v2_invariant": v2_invariant,
    "v2_single_changing": v2_single_changing,
    "v2_three_changing": v2_three_changing,
    "v2_multi_changing": v2_multi_changing,
    "v2_missing_translation": v2_missing_translation,
    "legacy_report": legacy_report,
    "report_failed_envelope": report_failed_envelope,
}
