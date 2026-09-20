"""[4] 괘해석 리포트 생성 에이전트.

리포트는 **점법을 판단하지 않는다.** 무엇을 근거로 삼을지는 공통 엔진
(`core.hexagram_engine.calculate_focus_rule`)이 정하고, 그 근거의 원문·번역은
`core.reading.build_evidence`가 DB에서 1:1로 조회한다. 이 모듈은 조립된
`ReadingEvidence`를 받아 서술만 만든다.

예전에는 여기에 `determine_gobyeonjeom_rule()`이라는 **두 번째 점법 엔진**이 있었다.
공통 엔진이 이미 판단해 넘긴 `focus_rule`을 받아놓고 쓰지 않은 채 다시 계산했고,
두 판단이 실제로 갈렸다:

- 동효 3개: 공통 엔진은 본괘·지괘 괘사를 함께 싣고 본괘를 위주로 한다(BOTH).
  리포트는 초효가 동효에 포함되는지로 본괘/지괘 **하나만** 골랐다.
- 동효 4개: 초점은 지괘의 부동효에 있는데, 리포트의 보조 효는 **본괘** 동효에서
  가져왔다. 상담사가 말하는 괘와 리포트가 인용하는 원문이 다른 괘였다.
- 동효 6개: 건·곤 판정을 괘 ID가 아니라 이름 문자열(`"중천건" in name`)로 했다.

그래서 화면의 리포트와 상담 답변이 같은 괘에서 서로 다른 근거를 댈 수 있었다.
이제 규칙은 한 곳에만 있다.
"""

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from core.hexagram_engine import hexagram_id_to_binary
from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from core.reading import HexagramEvidence, LineEvidence, ReadingEvidence
from schemas.counsel import EvidenceItem
from schemas.hexagram_engine import FocusType
from schemas.report import (
    HexagramReportSchema,
    QuestionSettingSchema,
    HexagramCastingSchema,
    LineCastingItem,
    FocusAndBodyUseSchema,
    SectionItemSchema,
)


logger = logging.getLogger(__name__)


class ReportEvidenceError(ValueError):
    """확정 근거가 성립하지 않는다. 임의 값으로 메우지 않고 리포트를 실패시킨다."""


# 3비트(아래→위)로 팔괘를 정한다. DB에 상·하괘 칼럼이 없어서 예전에는
# `getattr(hex_obj, "upper_trigram", "") or "상괘"`가 **항상** "상괘"를 돌려줬다.
# 화면에는 상괘 이름 자리에 "상괘"라는 글자가 그대로 나갔다. 이진 코드에서
# 결정되는 값이므로 조회할 것이 아니라 계산하면 된다.
_TRIGRAM_BY_BITS = {
    "111": "건(하늘)",
    "110": "태(못)",
    "101": "리(불)",
    "100": "진(우레)",
    "011": "손(바람)",
    "010": "감(물)",
    "001": "간(산)",
    "000": "곤(땅)",
}

_LINE_NAMES = ["1효 (초효)", "2효 (이효)", "3효 (삼효)", "4효 (사효)", "5효 (오효)", "6효 (상효)"]

# 효 수치 → (명칭, 기호, 설명). 6/7/8/9 밖의 값은 검증에서 걸러진다.
_LINE_KIND = {
    6: ("노음", "⚋✕", "동효(변효) (음에서 양으로 변함)"),
    7: ("소양", "⚊", "변하지 않는 양효"),
    8: ("소음", "⚋", "변하지 않는 음효"),
    9: ("노양", "⚊○", "동효(변효) (양에서 음으로 변함)"),
}

_CHANGING_VALUES = frozenset({6, 9})


def _line_name(pos: int) -> str:
    return _LINE_NAMES[pos - 1] if 1 <= pos <= 6 else f"{pos}효"


def _trigrams(binary: str) -> Tuple[str, str]:
    """(하괘, 상괘). 이진 코드는 초효가 index 0이다."""
    lower = _TRIGRAM_BY_BITS.get(binary[0:3], "")
    upper = _TRIGRAM_BY_BITS.get(binary[3:6], "")
    return lower, upper


# ---------------------------------------------------------------------------
# 확정 근거 검증
# ---------------------------------------------------------------------------


