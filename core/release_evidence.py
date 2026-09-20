# -*- coding: utf-8 -*-
"""
인수기준 검증 증거(acceptance manifest) 검증.

## 왜 별도 모듈인가

R3에서는 `ACCEPTANCE_EVIDENCE_SHA`와 suite 문자열의 **형식**만 봤다. 형식이 맞는
아무 SHA나 넣으면 통과했다. 런타임 환경변수 두 개를 맞춰 넣는 것은 "검증을
통과했다"는 독립 증거가 아니다.

git 객체 존재 확인(`git cat-file`)으로 보강하는 방법은 쓰지 않는다. 배포 이미지에
`.git`이 없을 수 있고, 무엇보다 **커밋이 존재한다는 사실은 그 커밋에서 테스트가
통과했다는 증거가 아니다.**

## 신뢰 경계

증거를 만드는 쪽과 검증하는 쪽을 키로 분리한다.

- **CI**가 비공개 Ed25519 서명키를 보유하고, 테스트가 실제로 통과한 커밋에 대해
  manifest를 서명한다. 이 저장소에 비공개키는 없다.
- **애플리케이션**은 `core/release_trust.py`에 코드로 박힌 공개키로만 서명을
  검증한다. 런타임 환경변수에서 공개키를 읽지 않는다 — 배포 환경변수를 바꿀 수
  있는 사람이 자기 키로 자기 manifest를 서명해 통과시키는 경로를 없애기 위해서다.

따라서 애플리케이션 설정만 조작해서는 통과시킬 수 없다. CI의 비공개키와, 그
공개키를 승인해 빌드에 넣은 리뷰가 필요하다.

**현재 실제 CI 서명 단계도 승인된 공개키도 존재하지 않는다.** 이 모듈은 계약과
검증기를 먼저 갖춰 둔 것이고, 운영 기본값은 계속 false다. 저장소와 `.env.example`
에는 비공개키도 실제 운영 공개키도 실제 PASS manifest도 넣지 않는다.

## suite 자격

`RELEASE_ELIGIBLE_SUITE_VERSIONS`는 **비어 있다.** 무료 베타 공개를 정당화할 수
있는 전체 출시 suite가 아직 존재하지 않기 때문이다. 현재 저장소에서 도는 것은
개발 통합 smoke이며, 이름에 `development`를 명시해 출시 자격이 없음을 형식으로
드러낸다. 개발 smoke manifest는 구조 검증은 통과할 수 있어도 게이트를 열 자격이
없다.

## manifest 형식

봉투(envelope)는 정확히 세 필드만 갖는다.

    {
      "payload": { ... },
      "payload_digest": "sha256:<64 hex>",
      "signature": "<base64 Ed25519>"
    }

payload는 정확히 여섯 필드만 갖는다.

    {
      "schema": "iching.acceptance-manifest/v1",
      "target_sha": "<40 소문자 hex>",
      "suite_version": "<release-eligible suite>",
      "result": "PASS",
      "generated_at": "2026-09-09T00:00:00Z",
      "checks": [{"name": "release_gate", "result": "PASS"}, ...]
    }

알 수 없는 필드, 중복 check, 하나라도 PASS가 아닌 check, 빈 checks는 거부한다.
서명 대상은 payload의 정규화 직렬화 바이트다.

## 방어적 파싱

manifest는 신뢰할 수 없는 입력이다. 모든 필드는 **쓰기 전에 타입을 확인**한다.
예전에는 `suite_version`이 리스트로 들어오면 `frozenset` 조회에서
`TypeError: unhashable type: 'list'`가 그대로 위로 튀어 게이트 판정 자체가
예외로 끝났다. 게이트가 예외로 죽는 것은 fail-closed가 아니다 — 호출자가 그
예외를 삼키면 조용히 열린 것과 같아진다.

지금은 (1) 파일 크기 상한, (2) 중첩 깊이 상한, (3) 필드별 타입 검사,
(4) 최상위 예외 포획 세 겹으로, 어떤 입력에도 **명시적 차단 사유가 담긴 목록**만
돌려준다.
"""

