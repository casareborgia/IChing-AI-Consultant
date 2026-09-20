"""점괘 사전 분석 리포트 v2 생성기.

**확정 사실과 서술을 나눈다.** 서버가 괘·초점 규칙·원문·번역·출처를 조립하고,
LLM은 그 위에 서술과 상담 인계 초안만 쓴다. 모델이 괘 ID나 원문을 되돌려 보낼
자리가 없으므로(`NarrativeDraft`) 확정값이 서술로 덮이지 않는다.

    확정 근거 조립 → 서술 1회 생성 → 검증 → (실패 시) 같은 근거로 수정 1회
    → 재검증 → 실패면 중단

보고서당 논리적 LLM 호출은 최대 2회다. v1에 있던 **무조건 실행되는 정제 호출**은
없앴다 — 모든 리포트가 예외 없이 2회를 쓰던 구조였고, 그 두 번째 호출은 검증과
무관하게 문장만 다듬었다. 지금의 두 번째 호출은 검증이 실패했을 때만, 무엇이
틀렸는지를 들고 나간다.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pydantic import ValidationError

from agents.report import (
    Basis,
    EvidenceLike,
    ReportEvidenceError,
    _evidence_value,
    _trigrams,
    order_report_evidences,
    resolve_bases,
    validate_reading,
)
from core.hexagram_engine import FOCUS_RULE_VERSION
from core.config import settings
from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from core.reading import ReadingEvidence
from schemas.hexagram_engine import FocusType
from schemas.report_v2 import (
    SCHEMA_VERSION,
    AcademicDetails,
    CastingDetail,
    CastingLine,
    CounselingHandoff,
    FocusRuleDetail,
    GenerationMetadata,
    NarrativeDraft,
    PreCounselingReport,
    ReportSource,
    SourceRole,
    UserFact,
)


logger = logging.getLogger(__name__)

REPORT_V2_PROMPT = "report_v2"
REPORT_V2_PROMPT_VERSION = "v2.0.0"

# 공개 오류 코드. 내부 예외 문자열·프롬프트·사용자 고민을 응답이나 일반 로그로
# 내보내지 않는다. 화면과 FE가 분기하는 값이므로 문자열을 함부로 바꾸지 않는다.
CODE_EVIDENCE_INVALID = "REPORT_EVIDENCE_INVALID"
CODE_NARRATIVE_INVALID = "REPORT_NARRATIVE_INVALID"
CODE_MODEL_FAILED = "REPORT_MODEL_FAILED"

_LINE_TYPE = {6: "노음", 7: "소양", 8: "소음", 9: "노양"}

# 본문에 나오면 안 되는 것 — 한중일 통합 한자.
# 원문은 근거 패널(`academic_details.sources`)에 있다. 본문에까지 실으면
# `AGENTS.md` 설계원칙 1("원문은 그대로 노출하지 않는다")이 프롬프트 문구 하나에
# 매달리게 된다. 프롬프트로 부탁하는 대신 검증에서 끊는다.
_HANJA = re.compile(r"[一-鿿㐀-䶿]")

# 아래 세 가지는 **보수적** 탐지다. 정규식이 의미 안전을 보장하지 않는다 —
# 어휘가 아니라 구조가 걸릴 때만 잡도록 좁게 썼고, 나머지는 평가 사례로 다룬다.
#
# 1) 책임 전가. "X 때문이 아니라 당신의 Y 때문입니다" 구조. 명세서 헤드라인
#    템플릿이 정확히 이 모양이었다. 직장내 괴롭힘·가정폭력 사연에서 피해자에게
#    원인을 돌린다.
_BLAME_SHIFT = re.compile(
    r"아니라[^.!?\n]{0,60}?(당신|본인|스스로|내면)[^.!?\n]{0,40}?(때문|부재|탓|없어서|못해서)"
)

# 2) 진단 단정. 병명을 **긍정 서술로** 확정하는 경우만. "우울증이 아닙니다",
#    "우울증인지 걱정된다고 하셨지요" 같은 문장은 걸리지 않는다.
_DIAGNOSIS = re.compile(
    r"(우울증|공황장애|불안장애|조울증|양극성장애|조현병|ADHD|성격장애|강박장애)"
    r"\s*(입니다|이십니다|이에요|예요|이시네요|을 앓고|를 앓고|이 있으십니다|가 있으십니다)"
)

# 3) 확정적 미래. 단정 부사 + 종결. "가능성", "조건" 같은 완화어가 같은 문장에
#    있으면 걸리지 않는다.
_CERTAIN_FUTURE = re.compile(
    r"(반드시|필연적으로|틀림없이|무조건)[^.!?\n]{0,40}?"
    r"(될 것입니다|됩니다|옵니다|일어납니다|하게 됩니다|실패합니다|무너집니다)"
)
_HEDGE = re.compile(r"(가능성|조건|살펴|점검|아닐 수도|달라질 수)")


class ReportGenerationError(RuntimeError):
    """리포트를 만들지 못했다. `code`는 공개해도 되는 안정된 문자열이다."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------------------
