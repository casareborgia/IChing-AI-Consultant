"""[3] 상담 에이전트 (Counsel Agent).

- 한문 원문 노출 차단 (순수 한글 번역 및 해설만 전달)
- 단정적 예언 배제 및 성찰형 상담 대화 루프 (1턴 1질문 되묻기)
- 턴 수 상한(기본 12턴) 도달 시 마무리 강제
"""

from typing import Any, Dict, List, Optional

from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from schemas.counsel import CounselTurnSchema, HexagramInterpretationSchema

MAX_TURNS_LIMIT = 12


async def run_counsel_turn(
    user_message: str,
    interpretation: HexagramInterpretationSchema,
    *,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    turn_number: int = 1,
    client: Optional[LLMClient] = None,
    caution_append: bool = False,
) -> CounselTurnSchema:
    """내담자와 상담 대화 1턴을 수행하고 응답 및 후속 질문 여부를 반환합니다.

    Args:
        user_message: 이번 턴의 사용자 발화
        interpretation: [2] 해석 에이전트의 산출물
        conversation_history: 이전 대화 이력 (list of {"role": "user"|"counselor", "message": "..."})
        turn_number: 현재 세션의 턴 번호 (1부터 시작)
        client: 주입할 LLM 클라이언트
        caution_append: CAUTION 문구를 말미에 덧붙여야 하는지 여부

    Returns:
        CounselTurnSchema 객체
    """
    sys_prompt = load_system_prompt("counsel")
    llm = client or get_client(role="counsel")

    # 프롬프트 조립
    prompt_lines = [
        f"[도출된 괘 및 해설 요약(한글)]\n{interpretation.raw_text}\n",
        f"[상황 매핑 초안]\n{interpretation.contextual_mapping}\n",
    ]

    if conversation_history:
        prompt_lines.append("[지금까지의 대화 흐름]")
        for h in conversation_history:
            role_label = "내담자" if h.get("role") == "user" else "상담사"
            prompt_lines.append(f"{role_label}: {h.get('message', '')}")

    prompt_lines.append(f"\n[내담자의 이번 발화 (턴 {turn_number}/{MAX_TURNS_LIMIT})]\n{user_message}")

    if turn_number >= MAX_TURNS_LIMIT:
        prompt_lines.append("\n※ 이번 턴이 세션의 마지막 턴(상한 도달)입니다. 대화를 따뜻하게 마무리 짓고 is_final: true로 응답하십시오.")

    user_prompt = "\n".join(prompt_lines)

    try:
        data = llm.complete_json(user_prompt, system=sys_prompt, temperature=0.3)
        msg = data.get("message", "말씀해 주신 상황을 괘의 흐름과 함께 깊이 새겨봅니다.")
        needs_f = bool(data.get("needs_followup", True))
        f_q = data.get("followup_question")
        is_fin = bool(data.get("is_final", False))
    except Exception:
        msg = "남겨주신 마음을 천천히 되짚어보게 됩니다. 지금 이 순간 가장 마음에 걸리는 점은 무엇인가요?"
        needs_f = True
        f_q = "지금 이 순간 가장 마음에 걸리는 점은 무엇인가요?"
        is_fin = False

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
    )
