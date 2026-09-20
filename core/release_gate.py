# -*- coding: utf-8 -*-
"""
출시 게이트 판정.

기계가 확인할 수 있는 것과 사람만 확인할 수 있는 것을 나눈다.

- 코드가 판정하는 것: 설정값의 정합성. 결제가 꺼져 있는지, provider가
  allowlist 안에 있는지, 유료 단계인데 mock provider를 쓰고 있지는 않은지.
- 코드가 판정할 수 없는 것: 실제 사업자 정보, 개인정보 처리 근거, 처리업체
  계약, 라이선스 확인. 이런 항목은 운영자가 `OPERATOR_ATTESTED_DECISIONS`에
  결정 ID를 명시해야 통과한다. 기본값이 비어 있으므로 기본은 전부 차단이다.

이 모듈은 판정만 하고 아무것도 바꾸지 않는다. 비밀값을 출력하지 않는다.
법적 적합성 판정을 대신하지 않는다 — 게이트가 열렸다는 것은 "설정이 서로
모순되지 않고 운영자가 확인했다고 표시했다"는 뜻뿐이다.
"""

import re
from dataclasses import dataclass, field
from typing import List, Set

from core.release_evidence import acceptance_evidence_problems

# 무료 베타를 열기 전에 운영자 확인이 필요한 결정.
# 결제가 없어도 개인정보·AI 고지·보안·라이선스는 그대로 남는다.
# D05(위기 차단 정책)는 무료 베타에서도 실제로 동작하는 기능이라 포함한다.
# D06(판매 단위)이 여기 있는 이유: 무료 베타도 크레딧을 소비한다. 가입 50C와
# 1턴 10C, 위기·장애 0C는 무료 베타에서 이미 실제로 적용되는 규칙이다.
FREE_BETA_REQUIRED_DECISIONS = (
    "D01", "D02", "D03", "D04", "D05", "D06", "D10", "D11", "D12", "D13",
)

# 유료 판매에 추가로 필요한 결정. 실제 금전 거래에만 해당한다.
COMMERCIAL_EXTRA_DECISIONS = ("D07", "D08", "D09")

VALID_STAGES = ("free_beta", "commercial")

# 코드에 어댑터가 실제로 존재하는 결제 provider.
# 새 어댑터를 구현한 사람이 여기에 이름을 추가한다. 설정 문자열만으로는
# 구현이 있다고 판정하지 않는다.
IMPLEMENTED_PAYMENT_PROVIDERS = frozenset({"mock"})

# 실제 판매에 쓸 수 있는 provider. mock은 구현돼 있지만 판매용이 아니다.
# 현재 비어 있으므로 commercial_launch_ready는 항상 false다. 이것은 결함이
# 아니라 사실이다 — 아직 어떤 PG도 연동돼 있지 않다.
SELLABLE_PAYMENT_PROVIDERS = IMPLEMENTED_PAYMENT_PROVIDERS - {"mock"}


# 미기입 상태를 그럴듯한 문자열로 덮은 값들. 대소문자 무시로 비교한다.
_PLACEHOLDER_VALUES = frozenset({
    "todo", "tbd", "fixme", "changeme", "change-me", "placeholder", "none",
    "n/a", "na", "null", "unknown", "xxx", "example", "sample", "test",
    "your-value", "your_value", "dummy", "-", "0",
})

# 날짜 기반 정책 버전. 예: 2026-09-08, 2026-09-08.2
_VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(\.\d+)?$")
# ISO 날짜.
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# git 커밋 SHA 40자리 소문자 16진수.
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
# 검사 묶음 버전의 형식. 형식이 맞는다고 그 묶음이 존재한다는 뜻은 아니다.
# 실제로 출시 자격이 있는 묶음인지는 core/release_evidence.py의
# RELEASE_ELIGIBLE_SUITE_VERSIONS가 판정하며, 현재 그 registry는 비어 있다.
_SUITE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{4,}$")


def _is_placeholder(value: str) -> bool:
    return (value or "").strip().lower() in _PLACEHOLDER_VALUES


