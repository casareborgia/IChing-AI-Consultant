"""[3] 상담 에이전트 (Counsel Agent).

- 한문 원문 노출 차단 (순수 한글 번역 및 해설만 전달)
- 단정적 예언 배제 및 성찰형 상담 대화 루프 (1턴 1질문 되묻기)
- 대화 중 필요하면 해설을 다시 찾는다 (Agentic RAG, 한 턴 3회 상한)
- 턴 수 상한(기본 12턴) 도달 시 마무리 강제
"""

from typing import Any, Dict, List, Optional

from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from core.rag import RetrievedChunk, Retriever, source_label
from schemas.counsel import CounselTurnSchema, EvidenceItem, HexagramInterpretationSchema

MAX_TURNS_LIMIT = 12

# 한 턴 안에서 해설을 다시 찾을 수 있는 횟수.
#
# Agentic RAG는 "조금만 더 찾아보자"를 스스로 반복할 수 있다. 상한이 없으면 한 턴이
# 무한정 길어지고 호출도 그만큼 늘어난다.
MAX_RAG_SEARCHES = 3

# 답변에 나오면 안 되는 진단성 표현. 설계 원칙 4이자 SaMD 판정선과 닿는 자리다
# (CLAUDE.md 법적 확인 사항 — "고위험군입니다" 류의 등급·병명 표시는 의료기기 쪽으로
# 넘어가는 신호로 적혀 있다).
#
# 프롬프트에도 같은 목록이 있고, 둘이 어긋나지 않는지는 테스트가 지킨다.
# 문구를 코드에 복사해 두었다가 프롬프트와 갈라진 전례가 이미 있었다.
DIAGNOSIS_TERMS = (
    "우울증", "불안장애", "공황장애", "조울", "강박증", "ADHD", "번아웃증후군",
    "처방", "복용", "투약", "진단",
)

# 재생성까지 실패했을 때 나가는 문장. 병명을 피하면서 상담을 잇는다.
DIAGNOSIS_FALLBACK = (
    "그 이름을 붙이는 일은 전문가의 몫이라 제가 답할 수 있는 자리가 아닙니다.\n\n"
    "다만 말씀하신 상태가 언제부터였는지, 하루 중 언제 가장 힘드신지 들려주시겠어요?"
)


def find_diagnosis_terms(text: str) -> list:
    """답변에 섞인 진단성 표현을 찾는다."""
    return [w for w in DIAGNOSIS_TERMS if w in (text or "")]


# 근거를 물어오는 말들. 이 자리에서는 모델의 판단을 기다리지 않고 코드가 찾는다.
#
# 프롬프트에 "근거를 물으면 반드시 먼저 찾으라"고 조건까지 나열해 적어봤지만
# gemma4:latest는 여섯 턴 중 한 번도 `search_query`를 채우지 않았다. 대신 처음 받은
# 근거 한 줄을 말만 바꿔 되풀이했다. 진단어를 프롬프트로만 막으려다 코드로 옮긴 것과
# 같은 자리다 — 확률에 맡길 수 없는 동작은 코드가 붙든다.
#
# 근거 투명성은 이 앱의 차별점이다(CLAUDE.md 포지셔닝). "왜 이렇게 보느냐"는 물음에
# 찾아보지도 않고 답하는 것은 그 차별점을 스스로 무르는 일이다.
GROUNDS_PATTERNS = (
    "왜 그렇게", "왜 그런", "무슨 근거", "근거가", "근거는", "어떤 근거",
    "어떤 대목", "어디에 나오", "어디 나오", "출처", "무엇을 보고", "어떻게 아시",
)


def asks_for_grounds(text: str) -> bool:
    """근거를 묻는 발화인지 본다. 띄어쓰기 차이는 무시한다."""
    t = (text or "").replace(" ", "")
    return any(p.replace(" ", "") in t for p in GROUNDS_PATTERNS)


def format_retrieved(query: str, chunks: List[RetrievedChunk]) -> str:
    """재검색 결과를 프롬프트에 붙일 한글 블록으로 만든다.

    `content_ko`만 쓴다. 한문(`content`)은 "왜 이 해석인가"를 물었을 때 코드가 꺼내
    보여주려고 보존하는 값이지 모델에게 줄 값이 아니다. 모델 손에 한문이 있으면
    답변에 새어 나오고, 그러면 원칙 1이 프롬프트 문구 하나에 매달린다.
    """
    header = f'[추가로 찾아본 해설 — 질의: "{query}"]'
    lines = [header]

    for c in chunks:
        ko = (c.content_ko or "").strip()
        if not ko:
            continue  # 번역이 비어 있으면 건너뛴다. 한문으로 대신하지 않는다
        lines.append(f"- {source_label(c)}: {ko}")

    if len(lines) == 1:
        lines.append("찾은 해설이 없습니다. 지금 가진 근거 안에서 답하고, 없는 말을 지어내지 마십시오.")

    return "\n".join(lines)


