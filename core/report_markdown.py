"""v2 리포트를 마크다운으로 옮긴다.

**순수 함수다.** 같은 JSON이면 같은 글이 나온다. 화면과 별도로 LLM을 부르지
않는다 — 부르면 화면에 보이는 글과 내보낸 글이 달라지고, 사용자는 어느 쪽이
자기 리포트인지 알 수 없게 된다.

이스케이프 기준
--------------
본문에 들어가는 값은 사용자 발화와 모델 출력에서 온다. 둘 다 신뢰하지 않는다.

1. 줄바꿈을 공백으로 접는다. 그래야 값 하나가 새 블록(제목·목록·표)을 열 수 없다.
2. `&` `<` `>`를 HTML 엔티티로 바꾼다. 마크다운 렌더러가 원문 HTML을 통과시키는
   설정이어도 태그가 서지 않는다.
3. 마크다운 인라인 특수문자(``\\ ` * _ [ ] |``)를 역슬래시로 막는다.

순서가 중요하다 — `&`를 먼저 바꾸지 않으면 나중에 만든 엔티티의 `&`가 다시 바뀐다.
`|`까지 막는 이유는 근거 표가 파이프 표이기 때문이다.
"""

from typing import Any, Dict, List, Optional

from schemas.report_v2 import PreCounselingReport, ReportSource, SourceRole


_MD_SPECIAL = ("\\", "`", "*", "_", "[", "]", "|")

# 초효·상효는 이름으로 부른다. 나머지는 번호로.
_POSITION_NAME = {1: "초효", 2: "2효", 3: "3효", 4: "4효", 5: "5효", 6: "상효"}

_ROLE_LABEL = {
    SourceRole.PRIMARY: "주 근거",
    SourceRole.AUXILIARY: "보조 근거",
    SourceRole.BACKGROUND: "배경",
    SourceRole.BODY_USE: "체용 참작",
    SourceRole.SUPPLEMENT: "보충 (대상전)",
    SourceRole.ANNOTATION: "고전 주석",
}


def escape(text: Optional[str]) -> str:
    """본문에 넣어도 구조를 못 바꾸게 만든다."""
    if not text:
        return ""
    out = " ".join(str(text).split())
    out = out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for ch in _MD_SPECIAL:
        out = out.replace(ch, "\\" + ch)
    return out


def _line_label(source: ReportSource) -> str:
    if source.role == SourceRole.SUPPLEMENT:
        # 대상전을 "괘사"라고 부르면 보충이 주 근거처럼 읽힌다.
        return "대상전"
    if source.line_number is None:
        return "괘사"
    if source.line_number == 7:
        return "용구/용육"
    return f"{source.line_number}효"


def _academic_block(report: PreCounselingReport) -> List[str]:
    academic = report.academic_details
    casting = academic.casting
    focus = academic.focus_rule

    lines = [
        "<details>",
        "<summary><b>📜 고전 수리 검증 및 원전 근거 보기</b></summary>",
        "",
        "#### 1. 점서 예식 및 수리 도출",
        # 사용자의 마음가짐은 서버가 확인할 수 없다. 서버가 실제로 보장하는 것만 적는다.
        "- **점서 예식**: 재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 "
        "다시 뽑지 않습니다.",
    ]

    numerals = " ➔ ".join(
        f"{_POSITION_NAME.get(l.position, f'{l.position}효')}({l.value})"
        for l in casting.lines
    )
    lines.append(f"- **도출 수리**: {escape(numerals)}")
    lines.append(
        f"- **본괘**: {escape(casting.original_name)} "
        f"(하괘 {escape(casting.original_lower_trigram)}, "
        f"상괘 {escape(casting.original_upper_trigram)})"
    )
    if casting.has_transformation:
        lines.append(f"- **지괘**: {escape(casting.transformed_name)}")
    else:
        lines.append("- **지괘**: 없음 (동효가 없는 불변괘입니다)")

    lines += [
        "",
        "#### 2. 고변점(考變占) 판정 규칙",
        f"- **변효 개수**: {focus.changing_count}개"
        + (
            f" (위치 {escape(', '.join(f'{p}효' for p in casting.changing_lines))})"
            if casting.changing_lines
            else " (불변괘)"
        ),
        f"- **해석 원칙**: {escape(focus.description_ko)}",
    ]
    if focus.body_use_note_ko:
        lines.append(f"- **체용 참작**: {escape(focus.body_use_note_ko)}")
    lines.append(f"- **규칙 판본**: {escape(focus.rule_version)}")

    lines += ["", "#### 3. 고전 원문 및 번역", ""]
    for source in academic.sources:
        head = (
            f"- **[{escape(_ROLE_LABEL.get(source.role, source.role.value))}] "
            f"{escape(source.hexagram_name)} {escape(_line_label(source))}**"
        )
        if source.role == SourceRole.ANNOTATION:
            head = (
                f"- **[{escape(_ROLE_LABEL[SourceRole.ANNOTATION])}] "
                f"{escape(source.annotation_source or '출처 미상')}**"
            )
            lines.append(head)
            lines.append(f"    - {escape(source.annotation)}")
            continue
        lines.append(head)
        lines.append(f"    - 원문: {escape(source.classical_text)}")
        if source.classical_translation:
            lines.append(f"    - 번역: {escape(source.classical_translation)}")
        else:
            # 없는 번역을 지어내지 않는다. 누락은 누락으로 보인다.
            lines.append("    - 번역: (확인된 번역 없음)")
        if source.locator:
            lines.append(f"    - 출처: {escape(source.locator)}")

    meta = report.generation_metadata
    lines += [
        "",
        "#### 4. 생성 정보",
        f"- 생성 시각: {escape(meta.generated_at)}",
        f"- 모델: {escape(meta.model) if meta.model else '(미확인)'}",
        f"- 프롬프트 판본: {escape(meta.prompt_version)}",
        f"- 근거 지문: {escape(meta.evidence_snapshot_hash[:16])}",
        "",
        "</details>",
    ]
    return lines


