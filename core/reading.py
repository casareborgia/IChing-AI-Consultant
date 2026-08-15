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
from schemas.hexagram_engine import FocusRuleResult


@dataclass
class LineEvidence:
    """효사 및 소상전 확정 근거."""

    hexagram_id: int
    line_number: int  # 1~6 또는 7(용구/용육)
    position_name: str
    statement_text: str
    statement_ko: str
    small_xiang_text: Optional[str] = None


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

    @property
    def summary_korean(self) -> str:
        """상담 프롬프트 및 맥락 매핑에 주입할 확정 한글 근거 요약."""
        parts = []
        orig = self.original
        parts.append(f"본괘: 제{orig.hexagram_id}괘 {orig.name_full} ({orig.name_hanja})")
        parts.append(f"본괘 괘사: {orig.judgment_ko}")

        if self.transformed:
            trans = self.transformed
            parts.append(f"지괘: 제{trans.hexagram_id}괘 {trans.name_full} ({trans.name_hanja})")
            parts.append(f"지괘 괘사: {trans.judgment_ko}")

        parts.append(f"해석 초점: {self.focus_rule.description_ko}")

        if self.target_lines:
            parts.append("핵심 효사:")
            for line in self.target_lines:
                pos_label = "용구/용육" if line.line_number == 7 else f"{line.line_number}효"
                parts.append(f"- [{pos_label}] {line.statement_ko}")
                if line.small_xiang_text:
                    parts.append(f"  (상전 원문: {line.small_xiang_text})")

        return "\n".join(parts)


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
    )
