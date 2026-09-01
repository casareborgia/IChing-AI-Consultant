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
from core.rag import RetrievedChunk, search_balanced, source_label
from core.reading import ReadingEvidence, build_evidence
from schemas.counsel import EvidenceItem, HexagramInterpretationSchema
from schemas.hexagram_engine import BodyUseType


# 프롬프트에 실을 주석의 출처별 몫.
#
# 예전에는 세 검색 결과를 한 목록으로 합쳐 `chunks[:4]`로 잘랐다. 붙는 순서가
# 괘 단위 → 초점 효 → 지괘라서, 괘 단위가 4건 이상이면 **초점 효의 주석이 한 건도
# 남지 않는다.** 실제로 그랬다 — 8건을 찾아 4건을 넘겼고 그 4건이 전부 괘 단위였다.
#
# 이것이 "괘가 달라도 답이 비슷하다"의 원인이다. 효사는 "왕의 신하로서 간난하고 또
# 간난하니 몸을 위한 까닭이 아니다"처럼 압축돼 있어 주석 없이는 풀리지 않는다.
# 풀 것이 손에 없으면 모델은 괘 이름의 통념(건蹇=막힘, 둔遯=물러남)으로 물러나고,
# 통념은 여러 괘가 공유하므로 어느 괘를 뽑아도 같은 말이 나온다.
#
# 그래서 자르지 않고 몫을 나눈다. 초점 효 주석이 가장 앞이다 — 초점 규칙이 주
# 근거로 지목한 자리이기 때문이다.
PROMPT_QUOTA_FOCUS_LINE = 3    # 초점 효 주석. 검색이 가져오는 전량이다
PROMPT_QUOTA_HEXAGRAM = 3      # 괘 단위 주석
PROMPT_QUOTA_TRANSFORMED = 2   # 지괘 주석


def _annotation_block(
    focus_line_chunks: List[RetrievedChunk],
    hexagram_chunks: List[RetrievedChunk],
    transformed_chunks: List[RetrievedChunk],
) -> Tuple[List[str], List[RetrievedChunk]]:
    """주석 블록 문자열과, 거기에 실제로 들어간 청크 목록을 함께 돌려준다.

    들어간 것을 함께 돌려주는 이유는 화면의 근거 패널 때문이다. 프롬프트에 못 들어간
    청크는 답변에 영향을 준 적이 없으므로 근거로 보여주면 거짓이 된다.
    """
    묶음 = (
        ("■ 초점 효의 주석 — 주 해석 근거입니다. 여기부터 보십시오",
         focus_line_chunks[:PROMPT_QUOTA_FOCUS_LINE]),
        ("■ 괘 전체의 주석 — 배경입니다", hexagram_chunks[:PROMPT_QUOTA_HEXAGRAM]),
        ("■ 지괘의 주석 — 옮겨 갈 국면입니다", transformed_chunks[:PROMPT_QUOTA_TRANSFORMED]),
    )

    lines: List[str] = []
    used: List[RetrievedChunk] = []
    for 머리, 몫 in 묶음:
        실린 = [c for c in 몫 if (c.content_ko or "").strip()]
        if not 실린:
            continue
        lines.append(머리)
        for c in 실린:
            lines.append(f"- {source_label(c)}: {c.content_ko.strip()}")
            used.append(c)

    return lines, used


# 매핑 앞에 붙는 칸들. 표시 이름은 상담사 프롬프트에 그대로 나간다.
BRIDGE_FIELDS = (
    ("focus_image", "효사의 형상"),
    ("image_position", "그 장면에서의 자리"),
    ("only_this_line", "이 효만의 것"),
)


