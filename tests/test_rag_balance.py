"""정전·본의를 갈라 뽑는 검색 검증 (네트워크 없음).

한 풀에 던져 상위 k건을 받으면 무엇을 근거로 삼을지가 검색 순위의 우연에 맡겨진다.
본의는 중앙값 31자로 짧아 밀리기 쉽고, 반대로 질의어와 촘촘히 겹쳐 정전을 밀어낼
수도 있다. 그래서 출처별로 정해진 몫을 따로 뽑는다.
"""

import pytest

import core.rag as rag


class 검색기록:
    """`_search_with_vector` 호출을 받아 적는 대역."""

    def __init__(self):
        self.calls = []
        self.embeds = 0

    def embed(self, text, *, use_cache=False):
        self.embeds += 1
        return [0.1] * 768

    async def search(self, session, vec, *, hexagram_id, line_number=None,
                     source_types=None, k=5):
        self.calls.append({"types": list(source_types or []), "k": k,
                           "hexagram_id": hexagram_id, "line_number": line_number})
        return [
            rag.RetrievedChunk(
                chunk_id=f"x{len(self.calls)}-{i}", hexagram_id=hexagram_id,
                line_number=line_number, source_type=(source_types or ["?"])[0],
                category="annotation", content="원문", content_ko="번역",
                similarity=0.5,
            )
            for i in range(k)
        ]


@pytest.fixture
def 기록(monkeypatch):
    r = 검색기록()
    monkeypatch.setattr(rag, "embed_query", r.embed)
    monkeypatch.setattr(rag, "_search_with_vector", r.search)
    return r


@pytest.mark.asyncio
async def test_정전과_본의를_각각_정해진_몫만큼_뽑는다(기록):
    out = await rag.search_balanced(None, "기다려야 할까", hexagram_id=5)

    assert len(기록.calls) == 2
    정전, 본의 = 기록.calls
    assert 정전["k"] == 3 and 본의["k"] == 2
    assert "line_comm" in 정전["types"] and "benui_line" not in 정전["types"]
    assert 본의["types"] == rag.BENUI_TYPES
    assert len(out) == 5
    assert out[0].source_type in rag.JEONGJEON_TYPES, "정전이 앞에 온다"


@pytest.mark.asyncio
async def test_질의는_한_번만_임베딩한다(기록):
    """출처별로 두 번 검색한다고 임베딩까지 두 번 하면 돈과 지연이 그대로 두 배다."""
    await rag.search_balanced(None, "기다려야 할까", hexagram_id=5)
    assert 기록.embeds == 1


@pytest.mark.asyncio
async def test_본의를_0으로_두면_아예_검색하지_않는다(기록):
    """톤 대조용 스위치. 인덱스를 두 벌 만들면 다른 것까지 같이 달라진다."""
    out = await rag.search_balanced(None, "기다려야 할까", hexagram_id=5, k_benui=0)

    assert len(기록.calls) == 1
    assert 기록.calls[0]["types"] == rag.JEONGJEON_TYPES
    assert all(c.source_type not in rag.BENUI_TYPES for c in out)


@pytest.mark.asyncio
async def test_괘를_지정하지_않으면_검색하지_않는다(기록):
    with pytest.raises(ValueError):
        await rag.search_balanced(None, "질의", hexagram_id=None)
    assert 기록.calls == [], "괘를 좁히지 않은 검색이 나가면 안 된다"


@pytest.mark.asyncio
async def test_재검색도_같은_비율로_나눠_뽑는다(기록):
    """첫 검색만 균형을 잡고 재검색이 한 풀에서 뽑으면 대화가 길어질수록 쏠린다."""
    retrieve = rag.make_retriever(None, hexagram_id=5)
    await retrieve("왜 그렇게 보시나요")

    assert [c["k"] for c in 기록.calls] == [3, 2]
    assert 기록.calls[1]["types"] == rag.BENUI_TYPES
