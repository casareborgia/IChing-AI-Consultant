"""4단계 RAG 청크 적재 검증.

가장 중요한 것은 **넣으면 안 되는 것이 안 들어갔는가**다. 괘사·효사 원문이
인덱스에 있으면 의미 검색으로 엉뚱한 괘의 괘사를 끌어오게 된다. 그것들은
엔진의 focus_rule이 가리키는 대로 DB에서 1:1로 꺼내야 한다.
"""
import json
import os

import pytest
from sqlalchemy import func, select

from core.db import AsyncSessionLocal
from core.models.rag import InterpretationChunk

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data", "hexagrams_kanripo.json")
CHUNKS = os.path.join(ROOT, "data", "rag_chunks_kanripo.json")

ALLOWED_SOURCE_TYPES = {
    "gwa_intro", "guasa_comm", "tanjon", "tanjon_comm", "daesang", "daesang_comm",
    "line_comm", "sosang", "sosang_comm",
}


def _expected_count() -> int:
    """청크 파일에서 센다. 숫자를 박아두면 청크가 늘 때마다 테스트가 깨진다.

    파일과 맞대면 "DB를 다시 적재하지 않았다"는 것까지 잡힌다 — 하드코딩된
    숫자는 그걸 못 잡는다. 실제로 저본 이관 때 1,751 → 1,752로 늘면서
    이 테스트가 깨졌고, 숫자만 고쳤다면 같은 일이 또 생겼을 것이다.
    """
    return len(json.load(open(CHUNKS, encoding="utf-8")))


async def _count(session):
    return (await session.execute(select(func.count()).select_from(InterpretationChunk))).scalar()


@pytest.mark.asyncio
async def test_청크가_모두_적재되고_임베딩됐다():
    async with AsyncSessionLocal() as session:
        n = await _count(session)
        if n == 0:
            pytest.skip("청크 적재 전이다 (embed_chunks.py 미실행)")

        expected = _expected_count()
        assert n == expected, (
            f"청크 {n}건 (파일은 {expected}건) — "
            "청크를 다시 만들었으면 embed_chunks.py도 다시 돌려야 한다")

        no_vec = (await session.execute(
            select(func.count()).select_from(InterpretationChunk)
            .where(InterpretationChunk.embedding.is_(None)))).scalar()
        assert no_vec == 0, f"임베딩이 없는 청크 {no_vec}건"

        no_ko = (await session.execute(
            select(func.count()).select_from(InterpretationChunk)
            .where(InterpretationChunk.content_ko.is_(None)))).scalar()
        assert no_ko == 0, f"한글 번역이 없는 청크 {no_ko}건 — 임베딩은 한글에 건다"

        hexes = (await session.execute(
            select(func.count(func.distinct(InterpretationChunk.hexagram_id))))).scalar()
        assert hexes == 64, f"괘 커버리지 {hexes}/64 — 비어 있는 괘가 있으면 검색이 쏠린다"


@pytest.mark.asyncio
async def test_넣으면_안_되는_것이_안_들어갔다():
    """괘사·효사 원문과 문언전은 인덱스에 있으면 안 된다."""
    source = {h["hexagram_id"]: h for h in json.load(open(DATA, encoding="utf-8"))}

    async with AsyncSessionLocal() as session:
        if await _count(session) == 0:
            pytest.skip("청크 적재 전이다")

        types_ = {r[0] for r in (await session.execute(
            select(InterpretationChunk.source_type).distinct())).all()}

        assert types_ <= ALLOWED_SOURCE_TYPES, f"허용되지 않은 출처: {types_ - ALLOWED_SOURCE_TYPES}"

        # 괘사·효사 원문이 통째로 청크에 들어갔는지 실제 문자열로 확인한다.
        # source_type 이름만 보면 놓친다 — 잘못된 값이 들어와도 이름은 맞을 수 있다.
        contents = {r[0] for r in (await session.execute(
            select(InterpretationChunk.content))).all()}
        for hid, h in source.items():
            assert h["guasa"]["original"] not in contents, f"괘{hid} 괘사 원문이 인덱스에 있다"
            for line in h["lines"]:
                assert line["original"] not in contents, \
                    f"괘{hid} {line['position']}효 효사 원문이 인덱스에 있다"
            if h["munon"]["original"]:
                assert h["munon"]["original"] not in contents, f"괘{hid} 문언전이 인덱스에 있다"