def format_evidences(items: List[EvidenceItem]) -> str:
    """확정 근거를 푼 주석을 상담사 프롬프트에 붙일 블록으로 만든다.

    예전에는 이 주석이 상담사에게 오지 않았다. 해석 에이전트가 검색해 매핑 초안을
    만드는 데만 쓰고 버렸고(파이프라인이 받아놓고 아무 데도 넘기지 않았다), 상담사
    손에 남는 것은 괘사·효사 한 줄과 그 매핑뿐이었다.

    효사는 "왕의 신하로서 간난하고 또 간난하니 몸을 위한 까닭이 아니다"처럼 압축돼
    있어 그 한 줄만으로는 무슨 말인지 풀리지 않는다. 풀 것이 없으면 모델은 아는
    통념으로 물러나고, 통념은 여러 괘가 공유하므로 어느 괘를 뽑아도 같은 답이 나온다.

    한글(`content`)만 나간다. 한문은 애초에 이 경로에 실리지 않는다.
    """
    lines = [
        "[근거 주석 (한글)]",
        "※ 위 확정 근거를 옛 주석이 풀어놓은 것입니다. 초점 효의 주석이 맨 앞입니다.",
        "   답변의 뿌리를 괘 이름의 인상이 아니라 여기에 두십시오.",
    ]
    for e in items:
        content = (e.content or "").strip()
        if content:
            lines.append(f"- {e.source_title}: {content}")
    return "\n".join(lines) + "\n"


