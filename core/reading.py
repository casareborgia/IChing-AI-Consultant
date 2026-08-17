"""괘 도출 결과에 따른 DB 확정 근거(괘사·효사·소상전) 조립 모듈.

- 주자 점법 Focus Rule에 맞춰 DB에서 1:1로 확정 원문 및 한글 번역 조회
- LLM 의미 검색(RAG)이 아닌 정형 DB 쿼리로 무결성 보장
"""

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.hexagram_engine import HexagramCastResult
from core.models.hexagram import Hexagram, Line
from core.models.rag import InterpretationChunk
from schemas.hexagram_engine import BodyUseType, FocusRuleResult, FocusType

# 체용 참작 절의 머리. 주 근거와 섞이지 않게 하려고 절을 갈라 둔다 —
# 이 문자열로 요약을 쪼개면 "주 해석 근거에 무엇이 들었는지"를 정확히 셀 수 있다.
BODY_USE_SUPPLEMENT_HEADER = "체용 참작(주 근거가 아닙니다):"


@dataclass
class LineEvidence:
    """효사 및 소상전 확정 근거."""

    hexagram_id: int
    line_number: int  # 1~6 또는 7(용구/용육)
    position_name: str
    statement_text: str
    statement_ko: str
    small_xiang_text: Optional[str] = None   # 한문. 근거 표시용이며 프롬프트에 넣지 않는다
    small_xiang_ko: Optional[str] = None     # 한글. 상담 프롬프트에는 이쪽만 나간다


@dataclass
class HexagramEvidence:
    """괘 확정 정보 및 괘사."""

    hexagram_id: int
    name_full: str
    name_hanja: str
    judgment_text: str
    judgment_ko: str
    symbol: Optional[str] = None


@dataclass
class ReadingEvidence:
    """도출된 괘와 초점 규칙에 따른 최종 확정 근거 묶음."""

    cast_result: HexagramCastResult
    original: HexagramEvidence
    transformed: Optional[HexagramEvidence]
    focus_rule: FocusRuleResult
    target_lines: List[LineEvidence] = field(default_factory=list)
    target_hexagram_id: int = 0  # 초점이 가리키는 괘. RAG 검색도 이 괘로 좁혀야 한다

    @property
    def summary_korean(self) -> str:
        """상담 프롬프트에 주입할 확정 근거 요약. **한글만 담는다.**

        한문을 넣지 않는 것은 프롬프트 문구 하나에 기대지 않기 위해서다. 모델
        손에 한문이 있으면 답변에 새어 나오고, 그러면 "원문을 그대로 노출하지
        않는다"는 원칙이 프롬프트 한 줄에 매달리게 된다. 애초에 주지 않는다.

        **무엇을 주 근거로 삼을지는 오직 focus_rule이 정한다.** 6효가 모두 변한
        일반괘는 지괘 괘사만 본다 — 본괘 괘사를 늘 맨 앞에 붙이면 엔진이 갈라둔
        구분이 프롬프트에서 다시 뭉개진다.

        체용(體用)은 근거를 고르지 않는다. 읽는 무게만 보탠다. 그래서 체용이
        가리키는 괘의 괘사가 주 근거에 없을 때는 `체용 참작` 절에 따로 얹는다 —
        "그 괘에 무게를 두라"면서 그 괘의 괘사를 안 주면 모델이 없는 근거를
        지어낼 자리가 생긴다. 절을 갈라 두는 이유는 주 근거와 섞이지 않게
        하려는 것이다.
        """
        orig, trans = self.original, self.transformed
        focus = self.focus_rule.focus_type

        # 괘 이름도 한글만 쓴다. 상담사에게 乾이 필요하지 않다 — 중천건이면 충분하다.
        parts = [f"본괘: 제{orig.hexagram_id}괘 {orig.name_full}"]
        if trans:
            parts.append(f"지괘: 제{trans.hexagram_id}괘 {trans.name_full}")
        parts.append(f"해석 초점: {self.focus_rule.description_ko}")
        if self.focus_rule.body_use_note_ko:
            parts.append(f"체용(體用) 보완: {self.focus_rule.body_use_note_ko}")

        parts.append("주 해석 근거:")
        if focus == FocusType.ORIGINAL_JUDGMENT:
            parts.append(f"- 본괘 괘사: {orig.judgment_ko}")
        elif focus == FocusType.BOTH_JUDGMENTS:
            parts.append(f"- 본괘 괘사(위주): {orig.judgment_ko}")
            if trans:
                parts.append(f"- 지괘 괘사(참작): {trans.judgment_ko}")
        elif focus == FocusType.TRANSFORMED_JUDGMENT:
            if trans:
                parts.append(f"- 지괘 괘사: {trans.judgment_ko}")
        else:
            for line in self.target_lines:
                pos_label = "용구/용육" if line.line_number == 7 else f"{line.line_number}효"
                parts.append(f"- [{pos_label}] {line.statement_ko}")
                if line.small_xiang_ko:
                    parts.append(f"  (소상전) {line.small_xiang_ko}")
            # 효사가 주 근거일 때 괘사는 배경으로만 둔다
            parts.append(f"배경 — 본괘 괘사: {orig.judgment_ko}")

        참작 = self._body_use_supplement()
        if 참작:
            parts.append(BODY_USE_SUPPLEMENT_HEADER)
            parts.append(참작)

        return "\n".join(parts)

    def _body_use_supplement(self) -> Optional[str]:
        """체용이 가리키는 괘의 괘사가 주 근거에 없으면 그 한 줄을 돌려준다.

        이미 주 근거에 들어 있으면 None이다 — 같은 괘사를 두 번 싣지 않는다.
        효사가 주 근거인 경우 본괘 괘사는 '배경'으로 이미 실려 있으므로 본괘
        쪽은 보탤 것이 없다.
        """
        body_use = self.focus_rule.body_use_type
        focus = self.focus_rule.focus_type

        if body_use == BodyUseType.EMPHASIZE_TRANSFORMED:
            if self.transformed and focus != FocusType.TRANSFORMED_JUDGMENT:
                return f"- 지괘 괘사: {self.transformed.judgment_ko}"
            return None

        if body_use == BodyUseType.EMPHASIZE_ORIGINAL:
            if focus == FocusType.TRANSFORMED_JUDGMENT:
                return f"- 본괘 괘사: {self.original.judgment_ko}"
            return None

        return None