# 서버 확정 사실 조립
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。？！])\s+|\n+")


def build_user_facts(question: str, limit: int = 10) -> List[UserFact]:
    """사용자 발화를 문장 단위 발췌로 나눈다.

    서술이 "사용자가 이렇게 말했다"고 주장할 수 있는 **유일한** 근거다.
    여기에 없는 감정·과거·동기는 `pattern_hypothesis`에 가설로만 들어간다.
    """
    facts: List[UserFact] = []
    for piece in _SENTENCE_SPLIT.split(question or ""):
        text = piece.strip()
        if not text:
            continue
        facts.append(UserFact(id=f"U{len(facts) + 1}", text=text[:1000]))
        if len(facts) >= limit:
            break
    if not facts and (question or "").strip():
        facts.append(UserFact(id="U1", text=question.strip()[:1000]))
    return facts


def _source_from_basis(
    source_id: str, basis: Basis, role: SourceRole, hexagram_name: str
) -> ReportSource:
    return ReportSource(
        id=source_id,
        role=role,
        hexagram_id=basis.hexagram_id,
        hexagram_name=hexagram_name,
        line_number=basis.line_number,
        classical_text=basis.hanja,
        classical_translation=basis.korean or None,
        # 원전 위치를 확인할 수 없으면 비운다. 『역학계몽』의 편명·페이지를
        # 추측해 적지 않는다 — 확인 범위는 `data/PROVENANCE.md`에 있다.
        locator=None,
    )


