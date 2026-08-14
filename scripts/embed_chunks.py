"""RAG 청크를 임베딩해 DB에 적재한다 (4단계).

    python scripts/embed_chunks.py --translations data/translations/chunks_claude.json
    python scripts/embed_chunks.py --translations ... --dry-run

임베딩은 **한글 번역문**에 건다. 사용자의 고민이 한국어라 한문에 걸면 검색이
붙지 않는다. 한문 원문은 content에 그대로 남겨 근거 제시에 쓴다.

task_type은 RETRIEVAL_DOCUMENT다. 검색할 때는 RETRIEVAL_QUERY로 물어야 한다.
둘을 맞추지 않으면 같은 모델이라도 성능이 눈에 띄게 떨어진다.

이 테이블은 원본에서 다시 만들 수 있는 파생 데이터이므로, 적재는 전량 교체다.
부분 갱신을 하려면 청크를 식별할 자연키가 필요한데 지금 스키마에는 없다.
"""
import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, func, select

from core.config import settings
from core.db import AsyncSessionLocal
from core.models.rag import InterpretationChunk

EMBED_MODEL = "text-multilingual-embedding-002"
EMBED_DIM = 768          # 모델 출력 차원. 스키마의 Vector(768)과 맞아야 한다
BATCH = 25               # 한 번에 보낼 텍스트 수


def embed_texts(texts: List[str]) -> List[List[float]]:
    from google import genai
    from google.genai import types

    client = genai.Client(
        vertexai=True,
        project=settings.GOOGLE_CLOUD_PROJECT,
        location=settings.GEMINI_LOCATION,
    )
    out: List[List[float]] = []
    for i in range(0, len(texts), BATCH):
        part = texts[i:i + BATCH]
        resp = client.models.embed_content(
            model=EMBED_MODEL,
            contents=part,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        out.extend([e.values for e in resp.embeddings])
        print(f"  임베딩 {min(i + BATCH, len(texts))}/{len(texts)}")
    return out


def merge(chunks: List[Dict[str, Any]], translations_path: str):
    """청크 원본과 번역을 붙인다. 번역이 없거나 실패한 것은 제외한다."""
    tr = {str(r["id"]): r for r in json.load(open(translations_path, encoding="utf-8"))}
    ready, skipped = [], []
    for c in chunks:
        rec = tr.get(str(c["id"]))
        text = (rec or {}).get("translation_ko") or ""
        status = ((rec or {}).get("_meta") or {}).get("status")
        if rec is None:
            skipped.append((c["id"], "번역 없음"))
        elif status == "failed":
            skipped.append((c["id"], "번역 실패"))
        elif not text.strip():
            skipped.append((c["id"], "번역이 비어 있음"))
        else:
            ready.append({**c, "content_ko": text.strip()})
    return ready, skipped


async def load(rows: List[Dict[str, Any]], vectors: List[List[float]], dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        before = (await session.execute(
            select(func.count()).select_from(InterpretationChunk))).scalar()
        await session.execute(delete(InterpretationChunk))
        session.add_all([
            InterpretationChunk(
                hexagram_id=r["hexagram_id"],
                line_number=r["line_number"],
                category=r["category"],
                source_type=r["source_type"],
                content=r["content"],
                content_ko=r["content_ko"],
                embedding=v,
            )
            for r, v in zip(rows, vectors)
        ])
        if dry_run:
            await session.rollback()
            print(f"--dry-run: 되돌렸다 (기존 {before}건 그대로).")
        else:
            await session.commit()
            print(f"적재 완료: {before}건 → {len(rows)}건")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="data/rag_chunks.json")
    ap.add_argument("--translations", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="앞에서 N건만 (연결 시험용)")
    args = ap.parse_args()

    chunks = json.load(open(args.chunks, encoding="utf-8"))
    if args.limit:
        chunks = chunks[:args.limit]

    rows, skipped = merge(chunks, args.translations)
    print(f"청크 {len(chunks)}건 → 임베딩 대상 {len(rows)}건 / 제외 {len(skipped)}건")
    if skipped:
        for cid, why in skipped[:10]:
            print(f"  제외 {cid}: {why}")
        if len(skipped) > 10:
            print(f"  … 외 {len(skipped) - 10}건")

    vectors = embed_texts([r["content_ko"] for r in rows])
    bad = [i for i, v in enumerate(vectors) if len(v) != EMBED_DIM]
    if bad:
        raise SystemExit(f"차원이 {EMBED_DIM}이 아닌 벡터 {len(bad)}건 — 스키마와 맞지 않는다")

    asyncio.run(load(rows, vectors, args.dry_run))
    if skipped:
        sys.exit(1)


if __name__ == "__main__":
    main()
