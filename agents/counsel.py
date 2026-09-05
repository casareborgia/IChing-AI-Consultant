"""[3] 상담 에이전트 (Counsel Agent).

- 한문 원문 노출 차단 (순수 한글 번역 및 해설만 전달)
- 단정적 예언 배제 및 성찰형 상담 대화 루프 (1턴 1질문 되묻기)
- 대화 중 필요하면 해설을 다시 찾는다 (Agentic RAG, 한 턴 3회 상한)
- 턴 수 상한(기본 12턴) 도달 시 마무리 강제
"""

from typing import Any, Dict, List, Optional

from agents.divination_chat_engine import DivinationChatEngine, adapt_to_report_payload
from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from core.rag import RetrievedChunk, Retriever, source_label
from schemas.counsel import CounselTurnSchema, EvidenceItem, HexagramInterpretationSchema

MAX_TURNS_LIMIT = 5

# 한 턴 안에서 해설을 다시 찾을 수 있는 횟수.
MAX_RAG_SEARCHES = 3

# 답변에 나오면 안 되는 진단성 표현. 설계 원칙 4이자 SaMD 판정선과 닿는 자리다.
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
GROUNDS_PATTERNS = (
    "왜 그렇게", "왜 그런", "무슨 근거", "근거가", "근거는", "어떤 근거",
    "어떤 대목", "어디에 나오", "어디 나오", "출처", "무엇을 보고", "어떻게 아시",
)


def asks_for_grounds(text: str) -> bool:
    """근거를 묻는 발화인지 본다. 띄어쓰기 차이는 무시한다."""
    t = (text or "").replace(" ", "")
    return any(p.replace(" ", "") in t for p in GROUNDS_PATTERNS)


def format_retrieved(query: str, chunks: List[RetrievedChunk]) -> str:
    """재검색 결과를 프롬프트에 붙일 한글 블록으로 만든다."""
    header = f'[추가로 찾아본 해설 — 질의: "{query}"]'
    lines = [header]

    for c in chunks:
        ko = (c.content_ko or "").strip()
        if not ko:
            continue
        lines.append(f"- {source_label(c)}: {ko}")

    if len(lines) == 1:
        lines.append("찾은 해설이 없습니다. 지금 가진 근거 안에서 답하고, 없는 말을 지어내지 마십시오.")

    return "\n".join(lines)