def _check_field(problems: List[str], name: str, value: str, pattern, hint: str) -> None:
    """빈 값·placeholder·형식 불일치를 각각 다른 이유로 잡는다."""
    raw = (value or "").strip()
    if not raw:
        problems.append(f"{name}이(가) 비어 있음")
    elif _is_placeholder(raw):
        problems.append(f"{name}이(가) placeholder 값임")
    elif not pattern.match(raw):
        problems.append(f"{name} 형식이 올바르지 않음 ({hint})")


def check_free_beta_evidence(settings) -> List[str]:
    """무료 베타 공개에 필요한 증거가 갖춰졌는지 검사한다.

    코드가 확인할 수 있는 것은 형식과 미기입 여부뿐이다. 값이 사실인지는
    판정하지 못한다. 그래도 D 번호 문자열만 나열해 두고 게이트가 열리는 것은
    막을 수 있다. 반환값이 비어 있으면 형식상 증거가 갖춰진 것이다.
    """
    problems: List[str] = []

    _check_field(
        problems, "LEGAL_DOCUMENTS_VERSION", settings.LEGAL_DOCUMENTS_VERSION,
        _VERSION_PATTERN, "YYYY-MM-DD 또는 YYYY-MM-DD.N",
    )
    if not settings.LEGAL_DOCUMENTS_PUBLISHED:
        problems.append("정책 문서가 게시 상태가 아님 (LEGAL_DOCUMENTS_PUBLISHED)")

    approver = (settings.FREE_BETA_LAUNCH_APPROVED_BY or "").strip()
    if not approver:
        problems.append("FREE_BETA_LAUNCH_APPROVED_BY이(가) 비어 있음")
    elif _is_placeholder(approver) or len(approver) < 2:
        problems.append("FREE_BETA_LAUNCH_APPROVED_BY이(가) placeholder 값임")

    _check_field(
        problems, "FREE_BETA_LAUNCH_APPROVED_AT", settings.FREE_BETA_LAUNCH_APPROVED_AT,
        _DATE_PATTERN, "YYYY-MM-DD",
    )
    _check_field(
        problems, "ACCEPTANCE_EVIDENCE_SHA", settings.ACCEPTANCE_EVIDENCE_SHA,
        _SHA_PATTERN, "40자리 git SHA",
    )
    _check_field(
        problems, "ACCEPTANCE_EVIDENCE_SUITE_VERSION",
        settings.ACCEPTANCE_EVIDENCE_SUITE_VERSION,
        _SUITE_PATTERN, "예: <이름>/<버전>",
    )

    # 위 두 값은 기대값일 뿐이다. 승인된 신뢰 anchor로 검증되는 서명된 manifest가
    # 같은 값을 담고, 출시 자격이 있는 suite에서 실제 PASS를 증명해야 통과한다.
    # 형식만으로도, 런타임 환경변수만으로도 열리지 않는다.
    problems.extend(acceptance_evidence_problems(settings))

    return problems


@dataclass
class GateStatus:
    """게이트 판정 결과. JSON으로 그대로 직렬화할 수 있게 원시 타입만 쓴다."""

    service_stage: str
    config_consistent: bool
    free_beta_ready: bool
    commercial_config_ready: bool
    commercial_launch_ready: bool
    blocking_ids: List[str] = field(default_factory=list)
    next_safe_action: str = ""

    def to_dict(self) -> dict:
        return {
            "service_stage": self.service_stage,
            "config_consistent": self.config_consistent,
            "free_beta_ready": self.free_beta_ready,
            # 설정과 운영자 표시가 유료 판매 형태로 갖춰졌는지만 뜻한다.
            # 구현·검증 증거는 포함하지 않는다.
            "commercial_config_ready": self.commercial_config_ready,
            # 위에 더해 실제로 판매 가능한 provider 어댑터가 있어야 true다.
            "commercial_launch_ready": self.commercial_launch_ready,
            "blocking_ids": list(self.blocking_ids),
            "next_safe_action": self.next_safe_action,
        }


def parse_csv_setting(raw: str) -> Set[str]:
    """쉼표로 구분된 설정을 집합으로 바꾼다. 공백과 빈 항목은 버린다."""
    return {item.strip() for item in (raw or "").split(",") if item.strip()}