def build_sources(
    reading: ReadingEvidence,
    evidences: Sequence[EvidenceLike],
    primary: Basis,
    auxiliary: Optional[Basis],
) -> List[ReportSource]:
    """근거 목록. **LLM이 채우는 칸이 하나도 없다.**

    역할을 갈라 둔다 — 주 근거, 보조, 배경, 체용 참작, 보충(대상전), 검색 주석.
    체용은 근거를 고르지 않고 읽는 무게만 보태므로 `body_use` 역할로 따로 선다.
    """
    orig, trans = reading.original, reading.transformed
    name_of = {orig.hexagram_id: orig.name_full}
    if trans:
        name_of[trans.hexagram_id] = trans.name_full

    sources: List[ReportSource] = []

    def next_id() -> str:
        return f"E{len(sources) + 1}"

    sources.append(
        _source_from_basis(
            next_id(), primary, SourceRole.PRIMARY, name_of.get(primary.hexagram_id, "")
        )
    )
    if auxiliary is not None:
        sources.append(
            _source_from_basis(
                next_id(), auxiliary, SourceRole.AUXILIARY,
                name_of.get(auxiliary.hexagram_id, ""),
            )
        )

    covered_judgments = {
        (s.hexagram_id, s.line_number) for s in sources if s.line_number is None
    }

    # 효사가 주 근거일 때 본괘 괘사는 배경이다. 주 근거로 올리지 않는다.
    line_focused = reading.focus_rule.focus_type in (
        FocusType.SINGLE_LINE_STATEMENT,
        FocusType.MULTIPLE_LINE_STATEMENTS,
        FocusType.SPECIAL_USE_LINE,
    )
    if line_focused and (orig.hexagram_id, None) not in covered_judgments and orig.judgment_text:
        sources.append(
            ReportSource(
                id=next_id(),
                role=SourceRole.BACKGROUND,
                hexagram_id=orig.hexagram_id,
                hexagram_name=orig.name_full,
                classical_text=orig.judgment_text,
                classical_translation=orig.judgment_ko or None,
            )
        )
        covered_judgments.add((orig.hexagram_id, None))

    # 체용이 가리키는 괘의 괘사가 아직 없으면 얹는다. "그 괘에 무게를 두라"면서
    # 그 괘사를 안 주면 모델이 없는 근거를 지어낼 자리가 생긴다.
    body_use_target = _body_use_hexagram(reading)
    if body_use_target is not None and (body_use_target.hexagram_id, None) not in covered_judgments:
        if body_use_target.judgment_text:
            sources.append(
                ReportSource(
                    id=next_id(),
                    role=SourceRole.BODY_USE,
                    hexagram_id=body_use_target.hexagram_id,
                    hexagram_name=body_use_target.name_full,
                    classical_text=body_use_target.judgment_text,
                    classical_translation=body_use_target.judgment_ko or None,
                )
            )

    # 대상전 — 보충이다. 0변효에서도 주 근거로 승격하지 않는다.
    if orig.xiang_text:
        sources.append(
            ReportSource(
                id=next_id(),
                role=SourceRole.SUPPLEMENT,
                hexagram_id=orig.hexagram_id,
                hexagram_name=orig.name_full,
                classical_text=orig.xiang_text,
                # 번역이 없으면 없는 대로 둔다. 다른 유형의 청크로 메우지 않는다.
                classical_translation=orig.xiang_ko,
            )
        )

    # 검색된 주석. 해석 에이전트가 출처별 몫으로 고른 그대로이며 여기서 자르지 않는다.
    ordered = order_report_evidences(evidences, primary.hexagram_id, primary.line_number)
    for item in ordered:
        content = (_evidence_value(item, "content", "") or "").strip()
        hex_id = _evidence_value(item, "hexagram_id")
        if not content or not hex_id:
            continue
        if len(sources) >= 30:
            break
        sources.append(
            ReportSource(
                id=next_id(),
                role=SourceRole.ANNOTATION,
                hexagram_id=int(hex_id),
                hexagram_name=name_of.get(int(hex_id), f"제{hex_id}괘"),
                line_number=_evidence_value(item, "line_number"),
                # 주석에는 원문이 아니라 한글 본문이 실린다. `classical_text`가
                # 비면 스키마가 막으므로 본문을 넣고, 원문 칸을 지어내지 않는다.
                classical_text=content[:2000],
                annotation=content[:4000],
                annotation_source=(_evidence_value(item, "source_title") or None),
            )
        )

    return sources


def _body_use_hexagram(reading: ReadingEvidence):
    """체용이 무게를 싣는 괘. 표준이면 None."""
    from schemas.hexagram_engine import BodyUseType

    kind = reading.focus_rule.body_use_type
    if kind == BodyUseType.EMPHASIZE_ORIGINAL:
        return reading.original
    if kind == BodyUseType.EMPHASIZE_TRANSFORMED:
        return reading.transformed
    return None


def build_casting(reading: ReadingEvidence) -> CastingDetail:
    cast = reading.cast_result
    lower, upper = _trigrams(cast.original_binary)
    return CastingDetail(
        lines=[
            CastingLine(
                position=l.position,
                value=l.value,
                line_type_ko=_LINE_TYPE[l.value],
                is_changing=l.is_changing,
            )
            for l in cast.lines
        ],
        original_hexagram_id=cast.original_hexagram_id,
        original_name=reading.original.name_full,
        original_lower_trigram=lower,
        original_upper_trigram=upper,
        changing_lines=list(cast.changing_lines),
        has_transformation=bool(cast.changing_lines),
        transformed_hexagram_id=cast.transformed_hexagram_id,
        transformed_name=reading.transformed.name_full if reading.transformed else None,
    )


