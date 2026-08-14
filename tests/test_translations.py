"""3단계 번역 적재 검증 (HANDOFF E-2).

세 가지를 본다.
  1. 450건이 빠짐없이 채워졌는가
  2. 원문이 한 글자도 변하지 않았는가  ← 적재가 원문을 건드리면 여기서 걸린다
  3. 용어표 핵심어가 일관되게 쓰였는가

적재를 아직 안 했으면 1·3번은 건너뛴다. 시작도 안 한 상태와 하다 만 상태는
다른 사건이라, **한 건이라도 들어와 있으면 건너뛰지 않고 실패시킨다.**
2번은 적재 여부와 무관하게 항상 돈다.
"""
import json
import os

import pytest
from sqlalchemy import func, select

from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "hexagrams.json")

# 번역문에 반드시 이 우리말로 나타나야 하는 핵심어.
# 확정 용어표(pilot/GLOSSARY.md)에서 뜻이 갈릴 여지가 없는 것만 골랐다.
CORE_TERMS = {
    "高宗": "고종",
    "鬼方": "귀방",
    "童蒙": "동몽",
    "桎梏": "질곡",
    "臀": "볼기",
}


async def _translated_counts(session):
    gua = (await session.execute(
        select(func.count()).select_from(Hexagram).where(Hexagram.judgment_ko.isnot(None))
    )).scalar()
    hyo = (await session.execute(
        select(func.count()).select_from(Line).where(Line.statement_ko.isnot(None))
    )).scalar()
    return gua, hyo


@pytest.mark.asyncio
async def test_원문이_변하지_않았다():
    """DB의 원문이 data/hexagrams.json과 한 글자도 다르지 않아야 한다."""
    source = {h["hexagram_id"]: h for h in json.load(open(DATA, encoding="utf-8"))}

    async with AsyncSessionLocal() as session:
        for h in (await session.execute(select(Hexagram))).scalars().all():
            assert h.judgment_text == source[h.id]["guasa"]["original"], f"괘{h.id} 괘사 원문 변경됨"

        for l in (await session.execute(select(Line))).scalars().all():
            src = next(x for x in source[l.hexagram_id]["lines"] if x["position"] == l.line_number)
            assert l.statement_text == src["original"], f"괘{l.hexagram_id} {l.line_number}효 원문 변경됨"
            assert (l.small_xiang_text or "") == (src.get("sosang") or ""), \
                f"괘{l.hexagram_id} {l.line_number}효 소상전 변경됨"


@pytest.mark.asyncio
async def test_450건이_빠짐없이_채워졌다():
    async with AsyncSessionLocal() as session:
        gua, hyo = await _translated_counts(session)
        if gua == 0 and hyo == 0:
            pytest.skip("번역 적재 전이다 (load_translations.py 미실행)")

        assert gua == 64, f"괘사 번역 {gua}/64 — {64 - gua}건 비어 있다"
        assert hyo == 386, f"효사 번역 {hyo}/386 — {386 - hyo}건 비어 있다"

        # 공백만 든 값도 비어 있는 것으로 친다
        blank = (await session.execute(
            select(func.count()).select_from(Line)
            .where(Line.statement_ko.isnot(None), func.btrim(Line.statement_ko) == "")
        )).scalar()
        assert blank == 0, f"내용이 빈 효사 번역 {blank}건"


@pytest.mark.asyncio
async def test_용어표_핵심어가_일관되게_쓰였다():
    """원문에 그 한자가 있으면 번역문에 정한 우리말이 있어야 한다."""
    source = {h["hexagram_id"]: h for h in json.load(open(DATA, encoding="utf-8"))}

    async with AsyncSessionLocal() as session:
        gua, hyo = await _translated_counts(session)
        if gua == 0 and hyo == 0:
            pytest.skip("번역 적재 전이다 (load_translations.py 미실행)")

        violations = []
        for l in (await session.execute(select(Line))).scalars().all():
            if not l.statement_ko:
                continue
            src = next(x for x in source[l.hexagram_id]["lines"] if x["position"] == l.line_number)
            for hanja, korean in CORE_TERMS.items():
                if hanja in src["original"] and korean not in l.statement_ko:
                    violations.append(f"괘{l.hexagram_id} {l.line_number}효: {hanja}→'{korean}' 없음")

        assert not violations, "용어표 위반 %d건\n  %s" % (
            len(violations), "\n  ".join(violations[:15]))
