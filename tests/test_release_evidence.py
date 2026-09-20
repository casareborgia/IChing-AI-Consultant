"""인수증거 manifest 검증 테스트 (T01-BE-R4).

여기서 쓰는 키는 테스트마다 새로 만드는 임시 Ed25519 키다. 실제 CI 서명키도
운영 공개키도 실제 PASS manifest도 저장소에 두지 않는다.

검증기는 설정을 읽지 않는 순수 함수(`verify_manifest`)라, 제품 설정에 테스트용
우회를 만들지 않고도 임시 키로 직접 호출할 수 있다.
"""

import base64
import copy
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core import release_evidence, release_trust
from core.release_evidence import (
    DEVELOPMENT_SMOKE_SUITE,
    MANIFEST_SCHEMA,
    MAX_MANIFEST_BYTES,
    REQUIRED_CHECKS,
    UNVERIFIABLE_REASON,
    read_manifest_bytes,
    acceptance_evidence_problems,
    canonical_payload_bytes,
    load_public_key,
    payload_digest,
    verify_manifest,
)

TARGET_SHA = "0123456789abcdef0123456789abcdef01234567"
# 구조 검증에 쓰는 suite. 이름이 알려져 있을 뿐 출시 자격은 없다.
SUITE = DEVELOPMENT_SMOKE_SUITE


@pytest.fixture
def signing_key():
    """테스트마다 새로 만드는 임시 키. 저장소에 남지 않는다."""
    return Ed25519PrivateKey.generate()


def public_key_b64(private_key) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def make_payload(**overrides) -> dict:
    payload = {
        "schema": MANIFEST_SCHEMA,
        "target_sha": TARGET_SHA,
        "suite_version": SUITE,
        "result": "PASS",
        "generated_at": "2026-09-09T00:00:00Z",
        "checks": [{"name": name, "result": "PASS"} for name in REQUIRED_CHECKS],
    }
    payload.update(overrides)
    return payload


def sign_envelope(private_key, payload: dict, *, break_signature=False) -> bytes:
    signature = private_key.sign(canonical_payload_bytes(payload))
    if break_signature:
        signature = bytes([signature[0] ^ 0xFF]) + signature[1:]
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    return json.dumps(envelope).encode("utf-8")


def verify(manifest_bytes, private_key, **overrides):
    """구조·서명 검증만 본다.

    `require_release_eligible=False`인 이유: 출시 자격이 있는 suite registry는
    비어 있고 이 파일에서 채우지 않는다. 여기서 확인하려는 것은 "형식과 서명이
    올바른가"이고, "출시를 열 자격이 있는가"는 별도 테스트가 따로 확인한다.
    """
    kwargs = dict(
        public_key=load_public_key(public_key_b64(private_key)),
        expected_sha=TARGET_SHA,
        expected_suite=SUITE,
        build_sha=TARGET_SHA,
        require_release_eligible=False,
    )
    kwargs.update(overrides)
    return verify_manifest(manifest_bytes, **kwargs)


# --- 정상 경로 ---


def test_fully_signed_manifest_passes(signing_key):
    """임시 키로 서명한 완전한 fixture만 통과한다."""
    assert verify(sign_envelope(signing_key, make_payload()), signing_key) == []


# --- 서명·키 ---


def test_missing_public_key_fails(signing_key):
    problems = verify(
        sign_envelope(signing_key, make_payload()), signing_key, public_key=None
    )
    assert any("공개키" in p for p in problems)


@pytest.mark.parametrize("junk", ["", "not-base64!!", base64.b64encode(b"short").decode()])
def test_invalid_public_key_is_rejected(junk):
    assert load_public_key(junk) is None


def test_forged_signature_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(), break_signature=True)
    assert any("서명" in p for p in verify(manifest, signing_key))


def test_signature_from_other_key_fails(signing_key):
    """다른 키로 서명하면 통과하지 못한다. 설정만으로는 만들 수 없다."""
    attacker = Ed25519PrivateKey.generate()
    manifest = sign_envelope(attacker, make_payload())
    assert any("서명 검증 실패" in p for p in verify(manifest, signing_key))