def build_focus_detail(reading: ReadingEvidence) -> FocusRuleDetail:
    focus = reading.focus_rule
    return FocusRuleDetail(
        changing_count=len(reading.cast_result.changing_lines),
        focus_type=focus.focus_type.value,
        target_hexagram_type=focus.target_hexagram_type,
        target_line_numbers=list(focus.target_line_numbers),
        description_ko=focus.description_ko,
        body_use_type=focus.body_use_type.value,
        body_use_note_ko=focus.body_use_note_ko,
        rule_version=FOCUS_RULE_VERSION,
    )


def snapshot_hash(academic: AcademicDetails) -> str:
    """확정 근거 묶음의 지문.

    수정 호출이 **같은 근거**로 나갔는지, 저장된 리포트가 어느 근거에서 나왔는지를
    나중에 대조하려면 필요하다.
    """
    payload = academic.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------


def narrative_problems(
    draft: NarrativeDraft,
    source_ids: Sequence[str],
    fact_ids: Sequence[str],
) -> List[str]:
    """구조·참조는 결정적으로, 의미는 보수적으로 본다.

    돌려주는 문자열은 그대로 수정 요청 프롬프트에 들어간다. 사용자 고민이나 내부
    예외를 담지 않는다.
    """
    problems: List[str] = []
    known_sources = set(source_ids)
    known_facts = set(fact_ids)
    narrative = draft.narrative

    unknown = [r for r in narrative.perspective.evidence_refs if r not in known_sources]
    unknown += [r for r in narrative.value_direction.evidence_refs if r not in known_sources]
    if unknown:
        problems.append(
            f"evidence_refs에 제공되지 않은 근거 ID가 있습니다: {sorted(set(unknown))}. "
            f"허용된 ID는 {sorted(known_sources)}뿐입니다."
        )

    unknown_facts = [
        r for r in narrative.emotional_context.user_fact_refs if r not in known_facts
    ]
    if unknown_facts:
        problems.append(
            f"user_fact_refs에 제공되지 않은 발화 ID가 있습니다: {sorted(set(unknown_facts))}. "
            f"허용된 ID는 {sorted(known_facts)}뿐입니다."
        )

    if draft.counseling_handoff.suggested_action_title != narrative.micro_action_task.title:
        problems.append(
            "counseling_handoff.suggested_action_title이 micro_action_task.title과 다릅니다. "
            "제안한 행동은 하나여야 합니다."
        )

    for label, text in _narrative_texts(draft):
        if _HANJA.search(text):
            problems.append(
                f"{label}에 한자가 있습니다. 본문은 한글로만 씁니다 — "
                "원문은 근거 패널에 따로 실립니다."
            )
        if _BLAME_SHIFT.search(text):
            problems.append(
                f"{label}이 '…이 아니라 당신의 … 때문입니다' 구조로 원인을 단정합니다. "
                "환경·타인의 행동과 사용자의 선택 여지를 구분해 다시 쓰십시오."
            )
        if _DIAGNOSIS.search(text):
            problems.append(
                f"{label}에 병명을 확정하는 문장이 있습니다. 진단하지 않습니다."
            )
        if _CERTAIN_FUTURE.search(text) and not _HEDGE.search(text):
            problems.append(
                f"{label}이 미래를 확정적으로 말합니다. 점검할 조건과 가능성으로 바꾸십시오."
            )

    return problems


