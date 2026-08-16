"""[2] 괘 도출 및 해석 에이전트 (Interpretation Agent).

- 규칙 엔진(core.hexagram_engine)을 통한 괘 산출 (LLM 개입 없음)
- DB 확정 괘사/효사 조회 (core.reading)
- RAG(core.rag)를 통한 관련 주석/해설 검색
- LLM을 통한 사용자 고민과 괘상 간의 맥락 매핑(contextual_mapping) 초안 생성
"""

from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from core.hexagram_engine import cast_hexagram
from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from core.rag import RetrievedChunk, search_balanced
from core.reading import ReadingEvidence, build_evidence
from schemas.counsel import HexagramInterpretationSchema


async def run_interpret(
    session: AsyncSession,
    clarified_question: str,
    *,
    method: str = "coin",
    manual_lines: Optional[List[int]] = None,
    client: Optional[LLMClient] = None,
    k_benui: int = 2,
) -> Tuple[HexagramInterpretationSchema, ReadingEvidence, List[RetrievedChunk]]:
    """괘를 도출하고 확정 근거 및 RAG 주석을 수집하여 해석 초안을 생성합니다.

    Args:
        session: SQLAlchemy 비동기 세션
        clarified_question: 정리된 사용자 고민 질문
        method: 괘 산출 방식 ("coin" | "yarrow")
        manual_lines: 수동 지정 효 리스트 (테스트용)
        client: 주입할 LLM 클라이언트 (테스트 시 Mock 주입)
        k_benui: 본의에서 가져올 청크 수. 0이면 정전만 쓴다 — 본의가 답변의
            톤을 예언 쪽으로 당기는지 같은 인덱스에서 대조할 때 쓰는 스위치다

    Returns:
        (HexagramInterpretationSchema, ReadingEvidence, list of RetrievedChunk) 튜플
    """
    # 1. 괘 도출 규칙 엔진 (규칙 기반)
    cast_result = cast_hexagram(method=method, manual_lines=manual_lines)

    # 2. DB 1:1 확정 근거 조회 (규칙 기반)
    evidence = await build_evidence(session, cast_result)

    # 3. RAG 주석 및 해설 검색 (pgvector 의미 검색)
    #
    # 정전과 본의를 갈라 뽑는다. 한 풀에 던지면 무엇을 근거로 삼을지가 검색 순위의
    # 우연에 맡겨진다 — 본의는 중앙값 31자로 짧아 밀리거나, 반대로 질의어와 촘촘히
    # 겹쳐 정전을 밀어낸다. 비율은 `core.rag.search_balanced`에 드러나 있다.
    chunks = await search_balanced(
        session,
        clarified_question,
        hexagram_id=cast_result.original_hexagram_id,
        k_jeongjeon=3,
        k_benui=k_benui,
    )
    # 특정 효가 포커스인 경우 해당 효사 주석 추가 검색.
    #
    # 괘 ID는 반드시 `evidence.target_hexagram_id`를 쓴다. 동효가 4~5개면 초점이
    # 가리키는 효는 지괘의 효라서, 본괘 ID로 검색하면 효 번호만 같고 괘가 다른
    # 주석이 딸려온다 — DB 확정 근거와 RAG 근거가 서로 다른 괘를 가리키게 된다.
    if cast_result.focus_rule.target_line_numbers:
        primary_line = cast_result.focus_rule.target_line_numbers[0]
        if primary_line <= 6:
            line_chunks = await search_balanced(
                session,
                clarified_question,
                hexagram_id=evidence.target_hexagram_id,
                line_number=primary_line,
                k_jeongjeon=2,
                k_benui=1 if k_benui else 0,
            )
            chunks.extend(line_chunks)

    # 지괘가 있고 포커스가 지괘인 경우 지괘 주석도 검색
    if cast_result.transformed_hexagram_id and cast_result.focus_rule.target_hexagram_type in ("TRANSFORMED", "BOTH"):
        trans_chunks = await search_balanced(
            session,
            clarified_question,
            hexagram_id=cast_result.transformed_hexagram_id,
            k_jeongjeon=2,
            k_benui=1 if k_benui else 0,
        )
        chunks.extend(trans_chunks)

    # 4. LLM 상황 매핑(contextual_mapping) 초안 생성
    sys_prompt = load_system_prompt("interpret")
    llm = client or get_client(role="interpret")

    prompt_lines = [
        f"[내담자 고민] {clarified_question}\n",
        f"[도출된 괘 확정 근거]\n{evidence.summary_korean}\n",
    ]
    if chunks:
        prompt_lines.append("[관련 주석 및 해설 (참고용)]")
        for c in chunks[:4]:
            prompt_lines.append(f"- {c.source_type}: {c.content_ko}")

    user_msg = "\n".join(prompt_lines)

    try:
        data = llm.complete_json(user_msg, system=sys_prompt, temperature=0.0)
        mapping = data.get("contextual_mapping", "도출된 괘상의 흐름을 바탕으로 상황을 성찰합니다.")
    except Exception:
        mapping = f"제{evidence.original.hexagram_id}괘 {evidence.original.name_full}의 지혜를 바탕으로 마음을 살핍니다."

    schema_out = HexagramInterpretationSchema(
        original_hexagram_id=cast_result.original_hexagram_id,
        transformed_hexagram_id=cast_result.transformed_hexagram_id,
        changing_lines=cast_result.changing_lines,
        raw_text=evidence.summary_korean,
        contextual_mapping=mapping,
    )

    return schema_out, evidence, chunks