def test_unsigned_manifest_fails(signing_key):
    envelope = json.loads(sign_envelope(signing_key, make_payload()))
    envelope["signature"] = ""
    assert verify(json.dumps(envelope).encode(), signing_key) != []


# --- payload 변조 ---


def test_payload_tampering_breaks_digest_and_signature(signing_key):
    envelope = json.loads(sign_envelope(signing_key, make_payload()))
    envelope["payload"]["result"] = "PASS "  # 눈에 안 띄는 변조
    problems = verify(json.dumps(envelope).encode(), signing_key)
    assert any("payload_digest" in p for p in problems)
    assert any("서명 검증 실패" in p for p in problems)


def test_digest_recomputed_to_match_still_fails_signature(signing_key):
    """digest를 다시 계산해 맞춰도 서명이 막는다."""
    payload = make_payload(target_sha="f" * 40)
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": base64.b64encode(
            signing_key.sign(canonical_payload_bytes(make_payload()))
        ).decode("ascii"),
    }
    problems = verify(
        json.dumps(envelope).encode(), signing_key, expected_sha="f" * 40, build_sha="f" * 40
    )
    assert any("서명 검증 실패" in p for p in problems)


# --- SHA / suite 불일치 ---


def test_sha_mismatch_with_expected_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload())
    problems = verify(manifest, signing_key, expected_sha="a" * 40)
    assert any("기대 SHA와 다름" in p for p in problems)


def test_sha_mismatch_with_build_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload())
    problems = verify(manifest, signing_key, build_sha="b" * 40)
    assert any("빌드 대상 SHA와 다름" in p for p in problems)


def test_missing_build_sha_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload())
    problems = verify(manifest, signing_key, build_sha="")
    assert any("BUILD_GIT_SHA" in p for p in problems)


def test_unsupported_suite_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(suite_version="A01-A99/v9"))
    problems = verify(manifest, signing_key, expected_suite="A01-A99/v9")
    assert any("지원하지 않는 suite_version" in p for p in problems)
    # manifest가 정하는 값을 사유 문자열에 되돌려 싣지 않는다. blocking_ids는
    # 공개 응답으로 나간다.
    assert not any("A01-A99" in p for p in problems)


def test_retired_suite_name_is_no_longer_known(signing_key):
    """A01-A37/v1은 더 이상 알려진 suite가 아니다.

    존재하지 않는 전체 출시 suite를 이름만으로 SUPPORTED라고 선언해 두면,
    check 3개짜리 manifest가 그 이름을 달고 통과할 수 있었다.
    """
    manifest = sign_envelope(signing_key, make_payload(suite_version="A01-A37/v1"))
    problems = verify(manifest, signing_key, expected_suite="A01-A37/v1")
    assert any("지원하지 않는 suite_version" in p for p in problems)


def test_development_smoke_is_not_release_eligible(signing_key):
    """개발 smoke는 구조 검증은 통과해도 출시 자격이 없다."""
    manifest = sign_envelope(signing_key, make_payload(suite_version=SUITE))

    structural = verify(manifest, signing_key)
    assert structural == []

    release = verify(manifest, signing_key, require_release_eligible=True)
    assert any("출시 자격이 없는 suite_version" in p for p in release)


def test_development_suite_is_named_as_development():
    """개발용 묶음은 이름만 봐도 출시용이 아님을 알 수 있어야 한다.

    배포되는 registry가 비어 있다는 것은 tests/test_release_trust.py가 소스를
    직접 읽어 확인한다. 런타임 값으로 확인하면, 임시 anchor를 주입하는 다른
    테스트 모듈이 먼저 import됐는지에 따라 답이 달라진다.
    """
    assert "development" in DEVELOPMENT_SMOKE_SUITE
    assert DEVELOPMENT_SMOKE_SUITE in release_evidence.KNOWN_SUITE_VERSIONS


def test_suite_mismatch_with_expected_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload())
    problems = verify(manifest, signing_key, expected_suite="A01-A99/v9")
    assert any("suite_version이 설정의 기대 값과 다름" in p for p in problems)


# --- checks 목록 ---


