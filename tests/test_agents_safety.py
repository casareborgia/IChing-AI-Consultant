"""안전 스크리너 및 래치 동작 검증 단위 테스트."""

from pathlib import Path

import pytest

from agents.safety import format_safety_response, get_template, screen
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
async def test_위기_문구는_정황에_따라_연락처_순서가_바뀐다():
    """미성년자면 1388, 폭력 피해면 1366이 맨 위에 와야 한다 (CLAUDE.md 위기 연락처 절)."""
    기본 = format_safety_response(SafetyVerdict(category="BLOCK_CRISIS"))
    청소년 = format_safety_response(SafetyVerdict(category="BLOCK_CRISIS", context="minor"))
    폭력 = format_safety_response(SafetyVerdict(category="BLOCK_CRISIS", context="violence"))

    def 첫_연락처(msg: str) -> str:
        for line in msg.split("\n"):
            for num in ("109", "1577-0199", "1388", "1366", "112"):
                if num in line:
                    return num
        raise AssertionError(f"연락처가 하나도 없다: {msg}")

    assert 첫_연락처(기본) == "109"
    assert 첫_연락처(청소년) == "1388"
    assert 첫_연락처(폭력) == "1366"
    assert 기본 != 청소년 != 폭력


@pytest.mark.asyncio
async def test_모르는_정황값은_기본_문구로_떨어진다():
    """힌트가 이상해도 위기 안내 자체는 나가야 한다. 여기서 예외가 나면 위기가 통째로 실패한다."""
    class OddContextLLM:
        def complete_json(self, user: str, *, system: str = "", **kwargs) -> dict:
            return {"category": "BLOCK_CRISIS", "context": "elderly", "signals": [], "reason": ""}

    verdict = await screen("다 끝내고 싶어요", client=OddContextLLM())
    assert verdict.category == "BLOCK_CRISIS"
    assert verdict.context is None
    assert format_safety_response(verdict) == get_template("crisis")


@pytest.mark.asyncio
async def test_문구는_코드가_아니라_프롬프트_파일에서_온다():
    """safety_response.md를 고치면 화면이 바뀌어야 한다.

    한동안 문구가 코드에 복사돼 있어 .md를 고쳐도 아무 변화가 없었다.
    """
    import agents.safety as safety_mod

    for key in ("crisis", "crisis_minor", "crisis_violence", "scope", "caution", "ask", "error"):
        assert get_template(key).strip(), f"{key} 문구가 비어 있다"

    # 코드에 문구 복사본이 남아 있으면 안 된다
    source = Path(safety_mod.__file__).read_text(encoding="utf-8")
    assert "자살예방 상담전화" not in source
    assert "1577-0199" not in source


@pytest.mark.asyncio
async def test_사용자_출력에_내부_라벨_미노출_전수_검증():
    """모든 판정 카테고리에 대해 사용자 응답에 내부 라벨 문자열이 없어야 함."""
    internal_labels = ["BLOCK_CRISIS", "BLOCK_SCOPE", "ASK", "CAUTION", "NORMAL", "ERROR"]

    for cat in internal_labels:
        v = SafetyVerdict(category=cat, ask="구체적인 상황을 알려주세요.", reason="테스트")
        user_msg = format_safety_response(v)
        if user_msg:
            for label in internal_labels:
                assert label not in user_msg, f"사용자 응답에 내부 라벨 '{label}'이 노출되었습니다: {user_msg}"


@pytest.mark.asyncio
async def test_LLM_통신_장애_시_안전한_차단_및_시스템_에러_출력():
    """실패는 다섯 판정 중 하나로 뭉개지 않는다.

    부르는 쪽이 별도 인자를 넘겨야만 에러 문구가 나오는 구조였을 때는,
    파이프라인이 그 인자를 넘기지 않아 통신 장애가 BLOCK_SCOPE 문구
    ("의사·변호사와 상의하십시오")로 사용자에게 나갔다.
    """
    mock_llm = FailingMockLLM()
    verdict = await screen("오늘 운세 어때?", client=mock_llm)
    assert verdict.category == "ERROR"
    assert "screening_error" in verdict.signals

    # 판정만으로 에러 문구가 나와야 한다 (추가 인자 없이)
    err_msg = format_safety_response(verdict)
    assert err_msg == get_template("error")
    # 위기 핫라인도, 범위 밖 안내도 섞이면 안 된다
    assert "109" not in err_msg
    assert "변호사" not in err_msg
