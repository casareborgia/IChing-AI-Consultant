"""RAG 청크를 의미 검색한다 (4단계 확인용, 이후 에이전트가 쓸 조회 경로).

    python scripts/search_chunks.py "직장을 옮겨야 할지 모르겠다"
    python scripts/search_chunks.py "기다려야 할까" --hexagram 5 -k 5

질의는 **RETRIEVAL_QUERY**로 임베딩한다. 적재는 RETRIEVAL_DOCUMENT였다.
둘을 맞추지 않으면 같은 모델이라도 결과가 눈에 띄게 나빠진다.

`--hexagram`으로 좁히는 쓰임이 실제 경로다. 엔진이 괘를 먼저 확정하고,
그 괘에 붙은 근거만 검색해야 한다. 좁히지 않으면 64괘 전체에서 끌어오므로
지금 뽑은 괘와 무관한 해설이 상담 답변에 섞인다.
"""
import argparse
import asyncio
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.config import settings
from core.db import AsyncSessionLocal
from core.models.rag import InterpretationChunk

EMBED_MODEL = "text-multilingual-embedding-002"


def embed_query(text: str) -> List[float]:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=settings.GOOGLE_CLOUD_PROJECT,
                          location=settings.GEMINI_LOCATION)
    resp = client.models.embed_content(
        model=EMBED_MODEL, contents=[text],
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return resp.embeddings[0].values


async def search(query: str, k: int, hexagram: Optional[int], source_type: Optional[str]):
    vec = embed_query(query)
    async with AsyncSessionLocal() as session:
        stmt = select(
            InterpretationChunk,
            InterpretationChunk.embedding.cosine_distance(vec).label("dist"),
        )
        if hexagram:
            stmt = stmt.where(InterpretationChunk.hexagram_id == hexagram)
        if source_type:
            stmt = stmt.where(InterpretationChunk.source_type == source_type)
        stmt = stmt.order_by("dist").limit(k)
        return (await session.execute(stmt)).all()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--hexagram", type=int, default=None, help="이 괘로 좁힌다")
    ap.add_argument("--source-type", default=None, help="sosang_comm 등으로 좁힌다")
    args = ap.parse_args()

    rows = asyncio.run(search(args.query, args.k, args.hexagram, args.source_type))
    print(f"질의: {args.query}")
    if args.hexagram:
        print(f"범위: 제{args.hexagram}괘")
    print()
    for chunk, dist in rows:
        pos = f" {chunk.line_number}효" if chunk.line_number else ""
        print(f"[유사도 {1 - dist:.3f}] 제{chunk.hexagram_id}괘{pos} · {chunk.source_type}")
        print(f"  {chunk.content_ko[:150]}")
        print(f"  원문: {chunk.content[:70]}")
        print()


if __name__ == "__main__":
    main()