def validate_reading(reading: ReadingEvidence) -> None:
    """넘어온 괘가 스스로 모순되지 않는지 본다.

    엔진이 만든 `HexagramCastResult`는 이 조건을 이미 만족한다. 그래도 여기서 다시
    보는 이유는 **리포트가 손으로 만든 괘를 받아들이지 않게** 하기 위해서다. 예전
    파이프라인은 `getattr(interp_res, "lines_val", [7, 8, 9, 8, 9, 7])`처럼 6효를
    기본값으로 채웠다 — 그 기본값이 쓰이면 화면의 수리 표가 실제 뽑힌 괘와 무관한
    숫자를 보여준다. 조용히 메우는 대신 끊는다.
    """
    cast = reading.cast_result
    lines = cast.lines

    if len(lines) != 6:
        raise ReportEvidenceError(f"6효가 아닙니다: {len(lines)}개")

    if [l.position for l in lines] != [1, 2, 3, 4, 5, 6]:
        raise ReportEvidenceError(
            f"효 위치가 초효~상효 순서가 아닙니다: {[l.position for l in lines]}"
        )

    bad = [l.value for l in lines if l.value not in _LINE_KIND]
    if bad:
        raise ReportEvidenceError(f"효 수치는 6·7·8·9만 허용합니다: {bad}")

    derived_changing = [l.position for l in lines if l.value in _CHANGING_VALUES]
    if derived_changing != sorted(cast.changing_lines):
        raise ReportEvidenceError(
            f"동효 목록이 효 수치와 어긋납니다: 수치 기준 {derived_changing}, "
            f"선언된 값 {sorted(cast.changing_lines)}"
        )

    # 효 수치가 곧 괘다. 본괘 ID와 맞지 않으면 둘 중 하나가 거짓이다.
    orig_bits = "".join("1" if l.value in (7, 9) else "0" for l in lines)
    if orig_bits != hexagram_id_to_binary(cast.original_hexagram_id):
        raise ReportEvidenceError(
            f"6효 수치가 본괘 제{cast.original_hexagram_id}괘와 맞지 않습니다: {orig_bits}"
        )

    if derived_changing:
        trans_bits = "".join("1" if l.value in (6, 7) else "0" for l in lines)
        if cast.transformed_hexagram_id is None:
            raise ReportEvidenceError("동효가 있는데 지괘가 없습니다")
        if trans_bits != hexagram_id_to_binary(cast.transformed_hexagram_id):
            raise ReportEvidenceError(
                f"변한 6효가 지괘 제{cast.transformed_hexagram_id}괘와 맞지 않습니다: {trans_bits}"
            )
    elif cast.transformed_hexagram_id is not None:
        raise ReportEvidenceError(
            f"동효가 없는데 지괘 제{cast.transformed_hexagram_id}괘가 있습니다"
        )

    # 조회된 원문이 그 괘의 것인지.
    if reading.original.hexagram_id != cast.original_hexagram_id:
        raise ReportEvidenceError(
            f"본괘 원문이 다른 괘입니다: 괘 {cast.original_hexagram_id}, "
            f"원문 {reading.original.hexagram_id}"
        )
    if cast.transformed_hexagram_id is None:
        if reading.transformed is not None:
            raise ReportEvidenceError("불변괘인데 지괘 원문이 조립됐습니다")
    else:
        if reading.transformed is None:
            raise ReportEvidenceError("지괘가 있는데 지괘 원문이 없습니다")
        if reading.transformed.hexagram_id != cast.transformed_hexagram_id:
            raise ReportEvidenceError(
                f"지괘 원문이 다른 괘입니다: 괘 {cast.transformed_hexagram_id}, "
                f"원문 {reading.transformed.hexagram_id}"
            )


# ---------------------------------------------------------------------------
# 초점 규칙 → 주/보조 근거
# ---------------------------------------------------------------------------


class Basis:
    """근거 한 건. 원문이 없으면 만들지 않는다."""

    __slots__ = ("label", "hanja", "korean", "hexagram_id", "line_number")

    def __init__(
        self,
        label: str,
        hanja: str,
        korean: str,
        hexagram_id: int,
        line_number: Optional[int] = None,
    ) -> None:
        self.label = label
        self.hanja = hanja
        self.korean = korean
        self.hexagram_id = hexagram_id
        self.line_number = line_number


