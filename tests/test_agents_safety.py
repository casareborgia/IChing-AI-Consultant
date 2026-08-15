"""안전 스크리너 및 래치 동작 검증 단위 테스트."""

import pytest

from agents.safety import format_safety_response, screen
from schemas.counsel import SafetyVerdict


class DummyMockLLM:
    """테스트용 Mock LLM 클라이언트."""

    def __init__(self, response_data: dict):
        self.response_data = response_data
        self.call_count = 0

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        self.call_count += 1
        return self.response_data


class FailingMockLLM:
    """호출 실패를 모사하는 Mock LLM."""

    def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
        raise ConnectionError("API 연결 실패")


@pytest.mark.asyncio
async def test_안전_스크리닝_정상_판정():
    mock_llm = DummyMockLLM({
        "category": "NORMAL",
        "signals": [],
        "reason": "일상적인 고민",
    })
    verdict = await screen("이직을 준비 중인데 조언이 필요해", client=mock_llm)
    assert verdict.category == "NORMAL"
    assert format_safety_response(verdict) is None
    assert mock_llm.call_count == 1


@pytest.mark.asyncio
async def test_안전_스크리닝_위기_감지_및_응답_문구():
    mock_llm = DummyMockLLM({
        "category": "BLOCK_CRISIS",
        "signals": ["자살 언급"],
        "reason": "자해/극단선택 위험",
    })
    verdict = await screen("모든 걸 끝내고 싶어", client=mock_llm)
    assert verdict.category == "BLOCK_CRISIS"

    msg = format_safety_response(verdict)
    assert msg is not None
    assert "109" in msg
    assert "1577-0199" in msg
    # 사용자 노출 문구에 내부 라벨이 없어야 함
    assert "BLOCK_CRISIS" not in msg


@pytest.mark.asyncio
async def test_위기_세션_래치_유지():
    """1턴에서 위기 감지 후 2턴에서 평온한 발화를 해도 LLM 호출 없이 차단이 유지되어야 함."""
    mock_llm = DummyMockLLM({
        "category": "NORMAL",
        "signals": [],
        "reason": "정상 발화",
    })

    # latched_crisis=True 인 경우
    verdict = await screen("이제 괜찮아요, 이직 얘기나 하죠", client=mock_llm, latched_crisis=True)
    assert verdict.category == "BLOCK_CRISIS"
    assert "latched_session" in verdict.signals
    # LLM이 호출되지 않아야 함
    assert mock_llm.call_count == 0


@pytest.mark.asyncio
async def test_사용자_출력에_내부_라벨_미노출_전수_검증():
    """모든 판정 카테고리에 대해 사용자 응답에 내부 라벨 문자열이 없어야 함."""
    internal_labels = ["BLOCK_CRISIS", "BLOCK_SCOPE", "ASK", "CAUTION", "NORMAL"]

    for cat in internal_labels:
        v = SafetyVerdict(category=cat, ask="구체적인 상황을 알려주세요.", reason="테스트")
        user_msg = format_safety_response(v)
        if user_msg:
            for label in internal_labels:
                assert label not in user_msg, f"사용자 응답에 내부 라벨 '{label}'이 노출되었습니다: {user_msg}"


@pytest.mark.asyncio
async def test_LLM_통신_장애_시_안전한_차단_및_시스템_에러_출력():
    mock_llm = FailingMockLLM()
    verdict = await screen("오늘 운세 어때?", client=mock_llm)
    # LLM 실패 시 보수적으로 BLOCK_SCOPE 처리
    assert verdict.category == "BLOCK_SCOPE"

    err_msg = format_safety_response(verdict, is_error=True)
    assert "일시적인 시스템 연결 지연" in err_msg
    # 에러 메시지에 109 핫라인이 오발송되지 않아야 함
    assert "109" not in err_msg