def _narrative_texts(draft: NarrativeDraft) -> List[Tuple[str, str]]:
    n = draft.narrative
    items: List[Tuple[str, str]] = [
        ("headline_metaphor", n.headline_metaphor),
        ("emotional_context.validation", n.emotional_context.validation),
        ("perspective.classical_reading", n.perspective.classical_reading),
        ("perspective.applied_reading", n.perspective.applied_reading),
        ("perspective.alternative_perspective", n.perspective.alternative_perspective),
        ("value_direction.rationale", n.value_direction.rationale),
        ("micro_action_task.title", n.micro_action_task.title),
        ("micro_action_task.when", n.micro_action_task.when),
        ("micro_action_task.completion_criterion", n.micro_action_task.completion_criterion),
        ("counseling_handoff.opening_question", draft.counseling_handoff.opening_question),
    ]
    if n.emotional_context.pattern_hypothesis:
        items.append(("emotional_context.pattern_hypothesis", n.emotional_context.pattern_hypothesis))
    if n.perspective.thought_observation:
        items.append(("perspective.thought_observation", n.perspective.thought_observation))
    if n.value_direction.proposed_value:
        items.append(("value_direction.proposed_value", n.value_direction.proposed_value))
    for i, cond in enumerate(n.value_direction.conditions_to_check):
        items.append((f"value_direction.conditions_to_check[{i}]", cond))
    for i, step in enumerate(n.micro_action_task.steps):
        items.append((f"micro_action_task.steps[{i}]", step))
    for i, h in enumerate(draft.counseling_handoff.working_hypotheses):
        items.append((f"counseling_handoff.working_hypotheses[{i}]", h))
    for i, u in enumerate(draft.counseling_handoff.unconfirmed_points):
        items.append((f"counseling_handoff.unconfirmed_points[{i}]", u))
    return items


def _validation_messages(exc: ValidationError) -> List[str]:
    """Pydantic 오류를 수정 요청에 쓸 수 있는 문장으로. 입력값은 싣지 않는다."""
    out: List[str] = []
    for err in exc.errors()[:20]:
        location = ".".join(str(p) for p in err.get("loc", ()))
        out.append(f"{location or '(최상위)'}: {err.get('msg', '형식 오류')}")
    return out


# ---------------------------------------------------------------------------
# 프롬프트
# ---------------------------------------------------------------------------


def build_context_block(
    question: str,
    topic_category: str,
    academic: AcademicDetails,
) -> str:
    """모델에게 주는 확정 사실. **한글만 담지 않는다** — 근거의 원문도 함께 준다.

    본문에 한자를 쓰지 말라는 요구와 원문을 주는 것은 다른 문제다. 원문이 없으면
    모델은 번역문만 보고 고전이 무슨 말을 했는지 추측하게 된다. 본문에 새는 것은
    검증에서 막는다.
    """
    lines = [
        "<confirmed_facts>",
        f"[사용자 발화 발췌] — 사실이라고 말할 수 있는 것은 이것뿐입니다",
    ]
    for fact in academic.user_facts:
        lines.append(f"  {fact.id}: {fact.text}")

    casting = academic.casting
    lines.append(f"[주제 분류] {topic_category}")
    lines.append(
        f"[괘] 본괘 {casting.original_name} (하괘 {casting.original_lower_trigram}, "
        f"상괘 {casting.original_upper_trigram})"
    )
    if casting.has_transformation:
        lines.append(f"     동효 {casting.changing_lines} → 지괘 {casting.transformed_name}")
    else:
        lines.append("     동효 없음 (불변괘). 지괘가 없습니다 — 있는 것처럼 쓰지 마십시오.")

    focus = academic.focus_rule
    lines.append(f"[초점 규칙] {focus.description_ko}")
    if focus.body_use_note_ko:
        lines.append(f"[체용 참작] {focus.body_use_note_ko}")

    lines.append("[근거] evidence_refs에는 아래 ID만 쓸 수 있습니다")
    for s in academic.sources:
        head = f"  {s.id} ({s.role.value}) {s.hexagram_name}"
        if s.line_number:
            head += f" {s.line_number}효" if s.line_number <= 6 else " 용구/용육"
        lines.append(head)
        lines.append(f"      원문: {s.classical_text}")
        if s.classical_translation:
            lines.append(f"      번역: {s.classical_translation}")
        else:
            lines.append("      번역: (없음 — 지어내지 마십시오)")
        if s.annotation and s.role == SourceRole.ANNOTATION:
            lines.append(f"      주석[{s.annotation_source or '출처 미상'}]: {s.annotation}")

    lines.append("</confirmed_facts>")
    lines.append("")
    lines.append(f'[사용자의 실제 질문] "{question}"')
    return "\n".join(lines)


