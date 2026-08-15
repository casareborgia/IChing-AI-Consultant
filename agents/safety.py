"""[0] 안전 스크리닝 에이전트 (Safety Screener).

- 사용자 발화 및 대화 맥락에서 위기(자해, 극단선택, 응급) 및 범위 밖(의료, 법률) 신호 감지
- 판정 카테고리: BLOCK_CRISIS, BLOCK_SCOPE, ASK, CAUTION, NORMAL
- 실패(통신 장애 등) 시 닫는 쪽(차단)으로 처리하되 사용자에게는 시스템 에러 문구 안내
- 내부 라벨/점수는 절대 사용자에게 노출하지 않음
"""

from typing import Optional

from core.llm import LLMClient, get_client
from core.prompts import load_system_prompt
from schemas.counsel import SafetyVerdict

VALID_CATEGORIES = {"BLOCK_CRISIS", "BLOCK_SCOPE", "ASK", "CAUTION", "NORMAL"}

# 사용자 노출용 기본 응답 문구들
CRISIS_DEFAULT_MESSAGE = """지금 남겨주신 말씀을 그냥 지나칠 수 없었습니다.
혼자 감당하기 어려운 무거운 마음과 순간에는, 주역의 괘를 헤아리기보다 전문가의 따뜻한 손길을 먼저 마주하는 것이 가장 중요합니다.

지금 바로 24시간 언제든 무료로 도움을 받을 수 있는 곳이 있습니다:

* 자살예방 상담전화: ☎ 109 (24시간 무료)
* 정신건강 위기상담전화: ☎ 1577-0199 (24시간 무료)
* 청소년 상담전화: ☎ 1388 (24시간 무료)
* 여성긴급전화: ☎ 1366 (24시간 무료)

당신의 삶과 안전은 그 어떤 것보다 소중합니다. 잠시 숨을 고르시고, 위의 번호로 마음을 나누어 보시기를 간곡히 권합니다."""

SCOPE_DEFAULT_MESSAGE = """질문해 주신 내용은 전문적인 진단과 검토가 필요한 영역(의료/약물, 법률, 세무, 금융 등)에 해당합니다.

주역은 삶의 변화와 마음가짐을 성찰하는 도구이지만, 전문적인 판단이나 치료를 대신할 수는 없습니다. 안전하고 정확한 해결을 위해 해당 분야의 전문 기관이나 전문가(의사, 변호사 등)와 상의하시기를 권해드립니다."""

SYSTEM_ERROR_MESSAGE = """죄송합니다. 일시적인 시스템 연결 지연으로 인해 답변을 준비하지 못했습니다.
잠시 후 다시 말씀해 주시거나 새로고침 후 이용해 주시기 바랍니다."""

CAUTION_APPEND_MESSAGE = """\n\n> 💡 참고 안내: 주역의 괘와 상담 내용은 상황을 바라보는 새로운 관점과 성찰을 돕기 위한 참고 자료입니다. 마음의 큰 부담이나 지속적인 어려움이 있으실 때는 전문 심리상담이나 의료 기관의 도움도 함께 고려해 보세요."""


def format_safety_response(verdict: SafetyVerdict, *, is_error: bool = False) -> Optional[str]:
    """SafetyVerdict에 따라 사용자에게 직접 노출할 안내 문구를 반환합니다.

    NORMAL 또는 CAUTION인 경우 즉각적인 차단 메시지가 없으므로 None을 반환합니다.
    """
    if is_error:
        return SYSTEM_ERROR_MESSAGE

    if verdict.category == "BLOCK_CRISIS":
        return CRISIS_DEFAULT_MESSAGE
    elif verdict.category == "BLOCK_SCOPE":
        return SCOPE_DEFAULT_MESSAGE
    elif verdict.category == "ASK":
        question = verdict.ask or "조금 더 구체적으로 어떤 상황인지 말씀해 주실 수 있나요?"
        return f"남겨주신 고민을 주역의 괘로 깊이 들여다보기에 앞서, 한 가지 여쭙고 싶은 점이 있습니다.\n\n{question}\n\n생각나시는 대로 편하게 말씀해 주시면, 그 마음의 맥락을 담아 괘를 헤아려 드리겠습니다."
    return None


async def screen(
    text: str,
    *,
    history: Optional[str] = None,
    client: Optional[LLMClient] = None,
    latched_crisis: bool = False,
) -> SafetyVerdict:
    """사용자의 발화를 안전 스크리닝합니다.

    Args:
        text: 사용자 발화 텍스트
        history: 앞선 대화 요약 (선택 사항)
        client: 주입할 LLM 클라이언트 (테스트 시 Mock 주입)
        latched_crisis: 해당 세션에서 이미 BLOCK_CRISIS가 발생했는지 여부 (래치)

    Returns:
        SafetyVerdict 객체
    """
    # 래치: 이전 턴에서 이미 위기로 차단된 세션은 검사 없이 차단 유지
    if latched_crisis:
        return SafetyVerdict(
            category="BLOCK_CRISIS",
            signals=["latched_session"],
            reason="이전 턴에서 위기 신호가 감지되어 세션이 차단 상태로 고정되었습니다.",
        )

    sys_prompt = load_system_prompt("safety_screening")
    llm = client or get_client(role="safety")

    user_msg = f"[발화] {text}"
    if history:
        user_msg += f"\n[앞선 대화 요약] {history}"

    try:
        data = llm.complete_json(user_msg, system=sys_prompt, temperature=0.0)
        cat = data.get("category", "")
        if cat not in VALID_CATEGORIES:
            raise ValueError(f"유효하지 않은 안전 카테고리 응답: {cat}")

        return SafetyVerdict(
            category=cat,
            ask=data.get("ask"),
            signals=data.get("signals", []),
            reason=data.get("reason", ""),
        )
    except Exception as e:
        # LLM 호출 실패 시 보수적으로 닫는 쪽(BLOCK_SCOPE 또는 별도 에러 처리)으로 반환
        return SafetyVerdict(
            category="BLOCK_SCOPE",
            signals=["screening_error"],
            reason=f"안전 스크리닝 중 오류 발생: {e}",
        )