def test_partial_pass_fails(signing_key):
    checks = [{"name": n, "result": "PASS"} for n in REQUIRED_CHECKS]
    checks[0]["result"] = "FAIL"
    manifest = sign_envelope(signing_key, make_payload(checks=checks))
    problems = verify(manifest, signing_key)
    assert any("PASS가 아님" in p for p in problems)


def test_missing_required_check_fails(signing_key):
    checks = [{"name": n, "result": "PASS"} for n in REQUIRED_CHECKS[1:]]
    manifest = sign_envelope(signing_key, make_payload(checks=checks))
    assert any("필수 check 누락" in p for p in verify(manifest, signing_key))


def test_duplicate_check_fails(signing_key):
    checks = [{"name": n, "result": "PASS"} for n in REQUIRED_CHECKS]
    checks.append({"name": REQUIRED_CHECKS[0], "result": "PASS"})
    manifest = sign_envelope(signing_key, make_payload(checks=checks))
    assert any("중복 check" in p for p in verify(manifest, signing_key))


def test_empty_checks_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(checks=[]))
    assert any("비어 있음" in p for p in verify(manifest, signing_key))


def test_check_with_unknown_field_fails(signing_key):
    checks = [{"name": n, "result": "PASS"} for n in REQUIRED_CHECKS]
    checks[0]["note"] = "extra"
    manifest = sign_envelope(signing_key, make_payload(checks=checks))
    assert any("check 필드가" in p for p in verify(manifest, signing_key))


# --- 형식·스키마 ---


def test_unknown_payload_field_fails(signing_key):
    payload = make_payload()
    payload["extra"] = 1
    manifest = sign_envelope(signing_key, payload)
    assert any("알 수 없는 필드" in p for p in verify(manifest, signing_key))


def test_unknown_envelope_field_fails(signing_key):
    envelope = json.loads(sign_envelope(signing_key, make_payload()))
    envelope["note"] = "x"
    problems = verify(json.dumps(envelope).encode(), signing_key)
    assert any("봉투 필드가" in p for p in problems)


def test_wrong_schema_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(schema="other/v1"))
    assert any("schema가" in p for p in verify(manifest, signing_key))


def test_result_not_pass_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(result="FAIL"))
    assert any("result가 PASS가 아님" in p for p in verify(manifest, signing_key))


def test_bad_timestamp_fails(signing_key):
    manifest = sign_envelope(signing_key, make_payload(generated_at="2026-09-09"))
    assert any("generated_at" in p for p in verify(manifest, signing_key))


def test_malformed_json_fails(signing_key):
    assert any("JSON으로 읽을 수 없음" in p for p in verify(b"{not json", signing_key))


# --- 설정 래퍼 ---


class FakeSettings:
    def __init__(self, **kwargs):
        self.ACCEPTANCE_MANIFEST_PATH = kwargs.get("ACCEPTANCE_MANIFEST_PATH", "")
        self.ACCEPTANCE_EVIDENCE_PUBLIC_KEY = kwargs.get("ACCEPTANCE_EVIDENCE_PUBLIC_KEY", "")
        self.ACCEPTANCE_EVIDENCE_SHA = kwargs.get("ACCEPTANCE_EVIDENCE_SHA", "")
        self.ACCEPTANCE_EVIDENCE_SUITE_VERSION = kwargs.get(
            "ACCEPTANCE_EVIDENCE_SUITE_VERSION", ""
        )
        self.BUILD_GIT_SHA = kwargs.get("BUILD_GIT_SHA", "")


def test_missing_manifest_path_fails():
    problems = acceptance_evidence_problems(FakeSettings())
    assert any("ACCEPTANCE_MANIFEST_PATH" in p for p in problems)


def test_unreadable_manifest_fails_without_leaking_path():
    problems = acceptance_evidence_problems(
        FakeSettings(ACCEPTANCE_MANIFEST_PATH="/nonexistent/secret-location/m.json")
    )
    assert problems
    assert not any("secret-location" in p for p in problems)


