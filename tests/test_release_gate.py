"""출시 게이트 판정 테스트 (T01-BE).

인수기준 A04(가짜 사업자·미승인 정책·mock 운영결제 상태에서 실제 판매 불가)와
A05(UI·API가 같은 정책 설정을 본다)를 코드로 확인할 수 있는 범위까지 검증한다.

여기서 확인하는 것은 설정 정합성과 운영자 표시 여부뿐이다. 실제 사업자 정보나
법적 적합성은 코드가 판정하지 않으며 이 테스트도 그것을 주장하지 않는다.
"""

import base64
import json
import pathlib
import tempfile
from dataclasses import dataclass

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core import release_evidence, release_trust
from core.release_evidence import (
    MANIFEST_SCHEMA,
    REQUIRED_CHECKS,
    canonical_payload_bytes,
    payload_digest,
)

from core.release_gate import (
    COMMERCIAL_EXTRA_DECISIONS,
    FREE_BETA_REQUIRED_DECISIONS,
    check_config_consistency,
    evaluate_release_gate,
    parse_csv_setting,
    public_service_config,
)


@dataclass
class FakeSettings:
    """실제 Settings의 게이트 관련 필드만 흉내 낸다."""

    SERVICE_STAGE: str = "free_beta"
    PURCHASE_ENABLED: bool = False
    PAYMENT_PROVIDER: str = "mock"
    PAID_CREDIT_EXPIRY_ENABLED: bool = False
    QUALITY_REUSE_ENABLED: bool = False
    GENERATION_ENABLED: bool = True
    LLM_PROVIDER: str = "gemini"
    LLM_ALLOWED_PROVIDERS: str = "gemini,ollama,lmstudio,anthropic"
    LLM_ALLOWED_REGIONS: str = "us-central1,us-east5"
    GEMINI_LOCATION: str = "us-central1"
    CLAUDE_LOCATION: str = "us-east5"
    OPERATOR_ATTESTED_DECISIONS: str = ""
    # 증거 필드 (CYCLE-01-R3). 기본값은 전부 미기입 = fail-closed.
    LEGAL_DOCUMENTS_VERSION: str = ""
    LEGAL_DOCUMENTS_PUBLISHED: bool = False
    FREE_BETA_LAUNCH_APPROVED_BY: str = ""
    FREE_BETA_LAUNCH_APPROVED_AT: str = ""
    ACCEPTANCE_EVIDENCE_SHA: str = ""
    ACCEPTANCE_EVIDENCE_SUITE_VERSION: str = ""
    ACCEPTANCE_MANIFEST_PATH: str = ""
    ACCEPTANCE_EVIDENCE_PUBLIC_KEY: str = ""
    BUILD_GIT_SHA: str = ""


def attest(*ids: str) -> str:
    return ",".join(ids)


# 테스트용 임시 서명키와 manifest. 실제 CI 키도 운영 증거도 아니다.
# 저장소에 남지 않도록 임시 디렉터리에 만든다.
_TEST_KEY = Ed25519PrivateKey.generate()
_TEST_SHA = "0123456789abcdef0123456789abcdef01234567"
_TEST_SUITE = "acceptance-under-test/v1"


def _write_test_manifest() -> str:
    payload = {
        "schema": MANIFEST_SCHEMA,
        "target_sha": _TEST_SHA,
        "suite_version": _TEST_SUITE,
        "result": "PASS",
        "generated_at": "2026-09-09T00:00:00Z",
        "checks": [{"name": name, "result": "PASS"} for name in REQUIRED_CHECKS],
    }
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": base64.b64encode(
            _TEST_KEY.sign(canonical_payload_bytes(payload))
        ).decode("ascii"),
    }
    path = pathlib.Path(tempfile.mkdtemp()) / "acceptance.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    return str(path)


_TEST_MANIFEST_PATH = _write_test_manifest()
_TEST_PUBLIC_KEY = base64.b64encode(
    _TEST_KEY.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
).decode("ascii")

