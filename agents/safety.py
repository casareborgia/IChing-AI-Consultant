"""[0] 안전 스크리닝 에이전트 (Safety Screener).

- 사용자 발화 및 대화 맥락에서 위기(자해, 극단선택, 응급) 및 범위 밖(의료, 법률) 신호 감지
- 판정 카테고리: BLOCK_CRISIS, BLOCK_SCOPE, ASK, CAUTION, NORMAL
- 실패(통신 장애 등) 시 닫는 쪽(차단)으로 처리하되 사용자에게는 시스템 에러 문구 안내
- 내부 라벨/점수는 절대 사용자에게 노출하지 않음
"""

from functools import lru_cache
from typing import Optional

from core.llm import LLMClient, get_client
from core.prompts import load_prompt_block, load_system_prompt
from schemas.counsel import SafetyVerdict

VALID_CATEGORIES = {"BLOCK_CRISIS", "BLOCK_SCOPE", "ASK", "CAUTION", "NORMAL"}
VALID_CONTEXTS = {"minor", "violence"}

# 화면에 나가는 문구는 전부 prompts/safety_response.md에 있다. 여기에 복사해 두지
# 않는다 — 복사본이 있으면 .md를 고쳐도 화면은 그대로다. 실제로 그런 상태였고,
# 그래서 .md가 정의한 청소년·폭력 우선 문구가 한 번도 나가지 않았다.
_TEMPLATE_HEADINGS = {
    "crisis": "### 기본 템플릿",
    "crisis_minor": "### 청소년 정황 우선 템플릿",
    "crisis_violence": "### 폭력 피해 정황 우선 템플릿",
    "scope": "## 2. BLOCK_SCOPE",
    "caution": "## 3. CAUTION",
    "ask": "## 4. ASK",
    "error": "## 5. SYSTEM_ERROR",
}


@lru_cache(maxsize=None)
def get_template(key: str) -> str:
    """prompts/safety_response.md에서 문구 하나를 읽어온다."""
    if key not in _TEMPLATE_HEADINGS:
        raise KeyError(f"알 수 없는 안전 문구 키: {key}")
    return load_prompt_block("safety_response", _TEMPLATE_HEADINGS[key])


def _crisis_template_key(context: Optional[str]) -> str:
    """어느 위기 문구를 쓸지 고른다.

    미성년자 정황이면 1388을, 폭력 피해 정황이면 1366을 맨 위에 놓는다
    (CLAUDE.md 위기 대응 연락처 절). 정황이 불분명하면 기본 문구다 —
    억지로 고르는 것보다 109를 앞세운 일반 안내가 낫다.
    """
    if context == "minor":
        return "crisis_minor"
    if context == "violence":
        return "crisis_violence"
    return "crisis"


def caution_append_message() -> str:
    """CAUTION일 때 상담 답변 끝에 덧붙이는 문구."""
    return "\n\n" + get_template("caution")


def format_safety_response(verdict: SafetyVerdict) -> Optional[str]:
    """SafetyVerdict에 따라 사용자에게 직접 노출할 안내 문구를 반환합니다.

    NORMAL 또는 CAUTION인 경우 즉각적인 차단 메시지가 없으므로 None을 반환합니다.

    문구는 오직 판정에서만 나온다. 예전에는 `is_error` 인자로 오류 문구를 따로
    골랐는데, 부르는 쪽이 그 인자를 넘기지 않으면 통신 장애가 BLOCK_SCOPE 문구로
    나갔다. 갈래를 판정 하나로 모아 그 함정을 없앤다.
    """
    if verdict.category == "ERROR":
        return get_template("error")

    if verdict.category == "BLOCK_CRISIS":
        return get_template(_crisis_template_key(verdict.context))
    elif verdict.category == "BLOCK_SCOPE":
        return get_template("scope")
    elif verdict.category == "ASK":
        question = verdict.ask or "조금 더 구체적으로 어떤 상황인지 말씀해 주실 수 있나요?"
        return get_template("ask").replace("{ask_question}", question)
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

        # 안내처 힌트는 판정에 관여하지 않는다. 모르는 값이 오면 조용히 버리고
        # 기본 문구로 간다 — 여기서 예외를 던지면 위기 발화가 통째로 실패한다.
        ctx = data.get("context")
        if ctx not in VALID_CONTEXTS:
            ctx = None

        return SafetyVerdict(
            category=cat,
            ask=data.get("ask"),
            context=ctx,
            # `.get`의 기본값은 키가 **없을 때만** 쓰인다. 모델은 키를 담고 값을
            # null로 보내는 일이 있고, 그러면 None이 그대로 넘어가 스키마 검증에
            # 걸린다 — 그 예외를 아래 except가 받아 ERROR로 바꾸므로, 멀쩡한
            # 발화가 "연결 지연" 문구로 끝난다. 실제로 2턴째 이후에서 그랬다.
            signals=data.get("signals") or [],
            reason=data.get("reason") or "",
        )
    except Exception as e:
        # 스크리닝이 실패하면 괘를 뽑지 않는다(닫는 쪽). 다만 낙인은 남기지 않는다 —
        # BLOCK_CRISIS로 올리면 통신 장애에 자살예방 핫라인이 뜨고, BLOCK_SCOPE로
        # 내리면 진로 고민에 "의사·변호사와 상의하라"는 답이 나간다. 둘 다 아니다.
        return SafetyVerdict(
            category="ERROR",
            signals=["screening_error"],
            reason=f"안전 스크리닝 중 오류 발생: {e}",
        )