async def _get_hexagram(session: AsyncSession, hex_id: int) -> HexagramEvidence:
    stmt = select(Hexagram).where(Hexagram.id == hex_id)
    h = (await session.execute(stmt)).scalar_one()
    return HexagramEvidence(
        hexagram_id=h.id,
        name_full=h.name_full or "",
        name_hanja=h.name_hanja,
        judgment_text=h.judgment_text,
        judgment_ko=h.judgment_ko or "",
        symbol=h.symbol,
    )


async def _get_small_xiang_ko(session: AsyncSession, hex_id: int, line_num: int) -> Optional[str]:
    """소상전 한글 번역을 가져온다.

    `lines` 테이블에는 소상전 한문만 있고 번역은 청크 쪽에 있다. 다만 이건
    의미 검색이 아니라 (괘, 효)로 딱 떨어지는 1:1 조회다 — 386건이 중복 없이
    한 줄씩 붙어 있다. 확정 근거를 검색으로 찾지 말라는 원칙에 걸리지 않는다.
    """
    stmt = select(InterpretationChunk.content_ko).where(
        InterpretationChunk.source_type == "sosang",
        InterpretationChunk.hexagram_id == hex_id,
        InterpretationChunk.line_number == line_num,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_line(session: AsyncSession, hex_id: int, line_num: int) -> LineEvidence:
    stmt = select(Line).where(Line.hexagram_id == hex_id, Line.line_number == line_num)
    line = (await session.execute(stmt)).scalar_one()
    pos_name = "용구/용육" if line_num == 7 else f"{line_num}효"
    return LineEvidence(
        hexagram_id=line.hexagram_id,
        line_number=line.line_number,
        position_name=pos_name,
        statement_text=line.statement_text,
        statement_ko=line.statement_ko or "",
        small_xiang_text=line.small_xiang_text,
        small_xiang_ko=await _get_small_xiang_ko(session, hex_id, line_num),
    )



async def build_evidence(
    session: AsyncSession,
    cast: HexagramCastResult,
) -> ReadingEvidence:
    """주자 점법 규칙에 따라 본괘/지괘 및 대상 효사를 DB에서 조회하여 조립합니다.

    - target_hexagram_type (ORIGINAL, TRANSFORMED, BOTH) 처리
    - target_line_numbers (1~7, 용구/용육 포함) 처리
    """
    orig_ev = await _get_hexagram(session, cast.original_hexagram_id)
    trans_ev = (
        await _get_hexagram(session, cast.transformed_hexagram_id)
        if cast.transformed_hexagram_id
        else None
    )

    rule = cast.focus_rule
    target_lines: List[LineEvidence] = []

    # 대상 괘 결정
    target_hex_id = (
        cast.transformed_hexagram_id
        if rule.target_hexagram_type == "TRANSFORMED" and cast.transformed_hexagram_id
        else cast.original_hexagram_id
    )

    for line_num in rule.target_line_numbers:
        line_ev = await _get_line(session, target_hex_id, line_num)
        target_lines.append(line_ev)

    return ReadingEvidence(
        cast_result=cast,
        original=orig_ev,
        transformed=trans_ev,
        focus_rule=rule,
        target_lines=target_lines,
        target_hexagram_id=target_hex_id,
    )