def _fully_completed_settings(manifest_path, signing_key) -> "FakeSettings":
    """검수자가 만들 수 있는 가장 완전한 상태. 모든 env가 채워져 있다."""
    return FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_path),
        ACCEPTANCE_EVIDENCE_PUBLIC_KEY=public_key_b64(signing_key),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION=SUITE,
        BUILD_GIT_SHA=TARGET_SHA,
    )


def test_self_signed_manifest_with_every_env_filled_still_fails(
    tmp_path, signing_key, monkeypatch
):
    """이 파일의 핵심 회귀.

    검수자가 임의의 Ed25519 키를 만들고, 그 키로 완전한 manifest를 서명하고,
    공개키를 포함한 모든 환경변수를 형식에 맞게 채워도 통과하지 못해야 한다.
    승인된 신뢰 anchor가 0개이기 때문이다.

    예전에는 이 조합이 정확히 통과했다. 공개키를 런타임 env에서 읽었으므로
    서명자와 검증자가 같은 사람이 될 수 있었다.
    """
    # 배포 상태와 같게 registry를 명시적으로 비운다. 다른 테스트 모듈이 임시
    # anchor를 주입해 두었을 수 있으므로 여기서 확정한다.
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())
    monkeypatch.setattr(
        release_evidence, "RELEASE_ELIGIBLE_SUITE_VERSIONS", frozenset()
    )

    manifest = tmp_path / "acceptance.json"
    manifest.write_bytes(sign_envelope(signing_key, make_payload()))

    problems = acceptance_evidence_problems(
        _fully_completed_settings(manifest, signing_key)
    )

    assert problems != []
    assert release_trust.NO_TRUST_ANCHOR_REASON in problems


def test_public_key_env_cannot_change_the_verdict(tmp_path, signing_key, monkeypatch):
    """공개키 env를 어떤 값으로 바꿔도 결과가 달라지지 않는다 (no-op)."""
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())
    manifest = tmp_path / "acceptance.json"
    manifest.write_bytes(sign_envelope(signing_key, make_payload()))

    correct = public_key_b64(signing_key)
    baseline = acceptance_evidence_problems(
        _fully_completed_settings(manifest, signing_key)
    )

    for value in ("", correct, public_key_b64(Ed25519PrivateKey.generate()), "junk"):
        settings = _fully_completed_settings(manifest, signing_key)
        settings.ACCEPTANCE_EVIDENCE_PUBLIC_KEY = value
        assert acceptance_evidence_problems(settings) == baseline


def test_wrapper_passes_only_when_an_approved_anchor_exists(
    tmp_path, signing_key, monkeypatch
):
    """anchor가 승인돼 있고 suite가 출시 자격을 가질 때에만 래퍼가 통과한다.

    이 테스트는 제품 registry를 바꾸지 않는다. monkeypatch로 "승인이 끝났다면"
    상태를 잠시 세워, 검증기 자체는 정상 동작한다는 것만 확인한다.
    """
    manifest = tmp_path / "acceptance.json"
    manifest.write_bytes(sign_envelope(signing_key, make_payload()))

    monkeypatch.setattr(
        release_trust,
        "APPROVED_ACCEPTANCE_PUBLIC_KEYS",
        (public_key_b64(signing_key),),
    )
    monkeypatch.setattr(
        release_evidence, "RELEASE_ELIGIBLE_SUITE_VERSIONS", frozenset({SUITE})
    )

    problems = acceptance_evidence_problems(
        _fully_completed_settings(manifest, signing_key)
    )
    assert problems == []


def test_settings_alone_cannot_pass_without_manifest():
    """핵심 회귀: 환경변수만 형식에 맞게 채워도 통과하지 못한다."""
    problems = acceptance_evidence_problems(
        FakeSettings(
            ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
            ACCEPTANCE_EVIDENCE_SUITE_VERSION=SUITE,
            BUILD_GIT_SHA=TARGET_SHA,
        )
    )
    assert problems != []


def test_canonical_bytes_are_stable():
    """키 순서가 달라도 서명 대상 바이트가 같아야 한다."""
    a = make_payload()
    b = dict(reversed(list(copy.deepcopy(a).items())))
    assert canonical_payload_bytes(a) == canonical_payload_bytes(b)


