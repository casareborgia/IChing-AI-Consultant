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
    return await _search_with_vector(
        session, vec, hexagram_id=hexagram_id, line_number=line_number,
        source_types=source_types, k=k,
    )


async def _search_with_vector(
    session: AsyncSession,
    vec: List[float],
    *,
    hexagram_id: int,
    line_number: Optional[int] = None,
    source_types: Optional[List[str]] = None,
    k: int = 5,
) -> List[RetrievedChunk]:
    """이미 임베딩된 질의 벡터로 검색한다.

    출처를 갈라 두 번 검색할 때 질의를 두 번 임베딩하지 않으려고 벡터를 밖에서
    받는다. 같은 문장을 두 번 임베딩하는 것은 돈과 지연을 그냥 두 배로 쓰는 일이다.
    """
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


# 두 주석서. 한 풀에 던지지 않고 갈라서 뽑는다.
#
# 이 자료는 『주역전의』, 곧 정전(傳)과 본의(義)를 함께 읽는 체제에서 왔다.
# 그런데 한 번의 의미 검색에 다 던져 상위 k건을 받으면 균형이 검색 순위에
# 맡겨진다 — 본의는 중앙값 31자로 훨씬 짧아 밀리기 쉽고, 반대로 짧은 글이
# 질의어와 촘촘히 겹쳐 정전을 밀어낼 수도 있다. 어느 쪽이든 무엇을 근거로
# 삼을지가 우연에 달리게 된다.
#
# 그래서 출처별로 정해진 수만큼 따로 뽑아 합친다. 비율이 코드에 드러나 있어야
# 나중에 조정하거나 한쪽을 뺄 수 있다.
JEONGJEON_TYPES = [
    "gwa_intro", "guasa_comm", "tanjon_comm", "daesang_comm",
    "line_comm", "sosang_comm", "tanjon", "daesang", "sosang",
]
BENUI_TYPES = [
    "benui_guasa", "benui_line", "benui_tanjon", "benui_daesang", "benui_sosang",
]

# 출처 코드를 사람 말로 옮긴다. `source_type`은 내부 값이라, 모델 프롬프트에 그대로
# 넣으면 'line_comm' 같은 문자열을 근거인 양 읽고 답변에까지 새어 나온다. 화면의
# 근거 패널도 이 라벨을 쓴다 — 사용자에게 보이는 출처 이름과 모델이 보는 출처 이름이
# 갈라지면, 근거를 대조할 방법이 없어진다.
SOURCE_LABELS = {
    "line_comm": "효사 주석",
    "sosang": "소상전",
    "sosang_comm": "소상전 주석",
    "tanjon": "단전",
    "tanjon_comm": "단전 주석",
    "daesang": "대상전",
    "daesang_comm": "대상전 주석",
    "guasa_comm": "괘사 주석",
    "gwa_intro": "괘 서두 해설",
    "benui_guasa": "본의 괘사 주석",
    "benui_line": "본의 효사 주석",
    "benui_tanjon": "본의 단전 주석",
    "benui_daesang": "본의 대상전 주석",
    "benui_sosang": "본의 소상전 주석",
}


def source_label(chunk: RetrievedChunk) -> str:
    """청크의 출처를 사람이 읽는 이름으로. 효 단위면 몇 효인지까지 붙인다."""
    label = SOURCE_LABELS.get(chunk.source_type, "해설")
    if chunk.line_number and chunk.line_number <= 6:
        label = f"{label}({chunk.line_number}효)"
    return label


# 질의 문자열 하나만 받는 검색 함수. 상담 루프가 대화 중 다시 찾을 때 쓴다.
Retriever = Callable[[str], Awaitable[List[RetrievedChunk]]]


async def search_balanced(
    session: AsyncSession,
    query: str,
    *,
    hexagram_id: int,
    line_number: Optional[int] = None,
    k_jeongjeon: int = 3,
    k_benui: int = 2,
    use_cache: bool = False,
) -> List[RetrievedChunk]:
    """정전과 본의를 정해진 몫만큼 따로 뽑아 합친다.

    정전이 앞에 온다. 이 앱은 의사결정 지원을 표방하므로 의리(義理)를 논하는
    정전이 본류고, 점법(占法)을 말하는 본의는 근거를 두껍게 하는 자리다
    (CLAUDE.md 데이터 레이어 절).

    `k_benui=0`이면 본의를 아예 빼고 검색한다. 본의가 답변의 톤을 예언 쪽으로
    당기는지 같은 인덱스에서 대조하려면 이 스위치가 필요하다 — 인덱스를 두 벌
    만들어 비교하면 다른 것까지 같이 달라진다.
    """
    if hexagram_id is None:
        raise ValueError("hexagram_id는 필수 인자입니다. 괘 범위를 지정하지 않으면 타 괘 해설이 섞입니다.")

    vec = embed_query(query, use_cache=use_cache)  # 한 번만 임베딩한다

    out: List[RetrievedChunk] = []
    for types, k in ((JEONGJEON_TYPES, k_jeongjeon), (BENUI_TYPES, k_benui)):
        if k <= 0:
            continue
        out.extend(await _search_with_vector(
            session, vec, hexagram_id=hexagram_id, line_number=line_number,
            source_types=types, k=k,
        ))
    return out


def make_retriever(
    session: AsyncSession,
    *,
    hexagram_id: int,
    k_jeongjeon: int = 3,
    k_benui: int = 2,
    use_cache: bool = False,
) -> Retriever:
    """괘 범위를 미리 묶은 검색 함수를 만듭니다.

    상담 에이전트에게 `search_chunks`를 그대로 쥐여주지 않는 이유는 범위 때문이다.
    괘 ID를 부르는 쪽에서 못 박아 두면 에이전트가 넓힐 방법이 없다 — 질의 문자열만
    정할 수 있다. `hexagram_id`를 키워드 필수 인자로 둔 것과 같은 이유이고,
    거기서 한 걸음 더 간 것이다(주석이 아니라 구조로 막는다).

    대화 중 다시 찾을 때도 정전과 본의를 갈라 뽑는다. 첫 검색만 균형을 잡고
    재검색은 한 풀에서 뽑으면, 대화가 길어질수록 근거가 한쪽으로 쏠린다.

    Args:
        session: SQLAlchemy 비동기 세션
        hexagram_id: 검색을 묶어둘 괘. 초점이 가리키는 괘를 쓴다
        k_jeongjeon: 재검색 1회가 가져올 정전 쪽 최대 청크 수
        k_benui: 같은 자리에서 본의 쪽 최대 청크 수 (0이면 본의를 뺀다)
        use_cache: 임베딩 디스크 캐시 사용 여부
    """

    async def _retrieve(query: str) -> List[RetrievedChunk]:
        return await search_balanced(
            session, query, hexagram_id=hexagram_id,
            k_jeongjeon=k_jeongjeon, k_benui=k_benui, use_cache=use_cache,
        )

    return _retrieve

