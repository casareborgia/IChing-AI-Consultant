"""RAG 의미 검색 모듈.

- 괘 ID(hexagram_id) 범위 강제 (타 괘 오염 원천 차단)
- 상담 루프의 대화 중 재검색용 바인딩 (make_retriever)
- Vertex AI text-multilingual-embedding-002 (task_type=RETRIEVAL_QUERY)
- pgvector 코사인 거리 검색 및 유사도 계산
- 로컬 개발/튜닝을 위한 디스크 캐시 옵션 지원
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.rag import InterpretationChunk

EMBED_MODEL = "text-multilingual-embedding-002"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / ".cache"


@dataclass
class RetrievedChunk:
    """검색된 RAG 청크 데이터 클래스."""

    chunk_id: str
    hexagram_id: int
    line_number: Optional[int]
    source_type: str
    category: str
    content: str        # 한문 원문 (근거 보존용)
    content_ko: str     # 한글 번역 (상담 프롬프트 주입용)
    similarity: float   # 코사인 유사도 (1.0 - dist)


def _get_cache_path(text: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"embed_{h}.json"


def embed_query(text: str, *, use_cache: bool = False) -> List[float]:
    """질의 텍스트를 RETRIEVAL_QUERY 태스크 타입으로 임베딩합니다."""
    cache_path = _get_cache_path(text) if use_cache else None
    if cache_path and cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    from google import genai
    from google.genai import types

    project = settings.GOOGLE_CLOUD_PROJECT or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = settings.GEMINI_LOCATION or os.getenv("GEMINI_LOCATION", "us-central1")

    client = genai.Client(vertexai=True, project=project, location=location)
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=[text],
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    vec = resp.embeddings[0].values

    if cache_path:
        cache_path.write_text(json.dumps(vec), encoding="utf-8")

    return vec


async def search_chunks(
    session: AsyncSession,
    query: str,
    *,
    hexagram_id: int,
    line_number: Optional[int] = None,
    source_types: Optional[List[str]] = None,
    k: int = 5,
    use_cache: bool = False,
) -> List[RetrievedChunk]:
    """지정된 괘(hexagram_id) 범위 내에서 RAG 청크를 의미 검색합니다.

    Args:
        session: SQLAlchemy AsyncSession
        query: 검색 질의 문자열
        hexagram_id: 대상 괘 ID (필수 키워드 인자)
        line_number: 특정 효(1~6)로 좁힐 경우 지정
        source_types: 허용 출처 타입 목록 (예: ['line_comm', 'sosang_comm'])
        k: 반환할 청크 최대 개수
        use_cache: 임베딩 디스크 캐시 사용 여부

    Returns:
        유사도 내림차순으로 정렬된 RetrievedChunk 목록
    """
    if hexagram_id is None:
        raise ValueError("hexagram_id는 필수 인자입니다. 괘 범위를 지정하지 않으면 타 괘 해설이 섞입니다.")

    vec = embed_query(query, use_cache=use_cache)

    stmt = select(
        InterpretationChunk,
        InterpretationChunk.embedding.cosine_distance(vec).label("dist"),
    ).where(InterpretationChunk.hexagram_id == hexagram_id)

    if line_number is not None:
        stmt = stmt.where(InterpretationChunk.line_number == line_number)

    if source_types:
        stmt = stmt.where(InterpretationChunk.source_type.in_(source_types))

    stmt = stmt.order_by("dist").limit(k)
    results = (await session.execute(stmt)).all()

    retrieved: List[RetrievedChunk] = []
    for chunk, dist in results:
        sim = float(1.0 - dist) if dist is not None else 0.0
        retrieved.append(
            RetrievedChunk(
                chunk_id=str(chunk.id),
                hexagram_id=chunk.hexagram_id,
                line_number=chunk.line_number,
                source_type=chunk.source_type or "",
                category=chunk.category,
                content=chunk.content,
                content_ko=chunk.content_ko or "",
                similarity=sim,
            )
        )

    return retrieved


# 질의 문자열 하나만 받는 검색 함수. 상담 루프가 대화 중 다시 찾을 때 쓴다.
Retriever = Callable[[str], Awaitable[List[RetrievedChunk]]]


def make_retriever(
    session: AsyncSession,
    *,
    hexagram_id: int,
    k: int = 3,
    use_cache: bool = False,
) -> Retriever:
    """괘 범위를 미리 묶은 검색 함수를 만듭니다.

    상담 에이전트에게 `search_chunks`를 그대로 쥐여주지 않는 이유는 범위 때문이다.
    괘 ID를 부르는 쪽에서 못 박아 두면 에이전트가 넓힐 방법이 없다 — 질의 문자열만
    정할 수 있다. `hexagram_id`를 키워드 필수 인자로 둔 것과 같은 이유이고,
    거기서 한 걸음 더 간 것이다(주석이 아니라 구조로 막는다).

    Args:
        session: SQLAlchemy 비동기 세션
        hexagram_id: 검색을 묶어둘 괘. 초점이 가리키는 괘를 쓴다
        k: 한 번의 재검색이 가져올 최대 청크 수
        use_cache: 임베딩 디스크 캐시 사용 여부
    """

    async def _retrieve(query: str) -> List[RetrievedChunk]:
        return await search_chunks(
            session, query, hexagram_id=hexagram_id, k=k, use_cache=use_cache
        )

    return _retrieve