# --- 방어적 파싱: 어떤 malformed 입력에도 예외가 밖으로 나오지 않는다 -----------
#
# manifest는 신뢰할 수 없는 입력이다. 게이트 판정이 예외로 끝나면 fail-closed가
# 아니다 — 호출자가 그 예외를 삼키는 순간 조용히 열린 것과 구분되지 않는다.
# 아래는 모든 필드에 대해 "타입이 틀렸을 때"를 표로 훑는다.

# 필드에 넣어 볼 잘못된 값들. 어떤 것도 문자열이 아니다.
_WRONG_TYPES = (
    [],
    ["A01-A37/v1"],
    {},
    {"nested": "value"},
    0,
    1,
    -1,
    3.14,
    True,
    False,
    None,
)

_PAYLOAD_FIELD_NAMES = (
    "schema",
    "target_sha",
    "suite_version",
    "result",
    "generated_at",
    "checks",
)


def _problems_for_envelope(envelope) -> list:
    """서명 없이 봉투를 그대로 검증기에 넣는다. 예외가 나면 테스트가 실패한다."""
    raw = json.dumps(envelope).encode("utf-8")
    return verify_manifest(
        raw,
        public_key=None,
        expected_sha=TARGET_SHA,
        expected_suite=SUITE,
        build_sha=TARGET_SHA,
        require_release_eligible=False,
    )


@pytest.mark.parametrize("field", _PAYLOAD_FIELD_NAMES)
@pytest.mark.parametrize("value", _WRONG_TYPES)
def test_wrong_payload_field_type_never_raises(field, value):
    """payload 각 필드 × 잘못된 타입 조합. 예외 없이 차단 사유가 남아야 한다."""
    payload = make_payload(**{field: value})
    envelope = {
        "payload": payload,
        "payload_digest": "sha256:" + "0" * 64,
        "signature": "AAAA",
    }

    problems = _problems_for_envelope(envelope)

    assert problems, f"{field}={value!r}가 아무 사유 없이 통과했다"
    assert all(isinstance(p, str) and p for p in problems)


def test_suite_version_as_list_does_not_raise_unhashable():
    """회귀 고정: 예전에는 여기서 TypeError: unhashable type: 'list'가 났다.

    `suite not in frozenset(...)` 조회를 타입 검사 전에 했기 때문이다. 게이트
    판정 전체가 예외로 끝났다.
    """
    payload = make_payload(suite_version=[])
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": "AAAA",
    }

    problems = _problems_for_envelope(envelope)

    assert any("suite_version이 문자열이 아님" in p for p in problems)
    assert UNVERIFIABLE_REASON not in problems, "표면적 예외 포획에 기대면 안 된다"


@pytest.mark.parametrize("value", _WRONG_TYPES)
def test_wrong_envelope_field_type_never_raises(value):
    for field in ("payload", "payload_digest", "signature"):
        envelope = {
            "payload": make_payload(),
            "payload_digest": payload_digest(make_payload()),
            "signature": "AAAA",
        }
        envelope[field] = value
        assert _problems_for_envelope(envelope)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"   ",
        b"null",
        b"[]",
        b"[1,2,3]",
        b'"a string"',
        b"123",
        b"true",
        b"{",
        b"{}",
        b'{"payload": {}}',
        b"\xff\xfe\x00 not utf-8",
        "정상적인 UTF-8이지만 JSON은 아님".encode("utf-8"),
    ],
)
def test_non_object_or_broken_manifest_never_raises(raw):
    problems = verify_manifest(
        raw,
        public_key=None,
        expected_sha=TARGET_SHA,
        expected_suite=SUITE,
        build_sha=TARGET_SHA,
    )
    assert problems


@pytest.mark.parametrize("raw", ["not bytes", None, 123, [], {}])
def test_non_bytes_manifest_never_raises(raw):
    assert verify_manifest(raw, public_key=None, build_sha=TARGET_SHA)


