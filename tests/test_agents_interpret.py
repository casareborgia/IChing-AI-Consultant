"""해석 에이전트의 RAG 검색 범위 검증."""

import pytest

from agents.interpret import run_interpret
from core.db import AsyncSessionLocal
from core.rag import RetrievedChunk


class RecordingSearch:
    """search_chunks 호출 인자를 기록하는 대역."""

    def __init__(self):
        self.calls = []

    async def __call__(self, session, query, *, hexagram_id, line_number=None, **kwargs):
        self.calls.append({"hexagram_id": hexagram_id, "line_number": line_number})
        return [
            RetrievedChunk(
                chunk_id="c", hexagram_id=hexagram_id, line_number=line_number,
                source_type="line_comm", category="annotation",
                content="원문", content_ko="번역", similarity=0.7,
            )
        ]


class StubLLM:
    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        return {"contextual_mapping": "상황 매핑"}


@pytest.mark.asyncio
async def test_초점이_지괘면_효_검색도_지괘로_좁힌다(monkeypatch):
    """동효 5개면 볼 효사는 지괘의 효다.

    본괘 ID로 검색하면 효 번호만 같고 괘가 다른 주석이 딸려와, DB 확정 근거와
    RAG 근거가 서로 다른 괘를 가리키게 된다.
    """
    rec = RecordingSearch()
    monkeypatch.setattr("agents.interpret.search_chunks", rec)

    async with AsyncSessionLocal() as session:
        interp, evidence, _ = await run_interpret(
            session,
            "지금 물러나야 할까요",
            manual_lines=[9, 9, 9, 9, 9, 7],  # 동효 5개
            client=StubLLM(),
        )

    assert evidence.focus_rule.target_hexagram_type == "TRANSFORMED"
    line_calls = [c for c in rec.calls if c["line_number"] is not None]
    assert line_calls, "효 단위 검색이 있어야 한다"
    for call in line_calls:
        assert call["hexagram_id"] == interp.transformed_hexagram_id
        assert call["hexagram_id"] != interp.original_hexagram_id


@pytest.mark.asyncio
async def test_모든_RAG_검색이_괘로_좁혀진다(monkeypatch):
    """좁히지 않은 검색이 한 건도 없어야 한다."""
    rec = RecordingSearch()
    monkeypatch.setattr("agents.interpret.search_chunks", rec)

    async with AsyncSessionLocal() as session:
        await run_interpret(
            session, "새로 시작해도 될까요", manual_lines=[9, 8, 8, 8, 6, 8], client=StubLLM()
        )

    assert rec.calls
    for call in rec.calls:
        assert isinstance(call["hexagram_id"], int)
        assert 1 <= call["hexagram_id"] <= 64
