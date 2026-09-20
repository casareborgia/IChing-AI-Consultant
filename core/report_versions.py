"""리포트 판본 판별과 공개 오류 코드.

저장된 `counsel_sessions.report_data`는 두 모양이 섞여 있다. 판본을 어디서
판별하는지가 한 곳으로 모여 있어야 소비자마다 다른 규칙을 갖지 않는다.
"""

from typing import Any, Mapping, Optional

REPORT_LEGACY = "legacy"
REPORT_V2 = "2.0"

# 저장된 값이 명시적 판본을 달고 있는데 그 판본을 모르는 경우.
# **legacy로 묵인하지 않는다** — legacy 소비자가 v3 문서를 v1로 읽으면 화면에
# 엉뚱한 칸이 뜨거나, 더 나쁘게는 빈칸이 정상처럼 보인다.
REPORT_UNKNOWN = "unknown"

# 공개 오류 코드. 응답 본문과 FE 분기에 쓰이므로 문자열을 함부로 바꾸지 않는다.
CODE_REPORT_UNAVAILABLE = "REPORT_UNAVAILABLE"


def report_schema_version(report_data: Optional[Mapping[str, Any]]) -> Optional[str]:
    """저장된 리포트의 판본.

    - 값이 없으면 `None`
    - 판본 표기가 없으면 `legacy` (v1은 `schema_version`을 쓴 적이 없다)
    - `"2.0"`이면 v2
    - 그 밖의 명시적 표기는 `unknown`
    """
    if not report_data or not isinstance(report_data, Mapping):
        return None
    declared = report_data.get("schema_version")
    if declared is None:
        return REPORT_LEGACY
    if declared == REPORT_V2:
        return REPORT_V2
    return REPORT_UNKNOWN


def public_report_error_code(exc: BaseException) -> str:
    """예외를 공개해도 되는 코드로 옮긴다.

    내부 예외 클래스 이름·프롬프트·사용자 고민이 응답이나 일반 운영 로그로
    나가지 않게 하는 경계다. 모르는 예외는 뭉뚱그린다 — 무엇이 터졌는지는
    `exc_info`가 붙은 오류 로그에만 남는다.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.startswith("REPORT_"):
        return code
    return CODE_REPORT_UNAVAILABLE