def _nested_manifest_bytes(depth: int) -> bytes:
    """중첩이 깊은 manifest를 **바이트로** 만든다.

    파이썬 객체로 만들어 json.dumps 하면 테스트 쪽이 먼저 터진다. 실제 입력
    경로는 파일에서 읽은 바이트이므로 그대로 흉내낸다.
    """
    inner = b'{"n":' * depth + b"{}" + b"}" * depth
    return (
        b'{"payload":' + inner + b','
        b'"payload_digest":"sha256:' + b"0" * 64 + b'",'
        b'"signature":"AAAA"}'
    )


def _verify_raw(raw: bytes) -> list:
    return verify_manifest(
        raw,
        public_key=None,
        expected_sha=TARGET_SHA,
        expected_suite=SUITE,
        build_sha=TARGET_SHA,
        require_release_eligible=False,
    )


def test_moderately_nested_manifest_is_rejected_by_the_depth_limit():
    """파싱은 되지만 허용 깊이를 넘는 경우, 깊이 상한이 명시적으로 잡는다."""
    problems = _verify_raw(_nested_manifest_bytes(40))

    assert problems
    assert any("중첩" in p for p in problems)


def test_extremely_nested_manifest_never_raises_recursion_error():
    """파서 자체가 재귀 한계를 넘는 깊이에서도 예외가 밖으로 나오지 않는다."""
    problems = _verify_raw(_nested_manifest_bytes(20000))

    assert problems
    assert all(isinstance(p, str) and p for p in problems)


def test_duplicate_check_names_are_reported_without_echoing_the_name():
    checks = [{"name": n, "result": "PASS"} for n in REQUIRED_CHECKS]
    checks.append({"name": REQUIRED_CHECKS[0], "result": "PASS"})
    payload = make_payload(checks=checks)
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": "AAAA",
    }
    problems = _problems_for_envelope(envelope)
    assert any("중복 check" in p for p in problems)


@pytest.mark.parametrize(
    "checks",
    [
        [[]],
        [None],
        ["release_gate"],
        [{"name": [], "result": "PASS"}],
        [{"name": "release_gate", "result": []}],
        [{"name": "release_gate", "result": None}],
        [{"name": "", "result": "PASS"}],
        [{"name": "release_gate"}],
        [{"result": "PASS"}],
        [{"name": "release_gate", "result": "PASS", "extra": 1}],
    ],
)
def test_malformed_check_entries_never_raise(checks):
    payload = make_payload(checks=checks)
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": "AAAA",
    }
    assert _problems_for_envelope(envelope)


@pytest.mark.parametrize(
    "signature",
    ["", "   ", "not base64!!!", "AAAA", "=====", "A" * 10000],
)
def test_malformed_signature_never_raises(signing_key, signature):
    payload = make_payload()
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": signature,
    }
    raw = json.dumps(envelope).encode("utf-8")
    problems = verify_manifest(
        raw,
        public_key=load_public_key(public_key_b64(signing_key)),
        expected_sha=TARGET_SHA,
        expected_suite=SUITE,
        build_sha=TARGET_SHA,
        require_release_eligible=False,
    )
    assert problems


@pytest.mark.parametrize(
    "generated_at",
    [
        "2026-09-09",
        "2026-13-45T99:99:99Z",
        "not a date",
        "2026-09-09T00:00:00+09:00",
        "",
        "0000-00-00T00:00:00Z",
    ],
)
def test_malformed_timestamp_never_raises(generated_at):
    payload = make_payload(generated_at=generated_at)
    envelope = {
        "payload": payload,
        "payload_digest": payload_digest(payload),
        "signature": "AAAA",
    }
    problems = _problems_for_envelope(envelope)
    assert any("generated_at" in p for p in problems)


# --- 파일 크기 상한 ------------------------------------------------------------


def test_oversized_manifest_is_refused_before_parsing(tmp_path):
    """상한을 넘는 파일은 읽거나 파싱하기 전에 거부한다."""
    big = tmp_path / "big.json"
    big.write_bytes(b"{" + b" " * (MAX_MANIFEST_BYTES + 10) + b"}")

    content, problem = read_manifest_bytes(str(big))

    assert content is None
    assert problem is not None
    assert "크기" in problem