def _render_mapping(data: dict, mapping: str) -> str:
    """구조화된 칸들과 매핑 문장을 한 덩어리로 렌더한다.

    **왜 따로 들고 다니지 않고 합치는가.** 이 값은 `counsel_turns.contextual_mapping`에
    저장되어 후속 턴에서 되살아난다. 칸들을 스키마에만 두면 세션의 둘째 턴부터 사라지고,
    그러면 매핑을 저장하지 않아 사연이 그 자리를 메우던 것과 똑같은 일이 벌어진다.
    한 덩어리로 렌더해 두면 기존 칼럼을 그대로 타고 간다.

    빈 칸은 싣지 않는다. 머리만 남은 칸은 모델이 채워 넣을 빈자리가 된다.
    """
    lines = []
    for key, 이름 in BRIDGE_FIELDS:
        값 = str(data.get(key) or "").strip()
        if 값:
            lines.append(f"{이름}: {값}")
    if mapping:
        lines.append(f"— {mapping}" if lines else mapping)
    return "\n".join(lines)


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
    hexagram_chunks = await search_balanced(
        session,
        clarified_question,
        hexagram_id=cast_result.original_hexagram_id,
        k_jeongjeon=3,
        k_benui=k_benui,
    )
    focus_line_chunks: List[RetrievedChunk] = []
    transformed_chunks: List[RetrievedChunk] = []
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
            focus_line_chunks.extend(line_chunks)

    # 지괘가 있고 포커스가 지괘이거나 체용 규칙상 지괘(用) 강조인 경우 지괘 주석도 검색
    should_search_trans = (
        cast_result.transformed_hexagram_id is not None
        and (
            cast_result.focus_rule.target_hexagram_type in ("TRANSFORMED", "BOTH")
            or cast_result.focus_rule.body_use_type == BodyUseType.EMPHASIZE_TRANSFORMED
        )
    )
    if should_search_trans and cast_result.transformed_hexagram_id:
        trans_chunks = await search_balanced(
            session,
            clarified_question,
            hexagram_id=cast_result.transformed_hexagram_id,
            k_jeongjeon=2,
            k_benui=1 if k_benui else 0,
        )
        transformed_chunks.extend(trans_chunks)

    # 4. LLM 상황 매핑(contextual_mapping) 초안 생성
    sys_prompt = load_system_prompt("interpret")
    llm = client or get_client(role="interpret")

    prompt_lines = [
        f"[내담자 고민] {clarified_question}\n",
        f"[도출된 괘 확정 근거]\n{evidence.summary_korean}\n",
    ]
    block_lines, used_chunks = _annotation_block(
        focus_line_chunks, hexagram_chunks, transformed_chunks
    )
    if block_lines:
        prompt_lines.append("[관련 주석 및 해설 (참고용)]")
        prompt_lines.extend(block_lines)

    user_msg = "\n".join(prompt_lines)

    data: dict = {}
    try:
        data = llm.complete_json(user_msg, system=sys_prompt, temperature=0.0, max_tokens=1536)
        mapping = data.get("contextual_mapping", "도출된 괘상의 흐름을 바탕으로 상황을 성찰합니다.")
    except Exception:
        mapping = f"제{evidence.original.hexagram_id}괘 {evidence.original.name_full}의 지혜를 바탕으로 마음을 살핍니다."

    # 칸을 안 채우는 모델도 있다. 그때는 예전처럼 매핑 문장만 나간다 — 없는 칸을
    # 만들어 넣지 않는다.
    bridge = {k: str(data.get(k) or "").strip() for k, _ in BRIDGE_FIELDS}

    schema_out = HexagramInterpretationSchema(
        original_hexagram_id=cast_result.original_hexagram_id,
        transformed_hexagram_id=cast_result.transformed_hexagram_id,
        changing_lines=cast_result.changing_lines,
        lines_val=[l.value for l in cast_result.lines],
        raw_text=evidence.summary_korean,
        focus_image=bridge["focus_image"],
        image_position=bridge["image_position"],
        only_this_line=bridge["only_this_line"],
        contextual_mapping=_render_mapping(data, mapping),
        evidences=[
            EvidenceItem(
                source_type=c.source_type,
                source_title=source_label(c),
                content=(c.content_ko or "").strip(),
                hexagram_id=c.hexagram_id,
                line_number=c.line_number,
            )
            for c in used_chunks
        ],
    )

    # 반환하는 목록은 검색이 가져온 전량이다. 프롬프트에 실린 몫만 보고 싶으면
    # `schema_out.evidences`를 쓴다 — 두 값이 다른 것을 재는 하네스가 있다
    # (`scripts/compare_benui_tone.py`는 인덱스에 무엇이 걸리는지를 본다).
    chunks = hexagram_chunks + focus_line_chunks + transformed_chunks

    return schema_out, evidence, chunks
