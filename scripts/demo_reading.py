"""
질문 -> 괘 도출 -> DB 원문(괘사/효사) 조회까지의 파이프라인 데모.

아직 에이전트(안전 스크리닝/정리/해석/상담)는 구현 전이라 AI 상담 문장은 없다.
여기서는 엔진이 어떤 원문 근거를 짚어내는지만 확인한다.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.db import AsyncSessionLocal
from core.hexagram_engine import cast_hexagram
from core.models.hexagram import Hexagram, Line


async def fetch_hexagram(session, hex_id: int) -> Hexagram:
    stmt = select(Hexagram).where(Hexagram.id == hex_id)
    hexagram = (await session.execute(stmt)).scalar_one()
    return hexagram


async def fetch_line(session, hex_id: int, line_number: int) -> Line:
    stmt = select(Line).where(Line.hexagram_id == hex_id, Line.line_number == line_number)
    line = (await session.execute(stmt)).scalar_one()
    return line


def print_hexagram_header(label: str, hexagram: Hexagram):
    print(f"\n[{label}] 제{hexagram.id}괘 {hexagram.name_full} ({hexagram.name_hanja}) {hexagram.symbol or ''}")


async def run(query: str):
    result = cast_hexagram(method="coin")

    async with AsyncSessionLocal() as session:
        original = await fetch_hexagram(session, result.original_hexagram_id)
        transformed = (
            await fetch_hexagram(session, result.transformed_hexagram_id)
            if result.transformed_hexagram_id
            else None
        )

        print("=" * 64)
        print(f" 질문: {query}")
        print("=" * 64)

        print_hexagram_header("본괘", original)
        print(f"  괘사(원문): {original.judgment_text}")
        if original.judgment_ko:
            print(f"  괘사(한글): {original.judgment_ko}")

        if transformed:
            print_hexagram_header("지괘", transformed)
            print(f"  괘사(원문): {transformed.judgment_text}")
            if transformed.judgment_ko:
                print(f"  괘사(한글): {transformed.judgment_ko}")

        if result.changing_lines:
            print(f"\n[동효] {result.changing_lines}")

        rule = result.focus_rule
        print("\n--- 주자 점법 해석 지침 ---")
        print(f"  {rule.description_ko}")

        target = transformed if rule.target_hexagram_type == "TRANSFORMED" else original
        if target and rule.target_line_numbers:
            print("\n--- 근거 효사 (DB 조회) ---")
            for pos in rule.target_line_numbers:
                line = await fetch_line(session, target.id, pos)
                tag = "용구/용육" if pos == 7 else f"{pos}효"
                print(f"  [{tag}] 원문: {line.statement_text}")
                if line.statement_ko:
                    print(f"        한글: {line.statement_ko}")
                if line.small_xiang_text:
                    print(f"        소상전: {line.small_xiang_text}")

    print("\n" + "=" * 64)


if __name__ == "__main__":
    q = input("고민을 한 문장으로 입력하세요: ").strip() or "질문 미입력"
    asyncio.run(run(q))