def test_manifest_at_the_limit_is_still_read(tmp_path):
    ok = tmp_path / "ok.json"
    ok.write_bytes(b"x" * MAX_MANIFEST_BYTES)

    content, problem = read_manifest_bytes(str(ok))

    assert problem is None
    assert content is not None and len(content) == MAX_MANIFEST_BYTES


def test_directory_path_is_refused_without_leaking_it(tmp_path):
    content, problem = read_manifest_bytes(str(tmp_path))
    assert content is None
    assert problem and tmp_path.name not in problem


def test_verify_rejects_oversized_bytes_directly():
    problems = verify_manifest(
        b"x" * (MAX_MANIFEST_BYTES + 1), public_key=None, build_sha=TARGET_SHA
    )
    assert any("크기" in p for p in problems)


# --- 공개 응답에 내부 정보를 싣지 않는다 -------------------------------------------


def test_blocking_reasons_never_echo_manifest_controlled_values():
    """차단 사유는 공개 응답(blocking_ids)으로 나간다.

    manifest가 정하는 문자열을 그대로 되돌려 실으면, 증거 파일을 놓을 수 있는
    사람이 공개 엔드포인트의 출력에 임의 문자열을 넣을 수 있다.
    """
    marker = "SENTINEL-SHOULD-NOT-APPEAR"
    payload = make_payload(
        suite_version=marker,
        schema=marker,
        checks=[{"name": marker, "result": marker}],
    )
    payload[marker] = marker
    envelope = {
        "payload": payload,
        "payload_digest": marker,
        "signature": marker,
        marker: marker,
    }

    problems = _problems_for_envelope(envelope)

    assert problems
    assert not any(marker in p for p in problems)


def test_unreadable_manifest_reason_has_no_path_fragment():
    problems = acceptance_evidence_problems(
        FakeSettings(ACCEPTANCE_MANIFEST_PATH="/srv/secret-location/evidence/m.json")
    )
    assert problems
    assert not any("secret-location" in p or "/srv" in p for p in problems)


# ==============================================================================
# P5-G: 출시 게이트 10대 반증 테스트 (P1-5 산출물)
# ==============================================================================


def test_p5_g_01_unsigned_manifest_is_blocked(tmp_path):
    """[P5-G 1] 서명 없는 manifest는 차단된다."""
    manifest_file = tmp_path / "unsigned.json"
    payload = make_payload(suite_version="free-beta/v1")
    # signature 누락
    envelope = {"payload": payload, "payload_digest": payload_digest(payload)}
    manifest_file.write_text(json.dumps(envelope), encoding="utf-8")

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "서명 없는 manifest는 반드시 차단되어야 한다"


def test_p5_g_02_unapproved_key_signature_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 2] 승인되지 않은 키로 서명한 manifest는 차단된다."""
    manifest_file = tmp_path / "unapproved_key.json"
    payload = make_payload(suite_version="free-beta/v1")
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    # APPROVED_ACCEPTANCE_PUBLIC_KEYS에 포함되지 않은 키
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "미승인 키 서명은 반드시 차단되어야 한다"


def test_p5_g_03_development_smoke_suite_is_blocked_for_release(tmp_path, signing_key, monkeypatch):
    """[P5-G 3] suite_version='development-smoke/v1'은 출시 자격이 없어 차단된다."""
    manifest_file = tmp_path / "dev_smoke.json"
    payload = make_payload(suite_version="development-smoke/v1")
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="development-smoke/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "development-smoke는 출시 자격이 없으므로 차단되어야 한다"


def test_p5_g_04_target_sha_mismatch_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 4] target_sha가 BUILD_GIT_SHA와 다르면 차단된다."""
    manifest_file = tmp_path / "sha_mismatch.json"
    payload = make_payload(target_sha=TARGET_SHA, suite_version="free-beta/v1")
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    different_build_sha = "ffffffffffffffffffffffffffffffffffffffff"
    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=different_build_sha,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "target_sha != BUILD_GIT_SHA 불일치는 차단되어야 한다"