def render_markdown(report: PreCounselingReport) -> str:
    """리포트 전체를 마크다운 한 덩어리로."""
    n = report.narrative
    casting = report.academic_details.casting
    out: List[str] = [
        "# 💡 오늘 주역이 당신에게 건네는 통찰",
        "",
        f"> **{escape(n.headline_metaphor)}**",
        "",
        "---",
        "",
        f"### 1. 당신이 지나가는 계절의 이름 (본괘: {escape(casting.original_name)})",
        "",
        escape(n.emotional_context.validation),
    ]
    if n.emotional_context.pattern_hypothesis:
        out += [
            "",
            # 가설을 사실처럼 보이지 않게 한다. 화면에서도 같은 표시를 쓴다.
            f"*함께 살펴볼 가설입니다 — {escape(n.emotional_context.pattern_hypothesis)}*",
        ]

    out += ["", "---", "", "### 2. 생각의 덫에서 벗어나기", ""]
    if n.perspective.thought_observation:
        out += [escape(n.perspective.thought_observation), ""]
    out += [
        escape(n.perspective.classical_reading),
        "",
        escape(n.perspective.applied_reading),
        "",
        escape(n.perspective.alternative_perspective),
    ]

    out += ["", "---", "", "### 3. 나아갈 삶의 가치와 경고등", ""]
    if n.value_direction.proposed_value:
        out += [f"**지켜볼 가치**: {escape(n.value_direction.proposed_value)}", ""]
    out += [escape(n.value_direction.rationale), "", "**선택할 때 점검할 조건**", ""]
    out += [f"- {escape(c)}" for c in n.value_direction.conditions_to_check]

    task = n.micro_action_task
    out += [
        "",
        "---",
        "",
        f"### 4. 오늘 나를 구하는 {task.duration_minutes}분 행동",
        "",
        f"🎯 **{escape(task.title)}**",
        "",
        f"- 언제: {escape(task.when)}",
    ]
    for idx, step in enumerate(task.steps, start=1):
        out.append(f"- {idx}. {escape(step)}")
    out.append(f"- 끝난 것으로 볼 기준: {escape(task.completion_criterion)}")
    if task.smaller_alternative:
        out.append(f"- 더 작게 하려면: {escape(task.smaller_alternative)}")
    # 제안이지 사용자의 다짐이 아니다. 선택·완료는 별도 상태다.
    out += ["", "*제안입니다. 하실지는 직접 정하시면 됩니다.*"]

    out += ["", "---", ""]
    out += _academic_block(report)
    out.append("")
    return "\n".join(out)


def render_markdown_from_dict(data: Dict[str, Any]) -> str:
    """저장된 JSON에서 바로 렌더한다. v2가 아니면 거절한다."""
    return render_markdown(PreCounselingReport.model_validate(data))