def _judgment_basis(hexagram: HexagramEvidence, role: str) -> Basis:
    return Basis(
        label=f"{hexagram.name_full} 괘사{role}",
        hanja=hexagram.judgment_text or "",
        korean=hexagram.judgment_ko or "",
        hexagram_id=hexagram.hexagram_id,
    )


def _line_basis(line: LineEvidence, hexagram: HexagramEvidence) -> Basis:
    pos = "용구/용육" if line.line_number == 7 else f"{line.line_number}효"
    return Basis(
        label=f"{hexagram.name_full} {pos} 효사",
        hanja=line.statement_text or "",
        korean=line.statement_ko or "",
        hexagram_id=line.hexagram_id,
        line_number=line.line_number,
    )


def resolve_bases(reading: ReadingEvidence) -> Tuple[Basis, Optional[Basis]]:
    """초점 규칙이 정한 주 근거와 보조 근거를 꺼낸다.

    **판단하지 않는다.** `focus_rule`이 이미 내린 결정을 원문에 연결할 뿐이다.
    보조 근거가 있는 자리는 두 곳뿐이다 — 효사가 둘인 경우(동효 2개·4개)와
    본괘·지괘 괘사를 함께 보는 경우(동효 3개)다.
    """
    focus = reading.focus_rule
    orig, trans = reading.original, reading.transformed
    lines = reading.target_lines

    if focus.focus_type == FocusType.ORIGINAL_JUDGMENT:
        return _judgment_basis(orig, ""), None

    if focus.focus_type == FocusType.TRANSFORMED_JUDGMENT:
        if trans is None:
            raise ReportEvidenceError("지괘 괘사가 초점인데 지괘가 없습니다")
        return _judgment_basis(trans, ""), None

    if focus.focus_type == FocusType.BOTH_JUDGMENTS:
        # 동효 3개. 《역학계몽》은 본괘·지괘 괘사를 함께 보되 본괘를 위주로 한다.
        # 예전 리포트는 초효 포함 여부로 하나만 골랐다 — 나머지 한쪽이 통째로 빠졌다.
        if trans is None:
            raise ReportEvidenceError("본괘·지괘 괘사가 초점인데 지괘가 없습니다")
        return _judgment_basis(orig, "(위주)"), _judgment_basis(trans, "(참작)")

    # 효사 초점 — SINGLE_LINE_STATEMENT / MULTIPLE_LINE_STATEMENTS / SPECIAL_USE_LINE
    if not lines:
        raise ReportEvidenceError(
            f"효사가 초점({focus.focus_type})인데 대상 효사가 조립되지 않았습니다"
        )

    # 효사를 어느 괘에서 꺼낼지는 build_evidence가 이미 정했다. 동효 4~5개면
    # 지괘의 효다 — 여기서 본괘로 되돌리면 초점과 원문이 어긋난다.
    owner = trans if focus.target_hexagram_type == "TRANSFORMED" and trans else orig

    primary = _line_basis(lines[0], owner)
    auxiliary = _line_basis(lines[1], owner) if len(lines) > 1 else None
    return primary, auxiliary


def require_source_text(basis: Basis, role: str) -> None:
    """원문이 비면 근거 오류다.

    한글 번역을 한자 자리에 대신 넣거나 LLM에게 원문을 지어내게 하지 않는다.
    번역이 없으면 번역만 없는 것으로 둔다 — 원문과 번역은 서로를 대신하지 않는다.
    """
    if not (basis.hanja or "").strip():
        raise ReportEvidenceError(f"{role} 원문이 없습니다: {basis.label}")


# ---------------------------------------------------------------------------
# RAG 근거
# ---------------------------------------------------------------------------

EvidenceLike = Union[EvidenceItem, Mapping[str, Any]]


def _evidence_value(evidence: EvidenceLike, key: str, default: Any = None) -> Any:
    if isinstance(evidence, Mapping):
        return evidence.get(key, default)
    return getattr(evidence, key, default)