def check_config_consistency(settings) -> List[str]:
    """설정끼리 모순되는 지점을 찾는다. 반환값이 비어 있으면 정합적이다."""
    problems: List[str] = []

    if settings.SERVICE_STAGE not in VALID_STAGES:
        problems.append(
            f"SERVICE_STAGE가 {VALID_STAGES} 중 하나가 아님: {settings.SERVICE_STAGE!r}"
        )

    allowed_providers = parse_csv_setting(settings.LLM_ALLOWED_PROVIDERS)
    if settings.LLM_PROVIDER not in allowed_providers:
        problems.append(
            f"LLM_PROVIDER {settings.LLM_PROVIDER!r}가 LLM_ALLOWED_PROVIDERS에 없음"
        )

    # 리전은 Vertex 경로에서만 의미가 있다. 로컬 provider는 검사하지 않는다.
    if settings.LLM_PROVIDER in ("gemini", "anthropic"):
        allowed_regions = parse_csv_setting(settings.LLM_ALLOWED_REGIONS)
        for name in ("GEMINI_LOCATION", "CLAUDE_LOCATION"):
            region = getattr(settings, name, "")
            if region and region not in allowed_regions:
                problems.append(f"{name} {region!r}가 LLM_ALLOWED_REGIONS에 없음")

    if settings.SERVICE_STAGE == "free_beta" and settings.PURCHASE_ENABLED:
        problems.append("free_beta 단계에서 PURCHASE_ENABLED가 켜져 있음")

    if settings.PURCHASE_ENABLED:
        if settings.PAYMENT_PROVIDER not in IMPLEMENTED_PAYMENT_PROVIDERS:
            # 임의 문자열이 "구현된 provider"로 통과하면 안 된다.
            problems.append(
                f"PAYMENT_PROVIDER {settings.PAYMENT_PROVIDER!r}에 해당하는 구현이 없음"
            )
        elif settings.PAYMENT_PROVIDER not in SELLABLE_PAYMENT_PROVIDERS:
            problems.append(
                f"PAYMENT_PROVIDER {settings.PAYMENT_PROVIDER!r}는 실제 판매용이 아님"
            )

    if settings.PAID_CREDIT_EXPIRY_ENABLED and not settings.PURCHASE_ENABLED:
        problems.append("유료 결제가 없는데 PAID_CREDIT_EXPIRY_ENABLED가 켜져 있음")

    if getattr(settings, "LLM_BUDGET_ENABLED", False):
        daily_limit = getattr(settings, "LLM_DAILY_COST_BUDGET_USD", 0.0)
        monthly_limit = getattr(settings, "LLM_MONTHLY_COST_BUDGET_USD", 0.0)
        if daily_limit < 0 or monthly_limit < 0:
            problems.append("LLM_BUDGET_ENABLED가 켜져 있는데 일일/월간 한도가 음수임")

    return problems


