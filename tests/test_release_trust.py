"""신뢰 anchor registry 테스트 (CYCLE-03 T04-BE-GATE).

이 파일이 고정하는 성질은 하나다. **배포되는 코드로는 게이트를 열 수 없다.**

여기서 쓰는 검증 방식이 두 가지인 이유가 있다.

- 소스를 직접 읽는 **정적 검사.** 다른 테스트 모듈(tests/test_release_gate.py)이
  "게이트가 열린 뒤의 동작"을 보려고 테스트 프로세스 안에서 임시 anchor를
  주입한다. 그래서 런타임 값만 보면 실행 순서에 따라 답이 달라진다. 배포되는
  파일에 무엇이 적혀 있는지는 소스를 읽어야만 흔들리지 않게 확인할 수 있다.
- 명시적 `monkeypatch`로 registry를 비운 **동작 검사.** "우연히 비어 있어서
  닫혔다"가 아니라 "비어 있으면 반드시 닫힌다"를 확인한다.
"""

import ast
import json
import pathlib
from dataclasses import dataclass

import pytest

from core import release_evidence, release_trust
from core.release_gate import evaluate_release_gate, public_service_config

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_TRUST_SOURCE = _REPO_ROOT / "core" / "release_trust.py"
_EVIDENCE_SOURCE = _REPO_ROOT / "core" / "release_evidence.py"
_GATE_SOURCE = _REPO_ROOT / "core" / "release_gate.py"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

_PUBLIC_KEY_ENV = "ACCEPTANCE_EVIDENCE_PUBLIC_KEY"


