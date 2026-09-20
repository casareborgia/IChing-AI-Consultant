#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-5 인수증거 manifest 생성기 (make_manifest.py).

suite 실행 결과(suite.json)와 target commit SHA, Ed25519 서명키를 받아
정규화 직렬화·digest·서명을 수행하여 acceptance-manifest.json을 생성한다.

필수 요건:
- 봉투 3필드, payload 6필드 엄격 준수
- canonical_payload_bytes()를 통한 정규화 직렬화
- Ed25519 서명 및 base64 인코딩
- 생성 즉시 verify_manifest()로 자체 역검증 통과 필수
"""

from __future__ import annotations

import argparse
import base64
import binascii
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.release_evidence import (
    FREE_BETA_SUITE,
    MANIFEST_SCHEMA,
    REQUIRED_CHECKS,
    canonical_payload_bytes,
    load_public_key,
    payload_digest,
    verify_manifest,
)


def _get_head_sha(repo_root: str) -> str:
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.strip().lower()


def load_private_key(raw_str: str) -> Ed25519PrivateKey:
    """raw base64 (32바이트) 또는 PEM/PKCS8 개인키를 로드한다."""
    raw_str = raw_str.strip()
    # 1. PEM/OpenSSH
    if "BEGIN" in raw_str:
        return serialization.load_pem_private_key(raw_str.encode("utf-8"), password=None)  # type: ignore

    # 2. base64 raw 32 bytes (권장 CI secret 형식)
    try:
        raw_bytes = base64.b64decode(raw_str, validate=True)
        if len(raw_bytes) == 32:
            return Ed25519PrivateKey.from_private_bytes(raw_bytes)
    except binascii.Error:
        pass

    # 3. 64-hex string
    if len(raw_str) == 64 and re.match(r"^[0-9a-fA-F]{64}$", raw_str):
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw_str))

    raise ValueError("지원하지 않는 Ed25519 비공개키 형식입니다. 32바이트 raw base64 또는 PEM이어야 합니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="I-Ching Acceptance Manifest Generator")
    parser.add_argument("--suite", default="suite.json", help="Path to suite execution json")
    parser.add_argument("--target-sha", default=None, help="Target git commit SHA (defaults to HEAD)")
    parser.add_argument("--key-env", default="ACCEPTANCE_SIGNING_KEY", help="Env var name containing Ed25519 private key")
    parser.add_argument("--key-file", default=None, help="File path containing Ed25519 private key")
    parser.add_argument("--out", default="acceptance-manifest.json", help="Output path for acceptance manifest")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    # 1. target_sha 결정 및 검증
    target_sha = args.target_sha or _get_head_sha(repo_root)
    target_sha = target_sha.strip().lower()
    if not re.match(r"^[0-9a-f]{40}$", target_sha):
        print(f"[MAKE-MANIFEST] ERROR: 잘못된 target_sha 형식: {target_sha}", file=sys.stderr)
        return 1

    # 2. suite.json 로드 및 검증
    if not os.path.isfile(args.suite):
        print(f"[MAKE-MANIFEST] ERROR: suite 파일을 찾을 수 없습니다: {args.suite}", file=sys.stderr)
        return 1

    with open(args.suite, "r", encoding="utf-8") as f:
        suite_data = json.load(f)

    if suite_data.get("result") != "PASS":
        print(f"[MAKE-MANIFEST] ERROR: suite 결과가 PASS가 아닙니다 ({suite_data.get('result')}). 서명을 거부합니다.", file=sys.stderr)
        return 1

    if suite_data.get("suite_version") != FREE_BETA_SUITE:
        print(f"[MAKE-MANIFEST] ERROR: 예상치 못한 suite_version: {suite_data.get('suite_version')}", file=sys.stderr)
        return 1

    checks = suite_data.get("checks", [])
    executed_names = {c.get("name") for c in checks if isinstance(c, dict)}
    required_set = set(REQUIRED_CHECKS)
    if executed_names != required_set:
        missing = required_set - executed_names
        extra = executed_names - required_set
        print(f"[MAKE-MANIFEST] ERROR: REQUIRED_CHECKS 불일치 (누락: {missing}, 초과: {extra})", file=sys.stderr)
        return 1

    for c in checks:
        if c.get("result") != "PASS":
            print(f"[MAKE-MANIFEST] ERROR: check '{c.get('name')}' 실패 ({c.get('result')}). 서명 거부.", file=sys.stderr)
            return 1

    # 3. 비공개키 로드
    key_material = None
    if args.key_file and os.path.isfile(args.key_file):
        with open(args.key_file, "r", encoding="utf-8") as kf:
            key_material = kf.read().strip()
    elif args.key_env and os.getenv(args.key_env):
        key_material = os.getenv(args.key_env, "").strip()

    if not key_material:
        print(f"[MAKE-MANIFEST] ERROR: 비공개키가 제공되지 않았습니다 (파일: {args.key_file}, 환경변수: {args.key_env}).", file=sys.stderr)
        return 1

    try:
        private_key = load_private_key(key_material)
    except Exception as e:
        print(f"[MAKE-MANIFEST] ERROR: 비공개키 파싱 실패: {e}", file=sys.stderr)
        return 1

    # 4. Canonical payload 구성
    # 정확히 6필드만 포함
    payload: Dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "target_sha": target_sha,
        "suite_version": FREE_BETA_SUITE,
        "result": "PASS",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": [{"name": name, "result": "PASS"} for name in REQUIRED_CHECKS],
    }

    canonical_bytes = canonical_payload_bytes(payload)
    digest_val = payload_digest(payload)

    # 5. Ed25519 서명
    signature_bytes = private_key.sign(canonical_bytes)
    signature_b64 = base64.b64encode(signature_bytes).decode("ascii")

    # 6. 봉투 구성 (정확히 3필드)
    envelope = {
        "payload": payload,
        "payload_digest": digest_val,
        "signature": signature_b64,
    }
    manifest_bytes = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")

    # 7. 자체 역검증 (공개키로 검증)
    raw_pub = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pub_b64 = base64.b64encode(raw_pub).decode("ascii")

    verify_problems = verify_manifest(
        manifest_bytes,
        public_key=load_public_key(pub_b64),
        build_sha=target_sha,
        expected_sha=target_sha,
        expected_suite=FREE_BETA_SUITE,
        require_release_eligible=True,
    )
    if verify_problems:
        print(f"[MAKE-MANIFEST] ERROR: 생성된 manifest가 자체 역검증에 실패했습니다: {verify_problems}", file=sys.stderr)
        return 1

    # 8. 파일 쓰기
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True) if os.path.dirname(out_path) else None
    with open(out_path, "wb") as f:
        f.write(manifest_bytes)

    print(f"[MAKE-MANIFEST] 성공: {out_path}")
    print(f"[MAKE-MANIFEST] target_sha: {target_sha}")
    print(f"[MAKE-MANIFEST] suite: {FREE_BETA_SUITE} ({len(REQUIRED_CHECKS)} checks)")
    print(f"[MAKE-MANIFEST] digest: {digest_val}")
    print(f"[MAKE-MANIFEST] 공개키 (base64): {pub_b64}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