def evaluate_release_gate(settings) -> GateStatus:
    """현재 설정으로 무료 베타와 유료 판매의 준비 상태를 판정한다."""
    blocking: List[str] = []

    config_problems = check_config_consistency(settings)
    blocking.extend(config_problems)

    attested = parse_csv_setting(settings.OPERATOR_ATTESTED_DECISIONS)

    missing_free = [d for d in FREE_BETA_REQUIRED_DECISIONS if d not in attested]
    blocking.extend(missing_free)

    # D 번호 나열만으로는 열리지 않는다. 검토 결과물이 실재한다는 증거가 필요하다.
    evidence_problems = check_free_beta_evidence(settings)
    blocking.extend(evidence_problems)

    missing_commercial = [d for d in COMMERCIAL_EXTRA_DECISIONS if d not in attested]

    config_consistent = not config_problems
    free_beta_ready = config_consistent and not missing_free and not evidence_problems

    # 설정과 운영자 표시만 본다. 구현·검증 증거는 포함하지 않는다.
    commercial_config_ready = (
        free_beta_ready
        and settings.SERVICE_STAGE == "commercial"
        and settings.PURCHASE_ENABLED
        and not missing_commercial
    )
    # 실제 판매 가능한 provider 어댑터가 있어야 한다. 설정 문자열이 mock이
    # 아니라는 것만으로는 부족하다. 현재 registry가 비어 있어 항상 false다.
    commercial_launch_ready = (
        commercial_config_ready
        and settings.PAYMENT_PROVIDER in SELLABLE_PAYMENT_PROVIDERS
    )

    if config_problems:
        next_safe_action = "설정 모순을 먼저 해소한다. 운영 변경 없이 값만 고친다."
    elif evidence_problems and not missing_free:
        next_safe_action = (
            "결정 ID는 모두 표시됐지만 공개 증거가 갖춰지지 않았다. "
            "정책 버전·게시 상태, 베타 공개 승인, 인수기준 검증 SHA를 기입한다."
        )
    elif missing_free:
        next_safe_action = (
            "운영자가 확인을 마친 결정 ID를 OPERATOR_ATTESTED_DECISIONS에 기입한다. "
            "코딩 에이전트가 대신 채우지 않는다."
        )
    elif commercial_config_ready and not commercial_launch_ready:
        next_safe_action = (
            "설정은 유료 판매 형태지만 판매 가능한 결제 어댑터가 없다. "
            "SELLABLE_PAYMENT_PROVIDERS가 비어 있다."
        )
    elif not commercial_launch_ready:
        next_safe_action = "무료 베타 범위는 준비됨. 유료 판매는 결제 구현과 D06~D09 승인 이후."
    else:
        next_safe_action = "설정 기준으로는 차단 없음. 실제 출시 승인은 운영자 판단."

    return GateStatus(
        service_stage=settings.SERVICE_STAGE,
        config_consistent=config_consistent,
        free_beta_ready=free_beta_ready,
        commercial_config_ready=commercial_config_ready,
        commercial_launch_ready=commercial_launch_ready,
        blocking_ids=blocking,
        next_safe_action=next_safe_action,
    )


def public_service_config(settings, consultation_credit_cost: int, welcome_credits: int) -> dict:
    """프런트가 읽을 최소 공개 설정.

    프런트가 요율이나 1회 차감량을 따로 하드코딩하지 않게 서버가 알려준다.
    비밀키·내부 검토 내용·운영자 결정 원문은 포함하지 않는다.
    """
    gate = evaluate_release_gate(settings)
    return {
        "service_stage": settings.SERVICE_STAGE,
        "purchase_enabled": settings.PURCHASE_ENABLED,
        "generation_enabled": settings.GENERATION_ENABLED,
        "consultation_credit_cost": consultation_credit_cost,
        "welcome_credits": welcome_credits,
        # 정책 문서가 초안 상태인지 화면에 표시하기 위한 값.
        # 기존 소비자 호환을 위해 유지한다.
        "policy_documents_draft": not gate.free_beta_ready,
        # 무료 베타 공개 준비 상태. 추가 필드이므로 기존 소비자에 영향이 없다.
        "free_beta_ready": gate.free_beta_ready,
        # 법적 정책 문서 버전 (서버 단일 출처)
        "legal_documents_version": settings.LEGAL_DOCUMENTS_VERSION,
        # 12시간 무료 자동 충전 정책 (설정 단일 출처)
        "free_beta_refill_credits": getattr(settings, "FREE_BETA_REFILL_CREDITS", 50),
        "free_beta_refill_hours": getattr(settings, "FREE_BETA_REFILL_HOURS", 12),
    }


def service_gate_reason(settings) -> str:
    """현재 단계 기준으로 상담 서비스를 열 수 없는 이유. 열 수 있으면 빈 문자열.

    운영 킬 스위치(GENERATION_ENABLED)와는 의미가 다르다. 이쪽은 "출시 준비가
    끝났는가"이고, 킬 스위치는 "지금 당장 내려야 하는가"다. 둘을 한 값으로
    합치면 장애 대응으로 내린 것과 준비가 안 된 것을 구분할 수 없다.
    """
    gate = evaluate_release_gate(settings)

    if settings.SERVICE_STAGE == "commercial":
        if not gate.commercial_launch_ready:
            return "commercial 단계의 출시 준비가 끝나지 않았습니다."
        return ""

    if not gate.free_beta_ready:
        return "무료 베타 출시 준비가 끝나지 않았습니다."
    return ""