_OUTPUT_CONTRACT = """
아래 JSON 하나만 반환하십시오. 주석·설명·코드펜스를 붙이지 마십시오.

{
  "narrative": {
    "headline_metaphor": "괘상에서 끌어낸 한 줄. 이 괘가 아니면 나올 수 없는 말이어야 합니다",
    "emotional_context": {
      "validation": "사용자가 실제로 쓴 말에 대한 공감",
      "pattern_hypothesis": "반복 패턴 가설. 근거가 없으면 null",
      "user_fact_refs": ["U1"]
    },
    "perspective": {
      "thought_observation": "스쳐 가는 생각으로 볼 만한 것. 없으면 null",
      "classical_reading": "고전이 말하는 바. 원전의 맥락 그대로",
      "applied_reading": "그것을 이번 사연에 옮기면",
      "alternative_perspective": "달리 볼 수 있는 각도",
      "evidence_refs": ["E1"]
    },
    "value_direction": {
      "proposed_value": "지킬 만한 가치. 확신이 없으면 null",
      "rationale": "왜 그 방향인지",
      "conditions_to_check": ["선택할 때 살펴볼 조건"],
      "evidence_refs": ["E1"]
    },
    "micro_action_task": {
      "title": "짧은 이름",
      "duration_minutes": 10,
      "when": "언제 할지. 생활 조건을 모르면 시각을 특정하지 마십시오",
      "steps": ["1~3단계"],
      "completion_criterion": "무엇을 보면 끝난 것인지",
      "smaller_alternative": "더 작게 줄인 것. 없으면 null"
    }
  },
  "counseling_handoff": {
    "working_hypotheses": ["상담에서 확인할 가설"],
    "unconfirmed_points": ["아직 모르는 것"],
    "suggested_action_title": "micro_action_task.title과 **같은 문자열**",
    "opening_question": "다음 턴을 여는 질문 하나"
  }
}
"""


def build_user_prompt(question: str, topic_category: str, academic: AcademicDetails) -> str:
    return (
        build_context_block(question, topic_category, academic)
        + "\n"
        + _OUTPUT_CONTRACT
    )


def build_repair_prompt(previous_prompt: str, problems: Sequence[str]) -> str:
    """수정 요청. **근거는 초안과 같아야 한다** — 그래서 앞 프롬프트를 그대로 싣는다."""
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        previous_prompt
        + "\n\n[검증 실패]\n"
        + "아래 문제를 고쳐 같은 JSON 구조로 다시 쓰십시오. "
        "근거와 사실은 위에 준 것에서 바꾸지 마십시오.\n"
        + listed
    )


# ---------------------------------------------------------------------------
# 생성
# ---------------------------------------------------------------------------


def _parse_draft(raw: Any) -> Tuple[Optional[NarrativeDraft], List[str]]:
    if not isinstance(raw, Mapping):
        return None, ["최상위가 JSON 객체가 아닙니다."]
    try:
        return NarrativeDraft.model_validate(dict(raw)), []
    except ValidationError as exc:
        return None, _validation_messages(exc)