def order_report_evidences(
    evidences: Sequence[EvidenceLike],
    target_hex_id: int,
    target_line_number: Optional[int],
) -> List[EvidenceLike]:
    """초점 효/괘의 근거를 앞으로 당긴다. **자르지 않는다.**

    예전에는 여기서 `limit=6`으로 잘랐다. 넘어오는 목록은 해석 에이전트가 이미
    출처별 몫으로 나눠 고른 것(초점 효 3 · 괘 단위 3 · 지괘 2 = 최대 8건)이라,
    6건으로 다시 자르면 우선순위가 가장 낮은 지괘 주석이 통째로 사라진다.

    2026-08-18에 `agents/interpret.py`에서 고쳤던 것과 같은 결함이다. 초점 효의
    주석이 손에 없으면 모델은 괘 이름의 통념으로 물러나고, 통념은 여러 괘가
    공유하므로 **어느 괘를 뽑아도 같은 말이 나온다.** 몫을 나눠 고른 것을 뒤에서
    다시 자르면 그 수고가 없던 일이 된다.
    """
    indexed = list(enumerate(evidences))

    def priority(item: Tuple[int, EvidenceLike]) -> Tuple[int, int]:
        index, evidence = item
        same_hex = _evidence_value(evidence, "hexagram_id") == target_hex_id
        line_number = _evidence_value(evidence, "line_number")
        exact_line = target_line_number is not None and same_hex and line_number == target_line_number
        whole_hex = target_line_number is None and same_hex and line_number is None
        return (0 if exact_line or whole_hex else 1 if same_hex else 2, index)

    return [evidence for _, evidence in sorted(indexed, key=priority)]


# ---------------------------------------------------------------------------
# 서술 생성
# ---------------------------------------------------------------------------


def _extract_section_interpretation(res_dict: Dict[str, Any], key: str, fallback_default: str) -> str:
    val = res_dict.get(key)
    if isinstance(val, dict):
        return val.get("interpretation") or val.get("text") or fallback_default
    elif isinstance(val, str) and val.strip():
        return val.strip()
    return fallback_default


def _require_report_draft(res_dict: Dict[str, Any]) -> Dict[str, str]:
    """불완전한 모델 출력을 정상 맞춤 리포트로 위장하지 않는다."""
    required = (
        "section1_diagnosis",
        "section2_action",
        "section3_warning",
        "section4_future",
        "final_summary",
    )
    values = {key: _extract_section_interpretation(res_dict, key, "") for key in required}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"리포트 LLM 응답 필드 누락: {', '.join(missing)}")
    return values


def _casting_items(reading: ReadingEvidence) -> List[LineCastingItem]:
    items: List[LineCastingItem] = []
    for line in reading.cast_result.lines:
        type_ko, symbol, note = _LINE_KIND[line.value]
        items.append(
            LineCastingItem(
                position=line.position,
                name=_line_name(line.position),
                value=line.value,
                line_type_ko=type_ko,
                symbol=symbol,
                is_changing=line.is_changing,
                note=note,
            )
        )
    return items


def _body_use_flow(reading: ReadingEvidence) -> str:
    """체용 문구. 없는 흐름을 지어내지 않는다.

    예전에는 불변괘에서도 "본괘(X)에서 지괘(X)로 나아가는 흐름"이라고 썼다.
    지괘가 없는 괘에 지괘를 말한 것이다. 체용 보완은 지괘가 특수 18괘일 때만
    성립하므로, 그렇지 않으면 적용되지 않았다고 말한다.
    """
    if reading.focus_rule.body_use_note_ko:
        return reading.focus_rule.body_use_note_ko
    if reading.transformed is None:
        return "동효가 없어 지괘가 없습니다. 체용(體用) 보완 규칙은 적용되지 않습니다."
    return (
        f"지괘가 {reading.transformed.name_full}이며 체용(體用) 보완 대상 18괘에 들지 "
        "않습니다. 표준 고변점 규칙대로 읽습니다."
    )