# --- 테스트 전용 신뢰 anchor -------------------------------------------------
#
# 제품 registry는 비어 있다(core/release_trust.py). 그래서 아무 것도 하지 않으면
# 이 파일의 "게이트가 열린 상태" 테스트를 만들 수 없다. 게이트가 열린 뒤의
# 동작은 계속 검증해야 하므로 각 테스트가 실행되는 동안에만 임시 키와 suite를
# 승인한다. import 시 모듈 전역을 바꾸면 다른 테스트의 게이트 판정이 수집 순서에
# 따라 달라지므로 금지한다.
#
TEST_RELEASE_PUBLIC_KEY = _TEST_PUBLIC_KEY
TEST_RELEASE_SUITE = _TEST_SUITE


@pytest.fixture(autouse=True)
def _scoped_test_release_registry(monkeypatch):
    monkeypatch.setattr(
        release_trust,
        "APPROVED_ACCEPTANCE_PUBLIC_KEYS",
        (TEST_RELEASE_PUBLIC_KEY,),
    )
    monkeypatch.setattr(
        release_evidence,
        "RELEASE_ELIGIBLE_SUITE_VERSIONS",
        frozenset({TEST_RELEASE_SUITE}),
    )
    monkeypatch.setattr(
        release_evidence,
        "KNOWN_SUITE_VERSIONS",
        frozenset(
            release_evidence.KNOWN_SUITE_VERSIONS | {TEST_RELEASE_SUITE}
        ),
    )


# 형식상 유효한 증거 한 벌. 실제 승인값이 아니라 테스트용 합성값이다.
VALID_EVIDENCE = dict(
    LEGAL_DOCUMENTS_VERSION="2026-09-08.1",
    LEGAL_DOCUMENTS_PUBLISHED=True,
    FREE_BETA_LAUNCH_APPROVED_BY="operator-under-test",
    FREE_BETA_LAUNCH_APPROVED_AT="2026-09-08",
    ACCEPTANCE_EVIDENCE_SHA=_TEST_SHA,
    ACCEPTANCE_EVIDENCE_SUITE_VERSION=_TEST_SUITE,
    ACCEPTANCE_MANIFEST_PATH=_TEST_MANIFEST_PATH,
    ACCEPTANCE_EVIDENCE_PUBLIC_KEY=_TEST_PUBLIC_KEY,
    BUILD_GIT_SHA=_TEST_SHA,
)


def ready_free_beta(**overrides) -> "FakeSettings":
    """무료 베타가 열리는 완전한 fixture. 개별 조건을 덮어써 차단을 검증한다."""
    base = dict(
        OPERATOR_ATTESTED_DECISIONS=attest(*FREE_BETA_REQUIRED_DECISIONS),
        **VALID_EVIDENCE,
    )
    base.update(overrides)
    return FakeSettings(**base)


def test_default_settings_are_config_consistent():
    """기본값끼리는 모순이 없어야 한다. 있으면 서비스가 기동하지 못한다."""
    assert check_config_consistency(FakeSettings()) == []


def test_default_blocks_both_gates():
    """운영자 표시가 없으면 무료 베타도 유료도 열리지 않는다 (fail-closed)."""
    gate = evaluate_release_gate(FakeSettings())
    assert gate.free_beta_ready is False
    assert gate.commercial_launch_ready is False
    assert set(FREE_BETA_REQUIRED_DECISIONS) <= set(gate.blocking_ids)


def test_free_beta_opens_without_payment_decisions():
    """무료 베타는 결제 결정(D06~D09) 없이도 열릴 수 있어야 한다.

    CYCLE-01-R3 정정: 예전에는 D 번호 나열만으로 열린다고 단언했다. 이제는
    공개 증거까지 갖춘 fixture여야 열린다.
    """
    gate = evaluate_release_gate(ready_free_beta())
    assert gate.free_beta_ready is True
    assert gate.commercial_launch_ready is False
    assert gate.blocking_ids == []


def test_free_beta_ready_does_not_imply_commercial():
    """무료 베타 준비가 유료 판매 승인으로 승격되지 않는다."""
    all_decisions = FREE_BETA_REQUIRED_DECISIONS + COMMERCIAL_EXTRA_DECISIONS
    gate = evaluate_release_gate(
        ready_free_beta(OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions))
    )
    # 결정은 전부 표시됐지만 단계와 스위치가 free_beta라 유료는 여전히 닫혀 있다.
    assert gate.free_beta_ready is True
    assert gate.commercial_launch_ready is False


