"""RAG 청크를 의미 검색한다 (4단계 확인용, 이후 에이전트가 쓸 조회 경로).

    python scripts/search_chunks.py "직장을 옮겨야 할지 모르겠다" --hexagram 47
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

from core.db import AsyncSessionLocal
from core.rag import search_chunks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=5)
    # 기본값을 두지 않는다. 1을 기본으로 두었더니 괘를 안 붙인 검색이 조용히
    # 건괘 안에서만 돌면서 전체를 훑은 것처럼 보였다.
    ap.add_argument("--hexagram", type=int, required=True, help="이 괘로 좁힌다 (필수)")
    ap.add_argument("--source-type", default=None, help="sosang_comm 등으로 좁힌다")
    args = ap.parse_args()

    async def _run():
        source_types = [args.source_type] if args.source_type else None
        async with AsyncSessionLocal() as session:
            return await search_chunks(
                session,
                args.query,
                hexagram_id=args.hexagram,
                source_types=source_types,
                k=args.k,
            )

    rows = asyncio.run(_run())
    print(f"질의: {args.query}")
    print(f"범위: 제{args.hexagram}괘\n")
    for chunk in rows:
        pos = f" {chunk.line_number}효" if chunk.line_number else ""
        print(f"[유사도 {chunk.similarity:.3f}] 제{chunk.hexagram_id}괘{pos} · {chunk.source_type}")
        print(f"  {chunk.content_ko[:150]}")
        print(f"  원문: {chunk.content[:70]}")
        print()


if __name__ == "__main__":
    main()