def _module_assignment(path: pathlib.Path, name: str):
    """모듈 최상위 대입문의 우변을 AST로 꺼낸다. 런타임 패치에 영향받지 않는다."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
    raise AssertionError(f"{path.name}에 {name} 최상위 대입이 없다")


# --- 배포되는 registry는 비어 있다 (정적) ---------------------------------------


def test_shipped_trust_registry_contains_approved_operator_key():
    """운영자가 정식 승인한 Ed25519 공개키 1개만 소스에 등록되어 있어야 한다."""
    value = _module_assignment(_TRUST_SOURCE, "APPROVED_ACCEPTANCE_PUBLIC_KEYS")

    assert isinstance(value, ast.Tuple), "튜플 리터럴이어야 한다"
    assert len(value.elts) == 1, f"승인된 신뢰 anchor는 정확히 1개여야 한다 (현재: {len(value.elts)}개)"
    assert value.elts[0].value == "C+hW+gU3+8M66AhwfEzIrBOiS7iwKmyPmyNOsq0T4uM="


def test_shipped_release_eligible_suite_registry_contains_only_free_beta():
    """출시 자격이 있는 suite는 정식 승인된 free-beta/v1만 허용되어야 한다."""
    assert release_evidence.RELEASE_ELIGIBLE_SUITE_VERSIONS == frozenset(
        {release_evidence.FREE_BETA_SUITE}
    )


def test_importing_test_modules_does_not_mutate_runtime_release_registries():
    """테스트 수집만으로 제품의 닫힌 기본값이 열리면 증거가 순서 의존적이다."""
    assert release_trust.APPROVED_ACCEPTANCE_PUBLIC_KEYS == (
        "C+hW+gU3+8M66AhwfEzIrBOiS7iwKmyPmyNOsq0T4uM=",
    )
    assert release_evidence.RELEASE_ELIGIBLE_SUITE_VERSIONS == frozenset(
        {release_evidence.FREE_BETA_SUITE}
    )
    assert release_evidence.KNOWN_SUITE_VERSIONS == frozenset(
        {release_evidence.DEVELOPMENT_SMOKE_SUITE, release_evidence.FREE_BETA_SUITE}
    )


def test_development_smoke_suite_is_named_as_development():
    """개발용 묶음은 이름만 봐도 출시용이 아님을 알 수 있어야 한다."""
    assert "development" in release_evidence.DEVELOPMENT_SMOKE_SUITE
    assert release_evidence.DEVELOPMENT_SMOKE_SUITE in release_evidence.KNOWN_SUITE_VERSIONS


def test_retired_full_suite_name_is_not_declared_anywhere():
    """A01-A37/v1을 지원 목록으로 되살리지 않았는지 소스에서 확인한다.

    존재하지 않는 전체 출시 suite를 이름으로 선언해 두면, check 3개짜리
    manifest가 그 이름을 달고 통과할 수 있다.
    """
    evidence_source = _EVIDENCE_SOURCE.read_text(encoding="utf-8")
    known = _module_assignment(_EVIDENCE_SOURCE, "KNOWN_SUITE_VERSIONS")

    assert "A01-A37" not in ast.dump(known)
    # 문서 문자열에서 과거 이름을 설명하는 것은 괜찮지만, 상수로는 없어야 한다.
    assert '"A01-A37/v1"' not in evidence_source.replace('"A01-A37/v1"이', "")


# --- 제품 코드가 런타임 env를 읽지 않는다 (정적) ----------------------------------


def test_product_code_never_reads_the_public_key_env():
    """공개키를 런타임 설정에서 읽는 경로가 남아 있으면 안 된다.

    남아 있으면 배포 환경변수를 바꿀 수 있는 사람이 자기 키로 자기 manifest를
    서명해 통과시킬 수 있다.
    """
    for source in (_EVIDENCE_SOURCE, _GATE_SOURCE, _TRUST_SOURCE):
        text = source.read_text(encoding="utf-8")
        code_lines = [
            line
            for line in text.splitlines()
            if _PUBLIC_KEY_ENV in line and not line.strip().startswith("#")
        ]
        # 주석과 문서 문자열에서 "이제 읽지 않는다"고 설명하는 것은 허용한다.
        for line in code_lines:
            assert "getattr" not in line and "settings" not in line, (
                f"{source.name}에 공개키 런타임 조회가 남아 있다: {line.strip()}"
            )


def test_env_example_marks_the_public_key_as_deprecated():
    text = _ENV_EXAMPLE.read_text(encoding="utf-8")
    assert _PUBLIC_KEY_ENV in text
    index = text.index(_PUBLIC_KEY_ENV)
    preceding = text[:index]
    assert "DEPRECATED" in preceding or "no-op" in preceding


# --- registry가 비어 있으면 반드시 닫힌다 (동작) ----------------------------------


@pytest.fixture
def empty_registry(monkeypatch):
    """배포 상태와 같게 registry를 비운다. 실행 순서에 의존하지 않는다."""
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())
    monkeypatch.setattr(
        release_evidence, "RELEASE_ELIGIBLE_SUITE_VERSIONS", frozenset()
    )


def test_no_anchor_yields_an_explicit_blocking_reason(empty_registry):
    assert release_trust.trusted_public_keys() == []
    assert release_trust.trust_anchor_problems() == [
        release_trust.NO_TRUST_ANCHOR_REASON
    ]


def test_unreadable_anchor_is_reported_separately(monkeypatch):
    """등록은 됐는데 읽을 수 없는 키는 '없음'과 다른 사유로 남는다."""
    monkeypatch.setattr(
        release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ("not-a-key",)
    )
    problems = release_trust.trust_anchor_problems()

    assert problems
    assert release_trust.NO_TRUST_ANCHOR_REASON not in problems


@pytest.mark.parametrize("junk", ["", "   ", "!!!", "AAAA", "A" * 43, None, 123, []])
def test_malformed_anchor_material_never_raises(monkeypatch, junk):
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (junk,))

    assert release_trust.trusted_public_keys() == []
    assert release_trust.trust_anchor_problems()


# --- 게이트 전체 판정 -------------------------------------------------------------


@dataclass
class GateSettings:
    """게이트가 읽는 필드만 흉내 낸다. 모든 값이 형식상 완성돼 있다."""

    SERVICE_STAGE: str = "free_beta"
    PURCHASE_ENABLED: bool = False
    PAYMENT_PROVIDER: str = "mock"
    PAID_CREDIT_EXPIRY_ENABLED: bool = False
    GENERATION_ENABLED: bool = True
    LLM_PROVIDER: str = "gemini"
    LLM_ALLOWED_PROVIDERS: str = "gemini,ollama,lmstudio,anthropic"
    LLM_ALLOWED_REGIONS: str = "us-central1,us-east5"
    GEMINI_LOCATION: str = "us-central1"
    CLAUDE_LOCATION: str = "us-east5"
    OPERATOR_ATTESTED_DECISIONS: str = (
        "D01,D02,D03,D04,D05,D06,D10,D11,D12,D13"
    )
    LEGAL_DOCUMENTS_VERSION: str = "2026-09-09"
    LEGAL_DOCUMENTS_PUBLISHED: bool = True
    FREE_BETA_LAUNCH_APPROVED_BY: str = "operator-under-test"
    FREE_BETA_LAUNCH_APPROVED_AT: str = "2026-09-09"
    ACCEPTANCE_EVIDENCE_SHA: str = "0123456789abcdef0123456789abcdef01234567"
    ACCEPTANCE_EVIDENCE_SUITE_VERSION: str = "development-smoke/v1"
    ACCEPTANCE_MANIFEST_PATH: str = ""
    ACCEPTANCE_EVIDENCE_PUBLIC_KEY: str = ""
    BUILD_GIT_SHA: str = "0123456789abcdef0123456789abcdef01234567"


def _signed_manifest(tmp_path):
    """검수자가 만들 수 있는 가장 완전한 자체서명 증거."""
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    payload = {
        "schema": release_evidence.MANIFEST_SCHEMA,
        "target_sha": "0123456789abcdef0123456789abcdef01234567",
        "suite_version": "development-smoke/v1",
        "result": "PASS",
        "generated_at": "2026-09-09T00:00:00Z",
        "checks": [
            {"name": name, "result": "PASS"}
            for name in release_evidence.REQUIRED_CHECKS
        ],
    }
    envelope = {
        "payload": payload,
        "payload_digest": release_evidence.payload_digest(payload),
        "signature": base64.b64encode(
            key.sign(release_evidence.canonical_payload_bytes(payload))
        ).decode("ascii"),
    }
    path = tmp_path / "acceptance.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")

    public_b64 = base64.b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    return str(path), public_b64


def test_self_signed_evidence_with_every_env_complete_cannot_open_the_gate(
    tmp_path, empty_registry
):
    """카드가 요구한 핵심 확인.

    검수자가 임의 키를 만들고, 그 키로 완전한 manifest를 서명하고, 공개키를
    포함한 모든 환경변수를 완성해도 free_beta_ready는 false여야 한다.
    """
    manifest_path, public_b64 = _signed_manifest(tmp_path)
    settings = GateSettings(
        ACCEPTANCE_MANIFEST_PATH=manifest_path,
        ACCEPTANCE_EVIDENCE_PUBLIC_KEY=public_b64,
    )

    gate = evaluate_release_gate(settings)

    assert gate.free_beta_ready is False
    assert release_trust.NO_TRUST_ANCHOR_REASON in gate.blocking_ids


def test_default_and_completed_env_are_both_closed(tmp_path, empty_registry):
    """기본 env와 완성형 env 모두 닫혀 있어야 한다."""
    assert evaluate_release_gate(GateSettings(ACCEPTANCE_MANIFEST_PATH="")).free_beta_ready is False

    manifest_path, public_b64 = _signed_manifest(tmp_path)
    completed = GateSettings(
        ACCEPTANCE_MANIFEST_PATH=manifest_path,
        ACCEPTANCE_EVIDENCE_PUBLIC_KEY=public_b64,
    )
    assert evaluate_release_gate(completed).free_beta_ready is False


def test_public_responses_never_expose_key_path_or_signature(
    tmp_path, empty_registry
):
    """공개 응답에 키·manifest 경로·서명·내부 예외가 실리면 안 된다."""
    manifest_path, public_b64 = _signed_manifest(tmp_path)
    settings = GateSettings(
        ACCEPTANCE_MANIFEST_PATH=manifest_path,
        ACCEPTANCE_EVIDENCE_PUBLIC_KEY=public_b64,
    )

    gate_body = json.dumps(evaluate_release_gate(settings).to_dict(), ensure_ascii=False)
    config_body = json.dumps(
        public_service_config(settings, consultation_credit_cost=10, welcome_credits=50),
        ensure_ascii=False,
    )

    signature = json.loads(pathlib.Path(manifest_path).read_text())["signature"]

    for body in (gate_body, config_body):
        assert public_b64 not in body, "공개키가 응답에 실렸다"
        assert manifest_path not in body, "manifest 경로가 응답에 실렸다"
        assert str(tmp_path) not in body
        assert signature not in body, "서명이 응답에 실렸다"
        for leak in ("Traceback", "Error", "Exception", "asyncpg", "/private/"):
            assert leak not in body, f"내부 정보가 응답에 실렸다: {leak}"


def test_public_config_reports_draft_documents_while_the_gate_is_closed(
    empty_registry,
):
    """게이트가 닫혀 있으면 프런트에 초안 상태로 보여야 한다."""
    body = public_service_config(
        GateSettings(), consultation_credit_cost=10, welcome_credits=50
    )

    assert body["free_beta_ready"] is False
    assert body["policy_documents_draft"] is True