def test_commercial_requires_stage_switch_and_real_provider():
    """A04: mock provider로는 유료 판매가 열리지 않는다.

    CYCLE-00-R2 정정: 예전에는 "mock이 아닌 문자열"이면 열린다고 단언했다.
    그 판정이 P1이었다. 이제는 구현 registry를 기준으로 하므로 `toss`처럼
    어댑터가 없는 이름은 설정 모순으로 잡힌다.
    """
    all_decisions = FREE_BETA_REQUIRED_DECISIONS + COMMERCIAL_EXTRA_DECISIONS

    # 단계와 스위치를 올렸지만 provider가 mock이면 판매용이 아니라 막힌다.
    mocked = FakeSettings(
        SERVICE_STAGE="commercial",
        PURCHASE_ENABLED=True,
        PAYMENT_PROVIDER="mock",
        OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions),
    )
    assert check_config_consistency(mocked) != []
    assert evaluate_release_gate(mocked).commercial_launch_ready is False

    # 어댑터가 없는 이름은 "구현 없음"으로 잡힌다. 문자열만으로 열리지 않는다.
    unimplemented = FakeSettings(
        SERVICE_STAGE="commercial",
        PURCHASE_ENABLED=True,
        PAYMENT_PROVIDER="toss",
        OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions),
    )
    assert check_config_consistency(unimplemented) != []
    assert evaluate_release_gate(unimplemented).commercial_launch_ready is False


def test_free_beta_stage_rejects_purchase_switch():
    """free_beta 단계에서 결제를 켜면 설정 모순으로 잡힌다."""
    problems = check_config_consistency(
        FakeSettings(SERVICE_STAGE="free_beta", PURCHASE_ENABLED=True)
    )
    assert any("PURCHASE_ENABLED" in p for p in problems)


def test_provider_and_region_allowlist():
    """키가 있다는 이유로 allowlist 밖 경로로 넘어가지 않게 막는다."""
    off_provider = check_config_consistency(
        FakeSettings(LLM_PROVIDER="openai")
    )
    assert any("LLM_PROVIDER" in p for p in off_provider)

    off_region = check_config_consistency(
        FakeSettings(GEMINI_LOCATION="europe-west1")
    )
    assert any("GEMINI_LOCATION" in p for p in off_region)


def test_local_provider_skips_region_check():
    """로컬 provider에는 리전 개념이 없으므로 리전 검사를 적용하지 않는다."""
    assert check_config_consistency(
        FakeSettings(LLM_PROVIDER="ollama", GEMINI_LOCATION="europe-west1")
    ) == []


def test_paid_expiry_requires_purchase():
    """유료 결제가 없는데 유료 소멸 배치를 켜면 모순이다."""
    problems = check_config_consistency(
        FakeSettings(PAID_CREDIT_EXPIRY_ENABLED=True, PURCHASE_ENABLED=False)
    )
    assert any("PAID_CREDIT_EXPIRY_ENABLED" in p for p in problems)


def test_invalid_stage_is_rejected():
    """오타 난 단계 이름이 조용히 통과하면 안 된다."""
    problems = check_config_consistency(FakeSettings(SERVICE_STAGE="beta"))
    assert any("SERVICE_STAGE" in p for p in problems)


def test_parse_csv_setting_tolerates_spacing():
    assert parse_csv_setting(" D01 , D02 ,, ") == {"D01", "D02"}
    assert parse_csv_setting("") == set()
    assert parse_csv_setting(None) == set()


def test_public_config_exposes_rates_and_no_secrets():
    """A05: 프런트가 요율을 하드코딩하지 않도록 서버가 알려준다. 비밀값은 없다."""
    payload = public_service_config(
        FakeSettings(), consultation_credit_cost=10, welcome_credits=50
    )
    assert payload["consultation_credit_cost"] == 10
    assert payload["welcome_credits"] == 50
    assert payload["purchase_enabled"] is False
    assert payload["service_stage"] == "free_beta"
    # 운영자 표시 전이므로 정책 문서는 초안 상태로 표시된다.
    assert payload["policy_documents_draft"] is True

    forbidden = ("SECRET", "KEY", "PASSWORD", "TOKEN", "DATABASE_URL", "ATTESTED")
    flat = " ".join(str(k) + str(v) for k, v in payload.items()).upper()
    for word in forbidden:
        assert word not in flat