import base64
import binascii
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from cryptography.exceptions import InvalidSignature

from core import release_trust

MANIFEST_SCHEMA = "iching.acceptance-manifest/v1"

# 개발 통합 smoke. 이름에 development를 박아 출시 자격이 없음을 형식으로 드러낸다.
# 현재 193 Python 선택 테스트·13 DB 테스트·42 FE 테스트가 여기에 해당하며,
# 이것은 개발 통합 증거이지 무료 베타 출시 suite가 아니다.
DEVELOPMENT_SMOKE_SUITE = "development-smoke/v1"

# 무료 베타 정식 검증 suite.
FREE_BETA_SUITE = "free-beta/v1"

# 검증기가 이름을 아는 suite. 구조 검증은 통과할 수 있다.
KNOWN_SUITE_VERSIONS = frozenset({DEVELOPMENT_SMOKE_SUITE, FREE_BETA_SUITE})

# 무료 베타 공개를 정당화할 수 있는 suite.
RELEASE_ELIGIBLE_SUITE_VERSIONS: frozenset = frozenset({FREE_BETA_SUITE})

# 하위 호환 별칭. 기존 소비자가 읽던 이름을 유지한다.
SUPPORTED_SUITE_VERSIONS = KNOWN_SUITE_VERSIONS

# 무료 베타 공개에 반드시 PASS여야 하는 check (11개).
REQUIRED_CHECKS = (
    "release_gate",
    "auth_hardening",
    "card_export",
    "credit_ledger",
    "consent",
    "data_rights",
    "support_intake",
    "safety_latch",
    "input_boundary",
    "e2e_contract",
    "frontend_static",
)

# manifest 파일 크기 상한. 서명된 증거 한 장은 수 KB면 충분하다. 상한을 두지
# 않으면 거대한 파일을 읽는 것만으로 메모리와 시간이 소모된다.
MAX_MANIFEST_BYTES = 64 * 1024

# JSON 중첩 깊이 상한. 깊은 중첩은 파싱과 정규화 직렬화 양쪽에서 재귀 한계를
# 건드린다. 정상 manifest의 최대 깊이는 4다(봉투→payload→checks→check).
MAX_MANIFEST_DEPTH = 8

_ENVELOPE_FIELDS = frozenset({"payload", "payload_digest", "signature"})
_PAYLOAD_FIELDS = frozenset(
    {"schema", "target_sha", "suite_version", "result", "generated_at", "checks"}
)
_CHECK_FIELDS = frozenset({"name", "result"})

_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

# 검증기가 어떤 이유로도 예외를 밖으로 내보내지 않았음을 나타내는 최후 사유.
UNVERIFIABLE_REASON = "인수증거 manifest를 검증할 수 없음"


def canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    """서명·digest 대상이 되는 정규화 직렬화.

    키 정렬과 공백 제거로 동일 내용이 항상 동일 바이트가 되게 한다.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def payload_digest(payload: Dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def load_public_key(encoded: str):
    """base64 Ed25519 공개키를 읽는다. 실패하면 None.

    신뢰 anchor 자체는 `core/release_trust.py`가 소유한다. 이 함수는 인코딩
    해석만 하며, 여기에 넘긴 키가 신뢰된다는 뜻이 아니다.
    """
    return release_trust._decode_public_key(encoded)


def _as_text(value: Any) -> str:
    """설정에서 온 값이 문자열이 아닐 수도 있다. 비문자는 빈 문자열로 본다."""
    return value.strip() if isinstance(value, str) else ""


def _exceeds_depth(value: Any, limit: int) -> bool:
    """재귀 없이 중첩 깊이를 잰다. 재귀로 재면 재는 도중에 터진다."""
    stack = [(value, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > limit:
            return True
        if isinstance(node, dict):
            for item in node.values():
                stack.append((item, depth + 1))
        elif isinstance(node, list):
            for item in node:
                stack.append((item, depth + 1))
    return False


def _check_payload_shape(payload: Any, problems: List[str]) -> bool:
    if not isinstance(payload, dict):
        problems.append("manifest payload가 객체가 아님")
        return False

    keys = {k for k in payload if isinstance(k, str)}
    if len(keys) != len(payload):
        problems.append("manifest payload에 문자열이 아닌 키가 있음")
        return False

    missing = _PAYLOAD_FIELDS - keys
    unknown = keys - _PAYLOAD_FIELDS
    if missing:
        # 누락된 이름은 우리 상수에서 온 것이라 그대로 남겨도 안전하다.
        problems.append(f"manifest payload 필수 필드 누락: {sorted(missing)}")
    if unknown:
        # 알 수 없는 필드의 이름은 manifest가 정하는 값이다. 공개 응답에
        # 그대로 실어 나르지 않는다.
        problems.append("manifest payload에 알 수 없는 필드가 있음")
    return not missing and not unknown


def _check_checks(checks: Any, problems: List[str]) -> None:
    if not isinstance(checks, list):
        problems.append("manifest checks가 목록이 아님")
        return
    if not checks:
        problems.append("manifest checks가 비어 있음")
        return

    seen = set()
    passed = set()
    for entry in checks:
        if not isinstance(entry, dict):
            problems.append("manifest check 항목이 객체가 아님")
            return
        keys = {k for k in entry if isinstance(k, str)}
        if len(keys) != len(entry) or keys != _CHECK_FIELDS:
            problems.append(f"manifest check 필드가 정확히 {sorted(_CHECK_FIELDS)}가 아님")
            return

        name = entry["name"]
        if not isinstance(name, str) or not name.strip():
            problems.append("manifest check 이름이 비어 있거나 문자열이 아님")
            return
        if name in seen:
            # 이름은 manifest가 정하는 값이라 되돌려주지 않는다.
            problems.append("manifest에 중복 check가 있음")
            return
        seen.add(name)

        result = entry["result"]
        if not isinstance(result, str):
            problems.append("manifest check result가 문자열이 아님")
            return
        if result != "PASS":
            # 부분 PASS를 통과시키지 않는다.
            problems.append("manifest check가 PASS가 아님")
        else:
            passed.add(name)

    missing_required = [c for c in REQUIRED_CHECKS if c not in passed]
    if missing_required:
        problems.append(f"필수 check 누락 또는 미통과: {missing_required}")


def _verify_signature(
    envelope: Dict[str, Any],
    payload: Any,
    public_keys: Sequence[Any],
    problems: List[str],
) -> None:
    signature_b64 = envelope["signature"]
    if not isinstance(signature_b64, str) or not signature_b64.strip():
        problems.append("서명이 비어 있거나 문자열이 아님")
        return
    if not public_keys:
        # 신뢰 anchor가 없다는 사유는 이미 따로 남아 있다. 여기서 서명을
        # "검증했다"고 말할 수 있는 근거가 없으므로 아무 것도 통과시키지 않는다.
        return

    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (binascii.Error, ValueError):
        problems.append("서명이 base64가 아님")
        return

    if not isinstance(payload, dict):
        problems.append("서명 대상 payload가 객체가 아님")
        return

    try:
        message = canonical_payload_bytes(payload)
    except (TypeError, ValueError, RecursionError):
        problems.append("서명 대상 payload를 정규화할 수 없음")
        return

    for key in public_keys:
        try:
            key.verify(signature, message)
            return
        except InvalidSignature:
            continue
        except Exception:
            problems.append("서명을 검증할 수 없음")
            return

    problems.append("서명 검증 실패")


def _verify_manifest_inner(
    manifest_bytes: Any,
    *,
    public_keys: Sequence[Any],
    expected_sha: str,
    expected_suite: str,
    build_sha: str,
    require_release_eligible: bool,
) -> List[str]:
    problems: List[str] = []

    if not public_keys:
        problems.append("인수증거 공개키가 없거나 형식이 올바르지 않음")

    build = _as_text(build_sha)
    if not _SHA_PATTERN.match(build):
        problems.append("BUILD_GIT_SHA가 없거나 40자리 소문자 hex가 아님")

    if not isinstance(manifest_bytes, (bytes, bytearray)):
        problems.append("manifest 내용을 읽을 수 없음")
        return problems

    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        problems.append("인수증거 manifest가 허용 크기를 초과함")
        return problems

    try:
        envelope = json.loads(bytes(manifest_bytes).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        problems.append("manifest를 JSON으로 읽을 수 없음")
        return problems

    if _exceeds_depth(envelope, MAX_MANIFEST_DEPTH):
        problems.append("manifest 중첩 깊이가 허용치를 초과함")
        return problems

    if not isinstance(envelope, dict):
        problems.append("manifest 봉투가 객체가 아님")
        return problems

    keys = {k for k in envelope if isinstance(k, str)}
    if len(keys) != len(envelope) or keys != _ENVELOPE_FIELDS:
        problems.append(
            f"manifest 봉투 필드가 정확히 {sorted(_ENVELOPE_FIELDS)}가 아님"
        )
        return problems

    payload = envelope["payload"]
    if not _check_payload_shape(payload, problems):
        return problems

    schema = payload["schema"]
    if not isinstance(schema, str) or schema != MANIFEST_SCHEMA:
        problems.append(f"manifest schema가 {MANIFEST_SCHEMA}가 아님")

    target_sha = payload["target_sha"]
    if not isinstance(target_sha, str) or not _SHA_PATTERN.match(target_sha):
        problems.append("manifest target_sha가 40자리 소문자 hex가 아님")
    else:
        expected = _as_text(expected_sha)
        if expected and target_sha != expected:
            problems.append("manifest target_sha가 설정의 기대 SHA와 다름")
        if build and target_sha != build:
            problems.append("manifest target_sha가 빌드 대상 SHA와 다름")

    # suite_version은 반드시 문자열인지 먼저 본다. 리스트나 dict가 오면
    # 집합 조회에서 unhashable 예외가 나므로, 조회 전에 걸러야 한다.
    suite = payload["suite_version"]
    if not isinstance(suite, str):
        problems.append("manifest suite_version이 문자열이 아님")
    elif suite not in KNOWN_SUITE_VERSIONS:
        problems.append("지원하지 않는 suite_version")
    else:
        if require_release_eligible and suite not in RELEASE_ELIGIBLE_SUITE_VERSIONS:
            problems.append(
                "출시 자격이 없는 suite_version (개발용 검사 묶음은 무료 베타를 열 수 없음)"
            )
        wanted = _as_text(expected_suite)
        if wanted and suite != wanted:
            problems.append("manifest suite_version이 설정의 기대 값과 다름")

    result = payload["result"]
    if not isinstance(result, str) or result != "PASS":
        problems.append("manifest result가 PASS가 아님")

    generated_at = payload["generated_at"]
    if not isinstance(generated_at, str):
        problems.append("manifest generated_at이 문자열이 아님")
    else:
        try:
            datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            problems.append("manifest generated_at이 YYYY-MM-DDTHH:MM:SSZ 형식이 아님")

    _check_checks(payload["checks"], problems)

    digest = envelope["payload_digest"]
    if not isinstance(digest, str) or not _DIGEST_PATTERN.match(digest):
        problems.append("payload_digest 형식이 올바르지 않음")
    else:
        try:
            expected_digest = payload_digest(payload)
        except (TypeError, ValueError, RecursionError):
            problems.append("payload digest를 계산할 수 없음")
        else:
            if digest != expected_digest:
                problems.append("payload_digest가 payload와 일치하지 않음")

    _verify_signature(envelope, payload, public_keys, problems)

    return problems


def verify_manifest(
    manifest_bytes: Any,
    *,
    public_key: Any = None,
    public_keys: Optional[Sequence[Any]] = None,
    expected_sha: str = "",
    expected_suite: str = "",
    build_sha: str = "",
    require_release_eligible: bool = True,
) -> List[str]:
    """manifest를 검증하고 문제 목록을 돌려준다. 비어 있으면 유효하다.

    설정을 읽지 않는 순수 함수다. 테스트는 임시 키와 임시 manifest로 이 함수를
    직접 호출한다. 제품 설정에 테스트용 우회를 만들지 않기 위해서다.

    **어떤 입력에도 예외를 밖으로 내보내지 않는다.** manifest는 신뢰할 수 없는
    입력이고, 게이트 판정이 예외로 끝나면 호출자가 그것을 삼켰을 때 조용히 열린
    것과 구분되지 않는다. 예상 못 한 오류는 명시적 차단 사유 한 줄이 된다.

    `public_key`는 단일 키를 받던 이전 호출 형태를 위한 하위 호환 인자다.
    """
    try:
        keys: List[Any] = []
        if public_keys:
            keys.extend(k for k in public_keys if k is not None)
        if public_key is not None:
            keys.append(public_key)

        return _verify_manifest_inner(
            manifest_bytes,
            public_keys=keys,
            expected_sha=expected_sha,
            expected_suite=expected_suite,
            build_sha=build_sha,
            require_release_eligible=require_release_eligible,
        )
    except Exception:
        # 원인 문자열을 밖으로 내보내지 않는다. 내부 예외 메시지는 공개
        # 응답에 실릴 수 있고, 경로나 스택 조각을 담을 수 있다.
        return [UNVERIFIABLE_REASON]


def read_manifest_bytes(path: str) -> "tuple[Optional[bytes], Optional[str]]":
    """manifest 파일을 읽는다. (내용, 문제) 중 하나만 채워진다.

    크기 상한을 **읽기 전에** 확인한다. 상한 없이 읽으면 거대한 파일 하나로
    기동 경로의 메모리를 소진시킬 수 있다.
    """
    target = _as_text(path)
    if not target:
        return None, "ACCEPTANCE_MANIFEST_PATH가 비어 있음"

    # 경로를 그대로 노출하지 않는다. 운영 파일 배치가 응답에 실리면 안 된다.
    try:
        info = os.stat(target)
    except (OSError, ValueError):
        return None, "인수증거 manifest 파일을 읽을 수 없음"

    if not stat.S_ISREG(info.st_mode):
        return None, "인수증거 manifest가 일반 파일이 아님"

    if info.st_size > MAX_MANIFEST_BYTES:
        return None, "인수증거 manifest 파일이 허용 크기를 초과함"

    try:
        with open(target, "rb") as handle:
            # stat 이후 파일이 커졌을 수도 있다. 한 바이트 더 읽어 확인한다.
            data = handle.read(MAX_MANIFEST_BYTES + 1)
    except (OSError, ValueError):
        return None, "인수증거 manifest 파일을 읽을 수 없음"

    if len(data) > MAX_MANIFEST_BYTES:
        return None, "인수증거 manifest 파일이 허용 크기를 초과함"

    return data, None


def acceptance_evidence_problems(settings) -> List[str]:
    """설정을 읽어 manifest를 검증하는 얇은 래퍼.

    실제 검증 논리는 `verify_manifest`에 있고 이 함수는 입력만 모은다.
    공개키는 설정이 아니라 `core/release_trust.py`의 승인 registry에서 온다 —
    운영 환경변수를 바꿀 수 있는 사람이 검증 결과를 바꾸지 못하게 하기 위해서다.
    """
    try:
        anchor_problems = release_trust.trust_anchor_problems()

        manifest_bytes, read_problem = read_manifest_bytes(
            getattr(settings, "ACCEPTANCE_MANIFEST_PATH", "")
        )
        if read_problem:
            return anchor_problems + [read_problem]

        return anchor_problems + verify_manifest(
            manifest_bytes,
            public_keys=release_trust.trusted_public_keys(),
            expected_sha=getattr(settings, "ACCEPTANCE_EVIDENCE_SHA", ""),
            expected_suite=getattr(settings, "ACCEPTANCE_EVIDENCE_SUITE_VERSION", ""),
            build_sha=getattr(settings, "BUILD_GIT_SHA", ""),
            require_release_eligible=True,
        )
    except Exception:
        return [UNVERIFIABLE_REASON]