async def run_report_v2_agent(
    *,
    question: str,
    session_id: str,
    reading: ReadingEvidence,
    evidences: Sequence[EvidenceLike],
    topic_category: str = "기타",
    client: Optional[LLMClient] = None,
    now: Optional[datetime] = None,
) -> PreCounselingReport:
    """v2 리포트를 만든다. 실패하면 `ReportGenerationError`를 던진다."""
    try:
        validate_reading(reading)
        primary, auxiliary = resolve_bases(reading)
        if not (primary.hanja or "").strip():
            raise ReportEvidenceError(f"주 근거 원문이 없습니다: {primary.label}")
        if auxiliary is not None and not (auxiliary.hanja or "").strip():
            raise ReportEvidenceError(f"보조 근거 원문이 없습니다: {auxiliary.label}")
    except ReportEvidenceError as exc:
        logger.error("v2 리포트 근거 오류: session=%s", session_id, exc_info=True)
        raise ReportGenerationError(CODE_EVIDENCE_INVALID, str(exc)) from exc

    academic = AcademicDetails(
        casting=build_casting(reading),
        focus_rule=build_focus_detail(reading),
        sources=build_sources(reading, evidences, primary, auxiliary),
        user_facts=build_user_facts(question),
    )

    # provider는 **우리가 고른 경우에만** 안다. 클라이언트를 주입받았으면 그것이
    # 어느 provider인지 서버가 알 길이 없으므로 미확인으로 둔다.
    provider = settings.LLM_PROVIDER if client is None else None
    llm = client or get_client("report")
    system_prompt = load_system_prompt(REPORT_V2_PROMPT)
    user_prompt = build_user_prompt(question, topic_category, academic)

    source_ids = [s.id for s in academic.sources]
    fact_ids = [f.id for f in academic.user_facts]

    draft: Optional[NarrativeDraft] = None
    repair_count = 0
    problems: List[str] = []

    for attempt in (0, 1):
        prompt = user_prompt if attempt == 0 else build_repair_prompt(user_prompt, problems)
        try:
            raw = llm.complete_json(prompt, system=system_prompt, temperature=0.1)
        except Exception as exc:
            logger.error(
                "v2 리포트 모델 호출 실패: session=%s attempt=%d", session_id, attempt,
                exc_info=True,
            )
            raise ReportGenerationError(CODE_MODEL_FAILED, type(exc).__name__) from exc

        candidate, problems = _parse_draft(raw)
        if candidate is not None:
            problems = narrative_problems(candidate, source_ids, fact_ids)
            if not problems:
                draft = candidate
                repair_count = attempt
                break

        if attempt == 1:
            break
        repair_count = 1
        logger.info(
            "v2 리포트 검증 실패, 같은 근거로 수정 요청: session=%s 문제=%d건",
            session_id, len(problems),
        )

    if draft is None:
        # 필수 서술이 빠진 것을 범용 조언으로 채워 `ready`로 위장하지 않는다.
        logger.error(
            "v2 리포트 검증 재실패: session=%s 문제=%s", session_id, problems[:5]
        )
        raise ReportGenerationError(CODE_NARRATIVE_INVALID, f"{len(problems)}건")

    stamp = (now or datetime.now(timezone.utc)).isoformat()
    return PreCounselingReport(
        schema_version=SCHEMA_VERSION,
        report_id=str(uuid.uuid4()),
        session_id=session_id,
        narrative=draft.narrative,
        academic_details=academic,
        counseling_handoff=draft.counseling_handoff,
        generation_metadata=GenerationMetadata(
            generated_at=stamp,
            # 클라이언트가 밝히지 않으면 미확인으로 둔다. 모르는 값을 적어 두면
            # 나중에 그 값으로 재현을 시도하게 된다.
            provider=_optional_str(provider),
            model=_optional_str(getattr(llm, "model_name", None)),
            prompt_version=_prompt_version(system_prompt),
            rule_version=FOCUS_RULE_VERSION,
            evidence_snapshot_hash=snapshot_hash(academic),
            repair_count=repair_count,
        ),
    )


def _optional_str(value: Any) -> Optional[str]:
    """문자열로 확인된 값만 남긴다.

    Mock이나 프록시 객체가 속성 접근만으로 값을 만들어 내는 경우가 있다. 그것이
    메타데이터에 실리면 "모델 이름"이라는 칸에 객체 표현이 박힌다 — 모르는 것은
    모른다고 두는 편이 낫다.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _prompt_version(system_prompt: str) -> str:
    """선언한 판본 + 실제 로드된 프롬프트의 지문.

    프롬프트 파일이 바뀌었는데 판본 문자열을 안 고치면 두 리포트를 구분할 수 없다.
    지문을 붙여 두면 적어도 같은 파일이었는지는 대조된다.
    """
    digest = hashlib.sha256((system_prompt or "").encode("utf-8")).hexdigest()[:8]
    return f"{REPORT_V2_PROMPT_VERSION}+{digest}"