async def run_report_agent(
    *,
    question: str,
    reading: ReadingEvidence,
    evidences: Sequence[EvidenceLike],
    topic_category: str = "기타",
    client: Optional[LLMClient] = None,
    enable_refinement_loop: bool = True,
) -> HexagramReportSchema:
    """확정 근거(`ReadingEvidence`) 위에 리포트 서술을 얹는다.

    DB 조회를 하지 않는다. 원문·번역·괘 이름은 `core.reading`이 이미 조립해 넘긴
    것을 그대로 쓴다. 이 모듈이 따로 조회하면 "확정 근거가 한 곳에서 나온다"는
    보장이 깨진다.
    """
    validate_reading(reading)

    llm = client or get_client("report")
    system_prompt = load_system_prompt("report")

    cast = reading.cast_result
    focus = reading.focus_rule
    orig, trans = reading.original, reading.transformed
    has_trans = trans is not None

    primary, auxiliary = resolve_bases(reading)
    require_source_text(primary, "주 근거")
    if auxiliary is not None:
        require_source_text(auxiliary, "보조 근거")

    orig_lower, orig_upper = _trigrams(cast.original_binary)

    selected_evidences = order_report_evidences(
        evidences, primary.hexagram_id, primary.line_number
    )
    evidence_texts = [
        f"[{_evidence_value(e, 'source_title', '고전주석')}] {_evidence_value(e, 'content', '')}"
        for e in selected_evidences
    ]
    rag_context = "\n".join(evidence_texts) if evidence_texts else "제공된 주석 없음"

    aux_block = (
        f"- Auxiliary Basis: {auxiliary.label}\n"
        f"- Auxiliary Basis Hanja: {auxiliary.hanja}\n"
        f"- Auxiliary Basis (Korean): {auxiliary.korean or 'None'}"
        if auxiliary
        else "- Auxiliary Basis: None"
    )
    body_use_line = (
        f"- Body-Use Supplement: {focus.body_use_note_ko}"
        if focus.body_use_note_ko
        else "- Body-Use Supplement: None"
    )

    user_prompt = f"""<actual_divination_context>
- User's Real Question: "{question}"
- Topic Category: {topic_category}
- Original Hexagram: {orig.name_full}({orig.name_hanja}) — 하괘 {orig_lower}, 상괘 {orig_upper}
- Original Judgment (Korean): {orig.judgment_ko or 'None'}
- Changing Lines: {cast.changing_lines if cast.changing_lines else 'None (Invariant)'}
- Transformed Hexagram: {f"{trans.name_full}({trans.name_hanja})" if trans else 'None (Invariant)'}
- Transformed Judgment (Korean): {trans.judgment_ko if trans else 'None'}

[Focus Rule — 주자 점법, core.hexagram_engine]
- Changing Count: {len(cast.changing_lines)}
- Focus Type: {focus.focus_type.value}
- Rule Description: {focus.description_ko}
- Primary Basis: {primary.label}
- Primary Basis Hanja: {primary.hanja}
- Primary Basis (Korean): {primary.korean or 'None'}
{aux_block}
{body_use_line}

[RAG Classical Annotations]
{rag_context}
</actual_divination_context>

[CRITICAL INSTRUCTION - DOMAIN CONTEXT ALIGNMENT & NO TEMPLATE CLICHES]
Write a razor-sharp, highly customized I-Ching consulting report in Korean adhering strictly to the JSON schema below.
- Derive terminology, emotional tone, and metaphors only from the User's Real Question and Topic Category ({topic_category}).
- Do not import vocabulary, entities, goals, or assumptions from a domain absent from the user's question.
- Avoid repetitive template phrasing. Vary sentence openings and reasoning structure according to the supplied evidence.
- Map the ancient I-Ching metaphors ('{primary.hanja}') 1:1 to the user's specific real-world question ('{question}') in fluid, elegant, natural Korean prose.

Return a JSON with these exact string keys:
{{
  "section1_diagnosis": "Deep diagnosis of the user's situation using the original hexagram metaphor in rich Korean prose (2-3 sentences)",
  "section2_action": "Specific 1:1 action guidance mapping '{primary.hanja}' to the user's question",
  "section3_warning": "Solemn cautions or bad habits to avoid based on the auxiliary basis and changing dynamics",
  "section4_future": "Future direction based on the transformed hexagram, or on holding the present situation if there is none",
  "final_summary": "Powerful 1-2 sentence final wisdom summary"
}}
"""

    try:
        draft_dict = llm.complete_json(user_prompt, system=system_prompt, temperature=0.1)
        draft = _require_report_draft(draft_dict)
        sec1_text = draft["section1_diagnosis"]
        sec2_text = draft["section2_action"]
        sec3_text = draft["section3_warning"]
        sec4_text = draft["section4_future"]
        final_summary_text = draft["final_summary"]

        if enable_refinement_loop:
            try:
                refine_prompt = f"""You are a Master Scribe refining an I-Ching report into a masterpiece in Korean.
Review the following interpretations for the user's question: "{question}" (Topic: {topic_category})

Section 1: {sec1_text}
Section 2: {sec2_text}
Section 3: {sec3_text}
Section 4: {sec4_text}
Final Summary: {final_summary_text}

[CRITICAL INSTRUCTION]
1. Remove repetitive phrasing and vary sentence openings according to the supplied evidence.
2. Deepen the 1:1 mapping with the target Hanja ('{primary.hanja}').
3. Derive all domain vocabulary from the user's question and supplied category. Do not introduce concepts from an absent domain.
4. Write in highly elegant, fluid, and natural Korean prose with respectful honorifics.

Return a JSON with exact keys: "section1_diagnosis", "section2_action", "section3_warning", "section4_future", "final_summary"."""

                refined_dict = llm.complete_json(refine_prompt, system=system_prompt, temperature=0.1)
                sec1_text = _extract_section_interpretation(refined_dict, "section1_diagnosis", sec1_text)
                sec2_text = _extract_section_interpretation(refined_dict, "section2_action", sec2_text)
                sec3_text = _extract_section_interpretation(refined_dict, "section3_warning", sec3_text)
                sec4_text = _extract_section_interpretation(refined_dict, "section4_future", sec4_text)
                final_summary_text = refined_dict.get("final_summary") or final_summary_text
            except Exception as ref_err:
                logger.warning("리포트 정제 호출 실패, 초안 사용: %s", ref_err, exc_info=True)

    except Exception as e:
        logger.error("리포트 LLM 초안 생성 실패", exc_info=True)
        raise RuntimeError("맞춤 해석 리포트 생성에 실패했습니다") from e

    section3_title = (
        f"③ 보조 경계 지침 ({auxiliary.label})" if auxiliary else "③ 보조 경계 지침 (경계 지침)"
    )
    section4_title = (
        f"④ 미래의 귀결 및 주의점 (지괘: {trans.name_full})"
        if has_trans
        else "④ 미래의 귀결 및 주의점 (본괘 유지)"
    )

    return HexagramReportSchema(
        question_setting=QuestionSettingSchema(
            question=question,
            # 사용자의 마음가짐은 서버가 확인할 수 없다. 예전에는 "무념무상의 경건한
            # 마음으로 점을 쳤습니다"라고 모든 리포트에 적었다 — 확인한 적 없는 사실이다.
            # 서버가 실제로 보장하는 것만 적는다: 이 세션의 괘는 다시 뽑지 않는다.
            mindset_rule=(
                "재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 "
                "다시 뽑지 않고 그대로 이어집니다."
            ),
        ),
        hexagram_casting=HexagramCastingSchema(
            lines=_casting_items(reading),
            original_hex_id=orig.hexagram_id,
            original_name_full=orig.name_full,
            original_name_hanja=orig.name_hanja,
            original_upper_trigram=orig_upper,
            original_lower_trigram=orig_lower,
            original_summary=orig.judgment_ko or "",
            has_transformation=has_trans,
            transformed_hex_id=trans.hexagram_id if trans else None,
            transformed_name_full=trans.name_full if trans else None,
            transformed_name_hanja=trans.name_hanja if trans else None,
            transformed_summary=(trans.judgment_ko or "") if trans else None,
        ),
        focus_and_body_use=FocusAndBodyUseSchema(
            changing_count=len(cast.changing_lines),
            rule_description=focus.description_ko,
            primary_target_name=primary.label,
            body_use_flow=_body_use_flow(reading),
        ),
        section1_diagnosis=SectionItemSchema(
            title=f"① 현재 상황 진단 (본괘: {orig.name_full})",
            target_name=orig.name_full,
            hanja_text=orig.name_hanja,
            interpretation=sec1_text,
        ),
        section2_action=SectionItemSchema(
            title=f"② 핵심 행동 지침 (주 해석 대상: {primary.label})",
            target_name=primary.label,
            hanja_text=primary.hanja,
            interpretation=sec2_text,
        ),
        section3_warning=SectionItemSchema(
            title=section3_title,
            target_name=auxiliary.label if auxiliary else "경계 지침",
            hanja_text=auxiliary.hanja if auxiliary else None,
            interpretation=sec3_text,
        ),
        section4_future=SectionItemSchema(
            title=section4_title,
            target_name=trans.name_full if trans else orig.name_full,
            hanja_text=(trans.judgment_text or "") if trans else None,
            interpretation=sec4_text,
        ),
        final_summary=final_summary_text,
    )