def format_evidences(items: List[EvidenceItem]) -> str:
    """확정 근거를 푼 주석을 상담사 프롬프트에 붙일 블록으로 만든다."""
    lines = [
        "[근거 주석 (한글)]",
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
    report_data: Optional[Dict[str, Any]] = None,
    enable_refinement_loop: bool = False,
) -> CounselTurnSchema:
    """내담자와 상담 대화 1턴을 수행하고 응답 및 후속 질문 여부를 반환합니다. (5턴 소크라테스식 코칭 모델)"""
    sys_prompt = load_system_prompt("counsel")
    llm = client or get_client(role="counsel")
    chat_engine = DivinationChatEngine()
    history = conversation_history or []

    prompt_lines: List[str] = []
    report_payload: Dict[str, Any] = {}

    if interpretation is None:
        prompt_lines.append(
            "[이번 턴에는 도출된 괘가 없습니다]\n"
            "주역 자체에 대한 물음입니다. 아는 대로 답하되, **괘를 뽑은 것처럼 말하지 마십시오.**\n"
            "'지금 보신 괘', '이번에 나온 괘' 같은 표현은 사실이 아닙니다.\n"
            "답을 마친 뒤, 물어볼 고민이 있다면 그때 괘를 헤아려 드리겠다고 알리십시오.\n"
        )
    else:
        report_payload = adapt_to_report_payload(
            report_data=report_data,
            interpretation_raw_text=interpretation.raw_text,
            contextual_mapping=interpretation.contextual_mapping or "",
        )
        prompt_lines.append(f"[도출된 괘 및 해설 요약(한글)]\n{interpretation.raw_text}\n")
        if report_data:
            sec2_text = report_data.get('section2_action', {}).get('interpretation', '')
            final_sum = report_data.get('final_summary', '')
            prompt_lines.append(f"[앞서 제시한 1:1 맞춤 리포트 핵심 결론]\n• 행동 지침: {sec2_text}\n• 최종 종합 요약: {final_sum}\n")
        if interpretation.evidences:
            prompt_lines.append(format_evidences(interpretation.evidences))

        if (interpretation.contextual_mapping or "").strip():
            prompt_lines.append(
                f"[상황 매핑 초안]\n{interpretation.contextual_mapping}\n"
            )

        # 5단계 소크라테스 코칭 프레임워크 지침 주입
        turn_goal_desc = chat_engine._get_turn_goal_description(turn_number)
        prompt_lines.append(
            f"[5단계 소크라테스 코칭 모델 - 턴 {turn_number}/{MAX_TURNS_LIMIT} 가이드]\n"
            f"• 이번 턴 목표: {turn_goal_desc}\n"
            "• 핵심 원칙: 성리학적 자성(自省)과 경(敬) 철학에 기반하여, 내담자 스스로 아집을 발견하고 성찰하도록 돕는 정제된 3~4문장의 한국어로 응답하십시오.\n"
            "• 반드시 응답 끝에 딱 하나의 깊은 성찰형 열린 질문(Single Socratic Question)으로 마무리하십시오."
        )

    if history:
        prompt_lines.append("[지금까지의 대화 흐름]")
        effective_history = history[-6:] if len(history) > 6 else history
        if len(history) > 6:
            prompt_lines.append("... (이전 대화 생략됨 — 초기 고민 매핑 참조) ...")
        for h in effective_history:
            role_label = "내담자" if h.get("role") == "user" else "상담사"
            prompt_lines.append(f"{role_label}: {h.get('message', '')}")

    prompt_lines.append(f"\n[내담자의 이번 발화 (턴 {turn_number}/{MAX_TURNS_LIMIT})]\n{user_message}")

    if turn_number >= MAX_TURNS_LIMIT:
        prompt_lines.append(
            f"\n※ 이번 턴이 세션의 마지막 턴(턴 {MAX_TURNS_LIMIT} 도달)입니다. "
            "대화를 따뜻하게 매듭짓고, 오늘 당장 실천할 단 1가지 행동 다짐(Action Pledge)을 확인하며 is_final: true, needs_followup: false로 응답하십시오."
        )

    user_prompt = "\n".join(prompt_lines)

    # 대화 중 재검색 (Agentic RAG)
    searched = 0
    notes: List[str] = []
    used_chunks: List[RetrievedChunk] = []
    data: Optional[Dict[str, Any]] = None
    final_prompt = user_prompt

    if retrieve is not None and asks_for_grounds(user_message):
        지난_상담사_발화 = next(
            (h.get("message", "") for h in reversed(history)
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
            data = llm.complete_json(final_prompt, system=sys_prompt, temperature=0.3, max_tokens=2048)
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

        if not str(msg or "").strip():
            msg = "말씀해 주신 상황을 괘의 흐름과 함께 다시 짚어봅니다."

    # 턴 상한 강제
    if turn_number >= MAX_TURNS_LIMIT:
        needs_f = False
        is_fin = True
        f_q = None

    # 진단성 표현 방어 (SaMD 가드레일)
    hits = find_diagnosis_terms(msg)
    if hits:
        try:
            retry_prompt = (
                final_prompt
                + f"\n\n※ 직전에 쓴 답변에 {', '.join(hits)} 라는 말이 들어 있었습니다."
                " 그 단어를 한 번도 쓰지 말고 다시 쓰십시오. 부정문으로도 쓰지 마십시오."
                " '그 이름', '말씀하신 그것'처럼 가리키기만 하고 넘어가십시오."
            )
            data = llm.complete_json(retry_prompt, system=sys_prompt, temperature=0.3, max_tokens=2048)
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

    # 자아비판 및 정밀화 루프 (Critique & Refinement Loop)
    if interpretation is not None and enable_refinement_loop and not hits and msg and not is_fin:
        try:
            critique_prompt = chat_engine.generate_critique_prompt(
                msg, history, report_payload, turn_num_override=turn_number
            )
            if hasattr(llm, "complete"):
                critique_res = llm.complete(critique_prompt, system="You are a senior dialog auditor.")
            else:
                critique_res = str(llm.complete_json(critique_prompt, system="You are a senior dialog auditor."))

            if critique_res and str(critique_res).strip():
                refine_prompt = chat_engine.generate_refinement_prompt(
                    msg, str(critique_res), history, report_payload, turn_num_override=turn_number
                )
                if hasattr(llm, "complete"):
                    refined_res = llm.complete(refine_prompt, system="You are the master scribe of the I-Ching counseling team.")
                else:
                    refined_res = str(llm.complete_json(refine_prompt, system="You are the master scribe of the I-Ching counseling team."))

                if refined_res and isinstance(refined_res, str) and len(refined_res.strip()) > 10:
                    refined_clean = refined_res.strip().strip('"').strip("'")
                    if refined_clean.startswith("{") and "message" in refined_clean:
                        try:
                            parsed_refine = json.loads(refined_clean)
                            if parsed_refine.get("message"):
                                refined_clean = parsed_refine["message"]
                        except Exception:
                            pass
                    if not find_diagnosis_terms(refined_clean):
                        msg = refined_clean
        except Exception:
            pass

    # 되묻기 질문 무결성 검증
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
