"""저장된 리포트를 상담 프롬프트로 옮긴다 — 판본별로.

상담사에게 넘길 때 **무엇이 확정이고 무엇이 아닌지**를 갈라야 한다. 갈라 두지
않으면 리포트의 잠정 해석이 다음 턴에서 확정 사실로 굳고, 사용자가 동의한 적 없는
제안이 "당신이 하기로 한 일"로 되돌아온다.

v1은 이 구분이 없었다. `section2_action.interpretation`과 `final_summary`를
그대로 "핵심 결론"이라는 이름표를 달아 넘겼고, 상담사는 그것을 이미 합의된
결론으로 읽었다. `hanja_text`가 섞여 들어가 한문이 상담 프롬프트까지 가기도 했다.
"""

from typing import Any, Dict, List, Mapping, Optional

from core.report_versions import REPORT_LEGACY, REPORT_V2, report_schema_version


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _legacy_block(report_data: Mapping[str, Any]) -> Optional[str]:
    """v1 리포트. 기존 동작을 보존하되 한문은 넘기지 않는다."""
    section2 = report_data.get("section2_action") or {}
    action = _clean(section2.get("interpretation") if isinstance(section2, Mapping) else "")
    summary = _clean(report_data.get("final_summary"))
    if not action and not summary:
        return None

    lines = ["[앞서 제시한 리포트의 요지 — 아직 내담자와 합의된 결론이 아닙니다]"]
    if action:
        lines.append(f"• 제시한 행동 지침: {action}")
    if summary:
        lines.append(f"• 리포트 종합: {summary}")
    return "\n".join(lines) + "\n"


def _v2_block(report_data: Mapping[str, Any]) -> Optional[str]:
    """v2 리포트. 확정 근거 / 잠정 해석 / 미확인 / 제안을 절로 나눈다.

    **자르지 않는다.** v1의 어댑터는 각 절을 100자에서 잘라 `...`을 붙였고,
    문장이 중간에서 끊긴 채로 상담사에게 갔다.
    """
    narrative = report_data.get("narrative")
    if not isinstance(narrative, Mapping):
        return None

    academic = report_data.get("academic_details") or {}
    handoff = report_data.get("counseling_handoff") or {}
    emotional = narrative.get("emotional_context") or {}
    perspective = narrative.get("perspective") or {}
    value = narrative.get("value_direction") or {}
    task = narrative.get("micro_action_task") or {}

    lines: List[str] = []

    # 1. 확정 원전 근거 — 한글 번역만. 원문은 넘기지 않는다.
    confirmed: List[str] = []
    for source in (academic.get("sources") or []):
        if not isinstance(source, Mapping):
            continue
        if source.get("role") not in ("primary", "auxiliary"):
            continue
        translation = _clean(source.get("classical_translation"))
        if not translation:
            continue
        name = _clean(source.get("hexagram_name"))
        line_number = source.get("line_number")
        where = "괘사" if not line_number else (
            "용구/용육" if line_number == 7 else f"{line_number}효"
        )
        confirmed.append(f"• {name} {where}: {translation}")
    if confirmed:
        lines.append("[확정 원전 근거 — 규칙이 지목한 자리입니다]")
        lines.extend(confirmed)
        lines.append("")

    # 2. 리포트의 잠정 해석 — 확정이 아니다.
    interpretive: List[str] = []
    if _clean(perspective.get("applied_reading")):
        interpretive.append(f"• 이번 사연에 옮긴 해석: {_clean(perspective['applied_reading'])}")
    if _clean(perspective.get("alternative_perspective")):
        interpretive.append(f"• 제시한 다른 관점: {_clean(perspective['alternative_perspective'])}")
    if _clean(value.get("rationale")):
        interpretive.append(f"• 가치 방향의 근거: {_clean(value['rationale'])}")
    if interpretive:
        lines.append("[리포트의 잠정 해석 — 내담자가 동의한 적 없습니다]")
        lines.extend(interpretive)
        lines.append("")

    # 3. 확인된 사용자 사실과 미확인 가설을 갈라 둔다.
    validation = _clean(emotional.get("validation"))
    if validation:
        lines.append("[내담자가 실제로 말한 것에 대한 공감]")
        lines.append(validation)
        lines.append("")

    unconfirmed: List[str] = []
    hypothesis = _clean(emotional.get("pattern_hypothesis"))
    if hypothesis:
        unconfirmed.append(f"• 반복 패턴 가설: {hypothesis}")
    for item in (handoff.get("working_hypotheses") or []):
        if _clean(item):
            unconfirmed.append(f"• 확인할 가설: {_clean(item)}")
    for item in (handoff.get("unconfirmed_points") or []):
        if _clean(item):
            unconfirmed.append(f"• 아직 모르는 것: {_clean(item)}")
    if not _clean(value.get("proposed_value")):
        unconfirmed.append("• 지킬 가치가 아직 정해지지 않았습니다.")
    for condition in (value.get("conditions_to_check") or []):
        if _clean(condition):
            unconfirmed.append(f"• 점검할 조건: {_clean(condition)}")
    if unconfirmed:
        lines.append("[아직 확인되지 않은 것 — 사실로 말하지 마십시오]")
        lines.extend(unconfirmed)
        lines.append("")

    # 4. 제안 행동. 고른 적도 끝낸 적도 없다.
    title = _clean(task.get("title"))
    if title:
        lines.append("[리포트가 제안한 행동 — 내담자가 선택하지 않았습니다]")
        lines.append(f"• {title}")
        for step in (task.get("steps") or []):
            if _clean(step):
                lines.append(f"    - {_clean(step)}")
        lines.append(
            "  내담자가 이 행동을 하기로 했다고 전제하지 마십시오. "
            "다짐이나 서약으로 되돌려 말하지도 마십시오."
        )
        lines.append("")

    lines.append(
        "[중요] 내담자가 위 해석이나 가설을 부인하면 그 정정을 받아들이고 이어가십시오. "
        "리포트가 먼저 쓴 말이라는 이유로 유지하지 마십시오."
    )
    return "\n".join(lines) + "\n"


def counsel_prompt_block(report_data: Optional[Dict[str, Any]]) -> Optional[str]:
    """상담 프롬프트에 실을 리포트 인계 블록. 판본을 모르면 아무것도 싣지 않는다."""
    version = report_schema_version(report_data)
    if version == REPORT_V2:
        return _v2_block(report_data)
    if version == REPORT_LEGACY:
        return _legacy_block(report_data)
    # None(리포트 없음) 또는 unknown(모르는 명시적 판본).
    # 모르는 판본을 legacy처럼 읽으면 빈 칸이 정상처럼 보인다. 싣지 않는다.
    return None
