"""해석 에이전트의 RAG 검색 범위 검증."""

import pytest

from agents.interpret import _annotation_block, _render_mapping, run_interpret
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
    monkeypatch.setattr("agents.interpret.search_balanced", rec)

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
    monkeypatch.setattr("agents.interpret.search_balanced", rec)

    async with AsyncSessionLocal() as session:
        await run_interpret(
            session, "새로 시작해도 될까요", manual_lines=[9, 8, 8, 8, 6, 8], client=StubLLM()
        )

    assert rec.calls
    for call in rec.calls:
        assert isinstance(call["hexagram_id"], int)
        assert 1 <= call["hexagram_id"] <= 64


def _chunk(hid, line, stype, ko="번역"):
    return RetrievedChunk(
        chunk_id=f"{stype}-{hid}-{line}", hexagram_id=hid, line_number=line,
        source_type=stype, category="annotation", content="원문", content_ko=ko,
        similarity=0.7,
    )


def test_괘_단위_주석이_많아도_초점_효_주석이_잘리지_않는다():
    """예전에는 합친 목록을 `chunks[:4]`로 잘랐다.

    붙는 순서가 괘 단위 → 초점 효 → 지괘라, 괘 단위가 4건 이상이면 초점 효의 주석이
    한 건도 남지 않았다. 규칙이 주 근거로 지목한 효의 주석을 통째로 버리고 괘 전체의
    일반론만 넘긴 셈이다. 그러면 모델은 괘 이름의 통념으로 물러나고, 통념은 여러 괘가
    공유하므로 어느 괘를 뽑아도 답이 비슷해진다.
    """
    괘단위 = [_chunk(39, None, "guasa_comm") for _ in range(3)] + \
             [_chunk(39, None, "benui_guasa") for _ in range(2)]
    초점효 = [_chunk(39, 2, "line_comm"), _chunk(39, 2, "line_comm"),
              _chunk(39, 2, "benui_line")]

    lines, used = _annotation_block(초점효, 괘단위, [])
    block = "\n".join(lines)

    assert used[:3] == 초점효, "초점 효 주석이 맨 앞에 와야 한다"
    assert sum(1 for c in used if c.line_number == 2) == 3
    assert block.index("초점 효의 주석") < block.index("괘 전체의 주석")
    assert "효사 주석(2효)" in block and "본의 효사 주석(2효)" in block
    assert "line_comm" not in block, "내부 출처 코드가 프롬프트에 새면 안 된다"


def test_번역이_빈_주석은_근거로도_프롬프트로도_나가지_않는다():
    """한문으로 대신하지 않는다. 근거 패널에도 빈 항목을 내지 않는다."""
    lines, used = _annotation_block([], [_chunk(39, None, "guasa_comm", ko="  ")], [])

    assert used == []
    assert lines == []


def test_칸들이_매핑_앞에_렌더된다():
    """이 값은 `counsel_turns.contextual_mapping`을 타고 후속 턴까지 간다.

    칸을 스키마에만 두면 세션 둘째 턴부터 사라진다 — 매핑을 저장하지 않아 사연이
    그 자리를 메우던 것과 똑같은 일이 벌어진다.
    """
    렌더 = _render_mapping(
        {
            "focus_image": "누런 소가죽으로 묶어 아무도 풀 수 없음",
            "image_position": "붙드는 쪽",
            "only_this_line": "물러나는 때인데도 뜻만은 놓지 않는다",
        },
        "접더라도 놓지 않을 것이 무엇인지가 이 자리의 물음입니다.",
    )

    assert 렌더.splitlines()[0].startswith("효사의 형상:")
    assert "이 효만의 것: 물러나는 때인데도" in 렌더
    assert 렌더.splitlines()[-1].startswith("— 접더라도")


def test_빈_칸은_머리만_남기지_않는다():
    """머리만 남은 칸은 모델이 채워 넣을 빈자리가 된다."""
    렌더 = _render_mapping(
        {"focus_image": "", "image_position": "   ", "only_this_line": None},
        "괘사가 주 근거라 형상이라 할 것이 없습니다.",
    )

    assert 렌더 == "괘사가 주 근거라 형상이라 할 것이 없습니다."
    assert "효사의 형상" not in 렌더


def test_칸을_안_채우는_모델도_예전처럼_돌아간다():
    """구조를 안 따르는 모델에게 없는 칸을 만들어 넣지 않는다."""
    assert _render_mapping({}, "지금은 힘을 모을 때입니다.") == "지금은 힘을 모을 때입니다."