def test_p5_g_05_failed_check_in_manifest_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 5] check 중 하나라도 FAIL이면 차단된다."""
    manifest_file = tmp_path / "check_failed.json"
    checks = [{"name": name, "result": "PASS"} for name in REQUIRED_CHECKS]
    checks[0]["result"] = "FAIL"  # 하나를 FAIL로 조작
    payload = make_payload(suite_version="free-beta/v1", checks=checks)
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "FAIL인 check가 포함된 manifest는 차단되어야 한다"


def test_p5_g_06_missing_required_check_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 6] REQUIRED_CHECKS 중 하나라도 누락되면 차단된다."""
    manifest_file = tmp_path / "missing_check.json"
    # REQUIRED_CHECKS 중 마지막 하나 누락
    checks = [{"name": name, "result": "PASS"} for name in REQUIRED_CHECKS[:-1]]
    payload = make_payload(suite_version="free-beta/v1", checks=checks)
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "필수 check 누락 manifest는 차단되어야 한다"


def test_p5_g_07_tampered_payload_digest_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 7] payload는 그대로 두고 payload_digest만 조작 시 차단된다."""
    manifest_file = tmp_path / "bad_digest.json"
    payload = make_payload(suite_version="free-beta/v1")
    sig_bytes = signing_key.sign(canonical_payload_bytes(payload))
    bad_digest = "sha256:" + "0" * 64
    envelope = {
        "payload": payload,
        "payload_digest": bad_digest,
        "signature": base64.b64encode(sig_bytes).decode("ascii"),
    }
    manifest_file.write_text(json.dumps(envelope), encoding="utf-8")

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "조작된 digest는 차단되어야 한다"


def test_p5_g_08_tampered_payload_content_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 8] payload 한 글자 변조 시 (서명 유지) 차단된다."""
    manifest_file = tmp_path / "tampered_payload.json"
    payload = make_payload(suite_version="free-beta/v1")
    # 원본 payload로 서명
    sig_bytes = signing_key.sign(canonical_payload_bytes(payload))
    # payload 내용 변조
    tampered_payload = copy.deepcopy(payload)
    tampered_payload["generated_at"] = "2026-09-12T00:00:01Z"

    envelope = {
        "payload": tampered_payload,
        "payload_digest": payload_digest(tampered_payload),
        "signature": base64.b64encode(sig_bytes).decode("ascii"),
    }
    manifest_file.write_text(json.dumps(envelope), encoding="utf-8")

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "서명 후 변조된 payload는 서명 검증에서 차단되어야 한다"


def test_p5_g_09_empty_approved_keys_tuple_is_blocked(tmp_path, signing_key, monkeypatch):
    """[P5-G 9] APPROVED_ACCEPTANCE_PUBLIC_KEYS가 빈 튜플이면 차단된다."""
    manifest_file = tmp_path / "valid_manifest.json"
    payload = make_payload(suite_version="free-beta/v1")
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    # 신뢰 anchor가 0개
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", ())

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems, "신뢰 공개키 0개인 상태는 차단되어야 한다"


def test_p5_g_10_valid_manifest_and_valid_settings_opens(tmp_path, signing_key, monkeypatch):
    """[P5-G 10] 정당한 manifest + 승인된 공개키 + 일치하는 설정 -> 통과(열림)."""
    manifest_file = tmp_path / "valid_manifest.json"
    payload = make_payload(suite_version="free-beta/v1")
    manifest_file.write_bytes(sign_envelope(signing_key, payload))

    pub_b64 = public_key_b64(signing_key)
    monkeypatch.setattr(release_trust, "APPROVED_ACCEPTANCE_PUBLIC_KEYS", (pub_b64,))

    settings = FakeSettings(
        ACCEPTANCE_MANIFEST_PATH=str(manifest_file),
        ACCEPTANCE_EVIDENCE_SHA=TARGET_SHA,
        ACCEPTANCE_EVIDENCE_SUITE_VERSION="free-beta/v1",
        BUILD_GIT_SHA=TARGET_SHA,
    )
    problems = acceptance_evidence_problems(settings)
    assert problems == [], f"정상 manifest와 승인키는 열려야 한다. 차단 사유: {problems}"