def test_gate_status_is_json_serializable():
    """Codex의 출시 검사 스크립트가 그대로 직렬화할 수 있어야 한다."""
    import json

    payload = evaluate_release_gate(FakeSettings()).to_dict()
    assert json.loads(json.dumps(payload))["free_beta_ready"] is False


@pytest.mark.parametrize("missing", FREE_BETA_REQUIRED_DECISIONS)
def test_any_missing_free_beta_decision_blocks(missing):
    """무료 베타 필수 결정 중 하나만 빠져도 열리지 않는다."""
    remaining = [d for d in FREE_BETA_REQUIRED_DECISIONS if d != missing]
    gate = evaluate_release_gate(
        ready_free_beta(OPERATOR_ATTESTED_DECISIONS=attest(*remaining))
    )
    assert gate.free_beta_ready is False
    assert missing in gate.blocking_ids


# --- CYCLE-00-R2: payment provider registry (P1-2) ---


def test_arbitrary_provider_string_is_not_implemented():
    """PAYMENT_PROVIDER=not-implemented 같은 임의 문자열이 통과하면 안 된다."""
    problems = check_config_consistency(
        FakeSettings(
            SERVICE_STAGE="commercial",
            PURCHASE_ENABLED=True,
            PAYMENT_PROVIDER="not-implemented",
        )
    )
    assert any("구현이 없음" in p for p in problems)


def test_commercial_launch_never_ready_without_sellable_provider():
    """판매 가능한 어댑터가 없으면 어떤 설정으로도 유료 출시가 열리지 않는다."""
    from core.release_gate import SELLABLE_PAYMENT_PROVIDERS

    assert SELLABLE_PAYMENT_PROVIDERS == frozenset()

    all_decisions = FREE_BETA_REQUIRED_DECISIONS + COMMERCIAL_EXTRA_DECISIONS
    for provider in ("mock", "not-implemented", "toss", "portone"):
        gate = evaluate_release_gate(
            ready_free_beta(
                SERVICE_STAGE="commercial",
                PURCHASE_ENABLED=True,
                PAYMENT_PROVIDER=provider,
                OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions),
            )
        )
        assert gate.commercial_launch_ready is False, provider


def test_commercial_config_ready_is_separate_from_launch_ready():
    """설정 정합성만 뜻하는 상태를 별도로 둔다."""
    all_decisions = FREE_BETA_REQUIRED_DECISIONS + COMMERCIAL_EXTRA_DECISIONS
    gate = evaluate_release_gate(
        ready_free_beta(
            SERVICE_STAGE="commercial",
            PURCHASE_ENABLED=True,
            PAYMENT_PROVIDER="mock",
            OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions),
        )
    )
    # mock은 구현돼 있지만 판매용이 아니라 모순으로 잡힌다.
    assert gate.commercial_config_ready is False
    assert gate.commercial_launch_ready is False
    assert any("판매용이 아님" in b for b in gate.blocking_ids)


def test_gate_dict_exposes_both_commercial_fields():
    payload = evaluate_release_gate(FakeSettings()).to_dict()
    assert payload["commercial_config_ready"] is False
    assert payload["commercial_launch_ready"] is False


# --- CYCLE-00-R2: 상담 API 게이트 연결 (P1-1) ---


def test_service_gate_reason_blocks_unattested_free_beta():
    from core.release_gate import service_gate_reason

    assert service_gate_reason(FakeSettings()) != ""


def test_service_gate_reason_opens_attested_free_beta():
    from core.release_gate import service_gate_reason

    assert service_gate_reason(ready_free_beta()) == ""


def test_service_gate_reason_blocks_commercial_without_provider():
    from core.release_gate import service_gate_reason

    all_decisions = FREE_BETA_REQUIRED_DECISIONS + COMMERCIAL_EXTRA_DECISIONS
    reason = service_gate_reason(
        ready_free_beta(
            SERVICE_STAGE="commercial",
            PURCHASE_ENABLED=True,
            PAYMENT_PROVIDER="mock",
            OPERATOR_ATTESTED_DECISIONS=attest(*all_decisions),
        )
    )
    assert reason != ""