async def run_counsel_turn(
    user_message: str,
    interpretation: Optional[HexagramInterpretationSchema],
    *,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    turn_number: int = 1,
    client: Optional[LLMClient] = None,
    caution_append: bool = False,
    retrieve: Optional[Retriever] = None,
) -> CounselTurnSchema:
    """내담자와 상담 대화 1턴을 수행하고 응답 및 후속 질문 여부를 반환합니다.

    Args:
        user_message: 이번 턴의 사용자 발화
        interpretation: [2] 해석 에이전트의 산출물
        conversation_history: 이전 대화 이력 (list of {"role": "user"|"counselor", "message": "..."})
        turn_number: 현재 세션의 턴 번호 (1부터 시작)
        client: 주입할 LLM 클라이언트
        caution_append: CAUTION 문구를 말미에 덧붙여야 하는지 여부
        retrieve: 대화 중 해설을 다시 찾을 검색 함수 (`core.rag.make_retriever`).
            None이면 재검색 없이 진행한다 — 괘가 없는 턴에는 좁힐 괘가 없으므로 None이다

    Returns:
        CounselTurnSchema 객체
    """
    sys_prompt = load_system_prompt("counsel")
    llm = client or get_client(role="counsel")

    # 프롬프트 조립.
    #
    # 괘가 없는 턴이 있다. 주역 자체를 묻는 질문("대흉이 무슨 뜻인가요")에는 괘를
    # 뽑지 않는다. 예전에는 이 경우에도 괘를 뽑아서 "지금 보신 괘는…"이라고 답했는데,
    # 묻는 사람은 괘를 뽑은 적이 없으므로 없는 일을 사실처럼 말한 셈이었다.
    if interpretation is None:
        prompt_lines = [
            "[이번 턴에는 도출된 괘가 없습니다]\n"
            "주역 자체에 대한 물음입니다. 아는 대로 답하되, **괘를 뽑은 것처럼 말하지 마십시오.**\n"
            "'지금 보신 괘', '이번에 나온 괘' 같은 표현은 사실이 아닙니다.\n"
            "답을 마친 뒤, 물어볼 고민이 있다면 그때 괘를 헤아려 드리겠다고 알리십시오.\n",
        ]
    else:
        prompt_lines = [
            f"[도출된 괘 및 해설 요약(한글)]\n{interpretation.raw_text}\n",
        ]
        if interpretation.evidences:
            prompt_lines.append(format_evidences(interpretation.evidences))

        # 매핑이 비어 있으면 그 절을 아예 내지 않는다.
        #
        # 예전에는 후속 턴에서 이 자리에 **사용자의 질문 원문**이 들어갔다. 상담사는
        # "상황 매핑 초안"이라는 이름표가 붙은 자기 내담자의 사연을 괘의 해석인 줄
        # 알고 읽었고, 그것을 말만 바꿔 되돌려줬다. 사연에 괘를 맞추는 것처럼 보이던
        # 증상의 큰 몫이 여기였다.
        #
        # 빈 절을 머리만 남겨 내보내도 같은 일이 벌어진다 — 모델은 빈 자리를 바로
        # 위 대화에서 메운다. 없으면 없는 채로 두고, 확정 근거로만 말하게 한다.
        if (interpretation.contextual_mapping or "").strip():
            prompt_lines.append(
                f"[상황 매핑 초안]\n{interpretation.contextual_mapping}\n"
            )

    if conversation_history:
        prompt_lines.append("[지금까지의 대화 흐름]")
        for h in conversation_history:
            role_label = "내담자" if h.get("role") == "user" else "상담사"
            prompt_lines.append(f"{role_label}: {h.get('message', '')}")

    prompt_lines.append(f"\n[내담자의 이번 발화 (턴 {turn_number}/{MAX_TURNS_LIMIT})]\n{user_message}")

    if turn_number >= MAX_TURNS_LIMIT:
        prompt_lines.append("\n※ 이번 턴이 세션의 마지막 턴(상한 도달)입니다. 대화를 따뜻하게 마무리 짓고 is_final: true로 응답하십시오.")

    user_prompt = "\n".join(prompt_lines)

    # 대화 중 재검색 (Agentic RAG). 설계 원칙 3.
    #
    # 첫 검색은 해석 에이전트가 괘를 뽑을 때 한 번 돈다. 그 결과는 정리된 첫 질문으로
    # 찾은 것이고, 대화는 거기서 멀리 간다 — "왜 그렇게 보시나요", "사람 문제가 아니라
    # 시기 문제라면요" 같은 물음의 답은 첫 검색 결과 안에 없다. 그때 모델이
    # `search_query`를 채우면 여기서 다시 찾아 프롬프트에 붙이고 한 번 더 부른다.
    #
    # 모델이 정하는 것은 질의 문자열뿐이다. 어느 괘에서 찾을지는 부르는 쪽이 묶어
    # 넘긴다 — 괘 범위까지 맡기면 64괘 전체에서 끌어와 지금 뽑은 괘와 무관한 해설이
    # 답변에 섞인다.
    searched = 0
    notes: List[str] = []
    # 프롬프트에 실제로 붙은 청크만 모은다. 화면의 근거 패널이 이 목록을 받는다 —
    # 찾기만 하고 안 쓴 것을 근거라고 보여주면 그 패널이 거짓말을 하게 된다.
    used_chunks: List[RetrievedChunk] = []
    data: Optional[Dict[str, Any]] = None
    final_prompt = user_prompt

    # 근거를 물어온 턴은 묻기 전에 찾는다. 모델이 요청하기를 기다리지 않는다.
    #
    # 질의로는 사용자의 물음 자체가 아니라 **직전에 상담사가 한 말**을 쓴다.
    # "왜 그렇게 보시나요"는 의미 검색에 넣을 것이 없는 문장이다. 근거를 대야 할
    # 대상은 그 앞에서 상담사가 한 말이므로, 그 말로 찾아야 관련 주석이 걸린다.
    if retrieve is not None and asks_for_grounds(user_message):
        지난_상담사_발화 = next(
            (h.get("message", "") for h in reversed(conversation_history or [])
             if h.get("role") != "user" and (h.get("message") or "").strip()),
            "",
        )
        seed_query = 지난_상담사_발화 or (
            interpretation.contextual_mapping if interpretation else ""
        ) or user_message
        chunks = await retrieve(seed_query)
        searched += 1
        notes.append(format_retrieved(seed_query, chunks))
        used_chunks.extend(c for c in chunks if (c.content_ko or "").strip())

    while True:
        final_prompt = user_prompt + ("\n\n" + "\n\n".join(notes) if notes else "")
        try:
            data = llm.complete_json(final_prompt, system=sys_prompt, temperature=0.3)
        except Exception:
            data = None
            break

        if not isinstance(data, dict):
            data = None
            break

        query = str(data.get("search_query") or "").strip()
        if not query or retrieve is None or searched >= MAX_RAG_SEARCHES:
            break

        chunks = await retrieve(query)
        searched += 1
        notes.append(format_retrieved(query, chunks))
        used_chunks.extend(c for c in chunks if (c.content_ko or "").strip())

        # 없는 것은 다시 찾아도 없다. 같은 괘 안에서 빈 결과가 나오면 질의를 바꿔도
        # 나아질 여지가 크지 않으므로 검색 예산을 여기서 닫는다.
        #
        # 다만 루프를 끊지는 않는다. 끊으면 마지막으로 받은 응답이 "검색해 주세요"인
        # 채로 남아 답변이 비고, 사용자는 아무 말도 못 듣는다. 한 번 더 불러
        # **못 찾았다는 사실을 알고** 가진 근거로 답하게 한다.
        if not chunks:
            searched = MAX_RAG_SEARCHES

    if data is None:
        msg = "남겨주신 마음을 천천히 되짚어보게 됩니다. 지금 이 순간 가장 마음에 걸리는 점은 무엇인가요?"
        needs_f = True
        f_q = "지금 이 순간 가장 마음에 걸리는 점은 무엇인가요?"
        is_fin = False
    else:
        msg = data.get("message", "말씀해 주신 상황을 괘의 흐름과 함께 깊이 새겨봅니다.")
        needs_f = bool(data.get("needs_followup", True))
        f_q = data.get("followup_question")
        is_fin = bool(data.get("is_final", False))

        # 검색을 요청하는 차례에는 답변을 비워도 된다고 프롬프트가 허락한다. 그래서
        # 상한에 닿아 더 못 찾게 된 마지막 응답이 빈 답변일 수 있다. 빈 화면을 내보내는
        # 대신 대화를 잇는 문장으로 바꾼다.
        if not str(msg or "").strip():
            msg = "말씀해 주신 상황을 괘의 흐름과 함께 다시 짚어봅니다."

    # 진단성 표현이 섞이면 한 번 다시 쓰게 한다.
    #
    # 프롬프트에 금지 목록과 예시까지 넣었는데도 다섯 번에 한 번은 샜다. 확률적으로
    # 새게 둘 수 있는 자리가 아니다 — 병명을 되받는 순간 상담이 아니라 감별이 되고,
    # 그건 SaMD 판정선 쪽으로 걸어가는 일이다.
    #
    # 재생성은 한 번뿐이다. 실패가 이어지면 호출만 늘고 답은 안 나아진다.
    hits = find_diagnosis_terms(msg)
    if hits:
        try:
            retry_prompt = (
                final_prompt  # 재검색으로 얻은 해설까지 그대로 들고 다시 쓴다
                + f"\n\n※ 직전에 쓴 답변에 {', '.join(hits)} 라는 말이 들어 있었습니다."
                " 그 단어를 한 번도 쓰지 말고 다시 쓰십시오. 부정문으로도 쓰지 마십시오."
                " '그 이름', '말씀하신 그것'처럼 가리키기만 하고 넘어가십시오."
            )
            data = llm.complete_json(retry_prompt, system=sys_prompt, temperature=0.3)
            retried = data.get("message", "")
            if retried and not find_diagnosis_terms(retried):
                msg = retried
                f_q = data.get("followup_question", f_q)
            else:
                msg = DIAGNOSIS_FALLBACK
                f_q = None
        except Exception:
            msg = DIAGNOSIS_FALLBACK
            f_q = None

    # 턴 상한 강제. 이 판단은 try 밖에 있어야 한다 — 안에 두면 호출이 실패했을 때
    # 상한이 적용되지 않아, LLM이 계속 죽는 동안 세션이 13턴, 14턴으로 끝없이 간다.
    if turn_number >= MAX_TURNS_LIMIT:
        needs_f = False
        is_fin = True
        f_q = None

    # 되묻기는 사용자에게 보이는 문장 안에 있어야 한다.
    #
    # `followup_question`은 이 함수 밖 어디에서도 쓰이지 않는다 — 파이프라인은
    # `message`만 화면으로 내보낸다. 그래서 모델이 질문을 별도 필드에만 담으면
    # 되묻기가 통째로 사라진다. 실제로 그렇게 되어 있었고, 실제 대화 세 턴에
    # 물음표가 하나도 없었다. "되묻고 깊어지는 대화"가 제품의 정의인데 화면에
    # 질문이 없었던 것이다.
    #
    # 자연스러운 문장은 프롬프트가 만들고, 여기서는 최소선만 지킨다.
    #
    # 조건이 둘인 이유가 있다. 실제 대화 36턴을 보니 물음표 없이 되묻는 경우가
    # 있었다 — "어떤 모습인지 궁금합니다", "한번 돌아보면 좋을 것 같아요". 물음표만
    # 보고 붙이면 이런 답변에 같은 질문이 두 번 나간다. 반대로 정확히 일치하는지만
    # 보면, 프롬프트를 안 따른 답변에서 되묻기가 통째로 사라진다. 둘 다 없을 때만
    # 붙인다 — 질문이 아예 없는 게 확실한 자리다.
    if needs_f and not is_fin and f_q and f_q.strip():
        if f_q.strip() not in msg and "?" not in msg:
            msg = msg.rstrip() + "\n\n" + f_q.strip()

    if caution_append:
        from agents.safety import caution_append_message

        append_text = caution_append_message()
        if append_text.strip() not in msg:
            msg += append_text

    return CounselTurnSchema(
        message=msg,
        needs_followup=needs_f,
        followup_question=f_q,
        is_final=is_fin,
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
