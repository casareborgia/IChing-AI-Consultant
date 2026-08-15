"""[1] 정리 에이전트 (Intake Agent).

- 고민 명확화 (clarified_question) 및 주제 분류 (topic_category)
- 최근 과거 상담 목록 대조를 통한 재삼독(동일 질문 반복) 감지
"""

from typing import Any, Dict, List, Optional

from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from schemas.counsel import IntakeOutput


async def run_intake(
    message: str,
    *,
    past_sessions: Optional[List[Dict[str, Any]]] = None,
    client: Optional[LLMClient] = None,
) -> IntakeOutput:
    """사용자의 고민을 정리하고 재삼독 여부를 판정합니다.

    Args:
        message: 사용자의 최초 질문 발화
        past_sessions: 최근 과거 세션 목록 (list of dict: session_id, clarified_question, summary 등)
        client: 주입할 LLM 클라이언트 (테스트 시 Mock 주입)

    Returns:
        IntakeOutput 객체
    """
    sys_prompt = load_system_prompt("intake")
    llm = client or get_client(role="intake")

    user_lines = [f"[사용자 발화] {message}"]

    valid_session_ids = set()
    if past_sessions:
        user_lines.append("\n[과거 상담 목록]")
        for s in past_sessions:
            sid = str(s.get("session_id", ""))
            valid_session_ids.add(sid)
            q = s.get("clarified_question", "")
            summ = s.get("summary", "")
            user_lines.append(f"- 세션ID: {sid} | 질문: {q} | 요약: {summ}")
    else:
        user_lines.append("\n[과거 상담 목록] 없음 (신규 사용자 또는 이전 상담 없음)")

    user_msg = "\n".join(user_lines)

    try:
        data = llm.complete_json(user_msg, system=sys_prompt, temperature=0.0)
        is_dup = bool(data.get("is_duplicate_question", False))
        ref_id = data.get("duplicate_session_ref")

        # LLM 환각 방지: 후보 목록에 없는 ID면 None으로 보정
        if is_dup and (not ref_id or str(ref_id) not in valid_session_ids):
            is_dup = False
            ref_id = None

        return IntakeOutput(
            clarified_question=data.get("clarified_question", message),
            topic_category=data.get("topic_category", "기타"),
            is_duplicate_question=is_dup,
            duplicate_session_ref=ref_id,
        )
    except Exception as e:
        # 에러 발생 시 원본 발화를 그대로 질문으로 삼아 진행
        return IntakeOutput(
            clarified_question=message,
            topic_category="기타",
            is_duplicate_question=False,
            duplicate_session_ref=None,
        )