# --- CYCLE-01-R3: D 번호만으로 열리지 않는다 ---


def test_d05_is_required_for_free_beta():
    """D05(위기 차단)는 무료 베타에서도 실제로 동작하는 기능이라 필수다."""
    assert "D05" in FREE_BETA_REQUIRED_DECISIONS

    without_d05 = [d for d in FREE_BETA_REQUIRED_DECISIONS if d != "D05"]
    gate = evaluate_release_gate(
        ready_free_beta(OPERATOR_ATTESTED_DECISIONS=attest(*without_d05))
    )
    assert gate.free_beta_ready is False
    assert "D05" in gate.blocking_ids


def test_decision_ids_alone_do_not_open_gate():
    """핵심 회귀: D 번호를 전부 나열해도 증거가 없으면 열리지 않는다."""
    gate = evaluate_release_gate(
        FakeSettings(OPERATOR_ATTESTED_DECISIONS=attest(*FREE_BETA_REQUIRED_DECISIONS))
    )
    assert gate.free_beta_ready is False
    # 차단 사유가 D 누락이 아니라 증거 부족으로 나와야 한다.
    assert not any(b.startswith("D") and len(b) == 3 for b in gate.blocking_ids)
    assert gate.blocking_ids


def test_default_settings_block_on_both_decisions_and_evidence():
    gate = evaluate_release_gate(FakeSettings())
    assert gate.free_beta_ready is False
    assert set(FREE_BETA_REQUIRED_DECISIONS) <= set(gate.blocking_ids)
    assert any("비어 있음" in b for b in gate.blocking_ids)


# --- CYCLE-01-R3: 증거 항목별 차단 ---


def test_draft_policy_blocks():
    """정책이 게시 상태가 아니면 열리지 않는다."""
    gate = evaluate_release_gate(ready_free_beta(LEGAL_DOCUMENTS_PUBLISHED=False))
    assert gate.free_beta_ready is False
    assert any("게시 상태가 아님" in b for b in gate.blocking_ids)


def test_missing_operator_approval_blocks():
    gate = evaluate_release_gate(ready_free_beta(FREE_BETA_LAUNCH_APPROVED_BY=""))
    assert gate.free_beta_ready is False
    assert any("APPROVED_BY" in b for b in gate.blocking_ids)


def test_missing_test_evidence_blocks():
    gate = evaluate_release_gate(ready_free_beta(ACCEPTANCE_EVIDENCE_SHA=""))
    assert gate.free_beta_ready is False
    assert any("ACCEPTANCE_EVIDENCE_SHA" in b for b in gate.blocking_ids)


@pytest.mark.parametrize(
    "field",
    [
        "LEGAL_DOCUMENTS_VERSION",
        "FREE_BETA_LAUNCH_APPROVED_BY",
        "FREE_BETA_LAUNCH_APPROVED_AT",
        "ACCEPTANCE_EVIDENCE_SHA",
        "ACCEPTANCE_EVIDENCE_SUITE_VERSION",
    ],
)
def test_each_evidence_field_is_individually_required(field):
    gate = evaluate_release_gate(ready_free_beta(**{field: ""}))
    assert gate.free_beta_ready is False
    assert any(field in b for b in gate.blocking_ids)


@pytest.mark.parametrize("junk", ["TODO", "tbd", "changeme", "placeholder", "n/a", "-"])
def test_placeholder_values_are_rejected(junk):
    """임의 문자열 하나로 통과시키지 않는다."""
    gate = evaluate_release_gate(
        ready_free_beta(
            LEGAL_DOCUMENTS_VERSION=junk,
            FREE_BETA_LAUNCH_APPROVED_BY=junk,
            ACCEPTANCE_EVIDENCE_SHA=junk,
        )
    )
    assert gate.free_beta_ready is False
    assert any("placeholder" in b for b in gate.blocking_ids)


@pytest.mark.parametrize(
    "bad_sha",
    ["abc123", "0123456789ABCDEF0123456789ABCDEF01234567", "z" * 40, "0" * 39],
)
def test_evidence_sha_must_be_full_lowercase_hex(bad_sha):
    """짧거나 대문자거나 16진수가 아닌 값은 SHA로 인정하지 않는다."""
    gate = evaluate_release_gate(ready_free_beta(ACCEPTANCE_EVIDENCE_SHA=bad_sha))
    assert gate.free_beta_ready is False


@pytest.mark.parametrize("bad_version", ["v1", "2026", "2026-9-8", "latest"])
def test_policy_version_must_be_date_based(bad_version):
    gate = evaluate_release_gate(ready_free_beta(LEGAL_DOCUMENTS_VERSION=bad_version))
    assert gate.free_beta_ready is False


def test_complete_fixture_opens_the_gate():
    """모든 조건을 갖추면 열린다. 이 fixture는 합성값이며 실제 승인값이 아니다."""
    gate = evaluate_release_gate(ready_free_beta())
    assert gate.free_beta_ready is True
    assert gate.blocking_ids == []
    from core.release_gate import service_gate_reason

    assert service_gate_reason(ready_free_beta()) == ""


def test_next_safe_action_distinguishes_evidence_gap():
    """D는 다 표시됐는데 증거만 없는 상태를 따로 안내한다."""
    gate = evaluate_release_gate(
        FakeSettings(OPERATOR_ATTESTED_DECISIONS=attest(*FREE_BETA_REQUIRED_DECISIONS))
    )
    assert "증거" in gate.next_safe_action


# --- CYCLE-01-R3: 공개 설정 하위 호환 ---


def test_public_config_adds_free_beta_ready_without_removing_fields():
    """추가 필드이며 기존 필드는 그대로 유지된다."""
    payload = public_service_config(
        FakeSettings(), consultation_credit_cost=10, welcome_credits=50
    )
    assert payload["free_beta_ready"] is False
    for legacy in (
        "service_stage",
        "purchase_enabled",
        "generation_enabled",
        "consultation_credit_cost",
        "welcome_credits",
        "policy_documents_draft",
    ):
        assert legacy in payload

    opened = public_service_config(
        ready_free_beta(), consultation_credit_cost=10, welcome_credits=50
    )
    assert opened["free_beta_ready"] is True
    assert opened["policy_documents_draft"] is False


def test_kill_switch_meaning_is_unchanged():
    """게이트가 열려도 킬 스위치는 별개로 유지된다."""
    settings_obj = ready_free_beta(GENERATION_ENABLED=False)
    gate = evaluate_release_gate(settings_obj)
    # 킬 스위치는 게이트 판정에 영향을 주지 않는다.
    assert gate.free_beta_ready is True
    assert (
        public_service_config(
            settings_obj, consultation_credit_cost=10, welcome_credits=50
        )["generation_enabled"]
        is False
    )


# --- CYCLE-01-R4: D06 재분류와 증거 앵커 ---


def test_d06_is_required_for_free_beta():
    """무료 베타도 크레딧을 소비한다. 가입 50C, 1턴 10C가 이미 적용된다."""
    assert "D06" in FREE_BETA_REQUIRED_DECISIONS
    assert "D06" not in COMMERCIAL_EXTRA_DECISIONS

    without_d06 = [d for d in FREE_BETA_REQUIRED_DECISIONS if d != "D06"]
    gate = evaluate_release_gate(
        ready_free_beta(OPERATOR_ATTESTED_DECISIONS=attest(*without_d06))
    )
    assert gate.free_beta_ready is False
    assert "D06" in gate.blocking_ids


def test_d07_d09_remain_commercial_only():
    assert COMMERCIAL_EXTRA_DECISIONS == ("D07", "D08", "D09")


def test_format_valid_strings_without_manifest_do_not_open_gate():
    """핵심 회귀: 존재하지 않는 SHA와 문자열 필드만으로는 열리지 않는다.

    R3에서는 이 조합이 free_beta_ready=true를 만들었다.
    """
    gate = evaluate_release_gate(
        FakeSettings(
            OPERATOR_ATTESTED_DECISIONS=attest(*FREE_BETA_REQUIRED_DECISIONS),
            LEGAL_DOCUMENTS_VERSION="2026-09-08.1",
            LEGAL_DOCUMENTS_PUBLISHED=True,
            FREE_BETA_LAUNCH_APPROVED_BY="operator-under-test",
            FREE_BETA_LAUNCH_APPROVED_AT="2026-09-08",
            # 형식은 완벽하지만 실제로 존재하지 않는 커밋
            ACCEPTANCE_EVIDENCE_SHA="deadbeef" * 5,
            ACCEPTANCE_EVIDENCE_SUITE_VERSION=_TEST_SUITE,
            BUILD_GIT_SHA="deadbeef" * 5,
        )
    )
    assert gate.free_beta_ready is False
    assert any("manifest" in b.lower() or "MANIFEST" in b for b in gate.blocking_ids)


def test_manifest_missing_blocks_gate():
    gate = evaluate_release_gate(ready_free_beta(ACCEPTANCE_MANIFEST_PATH=""))
    assert gate.free_beta_ready is False


def _other_public_key_b64() -> str:
    other = Ed25519PrivateKey.generate()
    return base64.b64encode(
        other.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
    ).decode("ascii")


def test_public_key_env_is_a_no_op_in_both_directions():
    """`ACCEPTANCE_EVIDENCE_PUBLIC_KEY`를 바꿔도 판정이 달라지지 않는다.

    예전에는 이 값이 검증 공개키였다. 그래서 배포 환경변수를 바꿀 수 있는 사람은
    자기 키를 넣고 자기가 서명한 manifest를 함께 넣어 게이트를 열 수 있었다.
    이제 이 설정은 아무 것도 하지 않는다. 열지도 닫지도 못한다는 것을 양방향으로
    확인한다 — 한쪽만 보면 "우연히 닫혀 있는 것"과 구분되지 않는다.
    """
    baseline = evaluate_release_gate(ready_free_beta()).to_dict()

    for value in ("", _other_public_key_b64(), "not-base64!!", "A" * 44):
        gate = evaluate_release_gate(
            ready_free_beta(ACCEPTANCE_EVIDENCE_PUBLIC_KEY=value)
        ).to_dict()
        assert gate == baseline, f"공개키 env가 판정을 바꿨다: {value[:12]!r}"


def test_shipped_trust_registry_cannot_be_opened_by_settings_alone(monkeypatch):
    """제품 registry(비어 있음)에서는 완전한 자체서명 증거로도 열리지 않는다.

    이 파일은 게이트가 열린 뒤의 동작을 보려고 테스트 전용 anchor를 주입해 둔다.
    그 주입을 걷어내면 배포되는 상태와 같아진다. 그때는 검수자가 만든 임의 키로
    서명한 manifest와 모든 env를 완성해도 free_beta_ready가 false여야 한다.
    """
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())
    monkeypatch.setattr(
        release_evidence, "RELEASE_ELIGIBLE_SUITE_VERSIONS", frozenset()
    )

    gate = evaluate_release_gate(ready_free_beta())

    assert gate.free_beta_ready is False
    assert any(release_trust.NO_TRUST_ANCHOR_REASON == b for b in gate.blocking_ids)


def test_development_smoke_suite_cannot_open_free_beta(monkeypatch):
    """개발 통합 smoke는 이름이 유효해도 무료 베타를 열 자격이 없다."""
    monkeypatch.setattr(
        release_evidence, "RELEASE_ELIGIBLE_SUITE_VERSIONS", frozenset()
    )

    gate = evaluate_release_gate(ready_free_beta())

    assert gate.free_beta_ready is False
    assert any("출시 자격이 없는 suite_version" in b for b in gate.blocking_ids)


def test_build_sha_mismatch_blocks_gate():
    """증거가 다른 빌드의 것이면 열리지 않는다."""
    gate = evaluate_release_gate(ready_free_beta(BUILD_GIT_SHA="a" * 40))
    assert gate.free_beta_ready is False


def test_complete_signed_fixture_still_opens():
    """서명까지 갖춘 완전한 fixture만 열린다."""
    gate = evaluate_release_gate(ready_free_beta())
    assert gate.free_beta_ready is True
    assert gate.blocking_ids == []
