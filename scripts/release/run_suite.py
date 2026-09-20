#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P1-5 출시 검증 suite 실행기 (run_suite.py).

무료 베타 정식 검증 suite('free-beta/v1')의 11개 REQUIRED_CHECKS를 순차적으로 실행하고,
그 결과를 JSON 형식으로 출력한다.

체크 하나라도 실패하면 부분 PASS를 만들지 않고 즉시 exit(1)로 종료한다.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from core.release_evidence import FREE_BETA_SUITE, REQUIRED_CHECKS


def _run_cmd(cmd: List[str], cwd: str | None = None, env: Dict[str, str] | None = None) -> bool:
    print(f"\n[RUN-SUITE] 실행: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, env=env)
    return res.returncode == 0


def check_release_gate(repo_root: str) -> bool:
    return _run_cmd(
        [
            "uv", "run", "pytest",
            "tests/test_release_gate.py",
            "tests/test_release_evidence.py",
            "tests/test_release_trust.py",
        ],
        cwd=repo_root,
    )


def check_auth_hardening(repo_root: str) -> bool:
    return _run_cmd(
        [
            "uv", "run", "pytest",
            "tests/test_auth_hardening.py",
            "tests/test_jwt_auth.py",
        ],
        cwd=repo_root,
    )


def check_card_export(repo_root: str) -> bool:
    return _run_cmd(
        ["uv", "run", "pytest", "tests/test_card_export.py"],
        cwd=repo_root,
    )


def check_credit_ledger(repo_root: str) -> bool:
    return _run_cmd(
        [
            "uv", "run", "pytest",
            "tests/test_credit_api_unit.py",
            "tests/test_credit_operation_unit.py",
        ],
        cwd=repo_root,
    )


def check_consent(repo_root: str) -> bool:
    return _run_cmd(
        ["uv", "run", "pytest", "tests/test_consent.py"],
        cwd=repo_root,
    )


def check_data_rights(repo_root: str) -> bool:
    return _run_cmd(
        ["uv", "run", "pytest", "tests/test_records.py"],
        cwd=repo_root,
    )


def check_support_intake(repo_root: str) -> bool:
    return _run_cmd(
        ["uv", "run", "pytest", "tests/test_support.py"],
        cwd=repo_root,
    )


def check_safety_latch(repo_root: str) -> bool:
    return _run_cmd(
        ["uv", "run", "pytest", "tests/test_crisis_resources.py"],
        cwd=repo_root,
    )


def check_input_boundary(repo_root: str) -> bool:
    """A10 입력 및 경계 제약 정적/단위 검증."""
    code = (
        "from api.main import _MAX_BODY_SIZE; "
        "from tests.e2e.scenarios_a_items import MAX_BODY_SIZE, QUESTION_MAX_LENGTH; "
        "assert _MAX_BODY_SIZE == 1024 * 1024; "
        "assert MAX_BODY_SIZE == 1024 * 1024; "
        "assert QUESTION_MAX_LENGTH == 1000; "
        "print('input_boundary constraints verified')"
    )
    return _run_cmd(["uv", "run", "python", "-c", code], cwd=repo_root)


def check_e2e_contract(repo_root: str) -> bool:
    """A47 E2E 시나리오 전체 PASS 검증 (실제 폐기 DB 및 앱 기동)."""
    return _run_cmd(
        ["uv", "run", "python", "-m", "tests.e2e.run_harness"],
        cwd=repo_root,
    )


def check_frontend_static(repo_root: str) -> bool:
    """A18 프론트엔드 정적 검증 (린트 + 빌드)."""
    frontend_dir = os.path.join(repo_root, "frontend")
    lint_ok = _run_cmd(["npm", "run", "lint"], cwd=frontend_dir)
    if not lint_ok:
        return False
    env = os.environ.copy()
    env.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://mock.supabase.co")
    env.setdefault("NEXT_PUBLIC_SUPABASE_ANON_KEY", "mock-anon-key-for-ci-build")
    build_ok = _run_cmd(["npm", "run", "build"], cwd=frontend_dir, env=env)
    return build_ok


CHECK_RUNNERS: Dict[str, Callable[[str], bool]] = {
    "release_gate": check_release_gate,
    "auth_hardening": check_auth_hardening,
    "card_export": check_card_export,
    "credit_ledger": check_credit_ledger,
    "consent": check_consent,
    "data_rights": check_data_rights,
    "support_intake": check_support_intake,
    "safety_latch": check_safety_latch,
    "input_boundary": check_input_boundary,
    "e2e_contract": check_e2e_contract,
    "frontend_static": check_frontend_static,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="I-Ching Release Suite Runner")
    parser.add_argument("--out", default="suite.json", help="Output path for suite execution results")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    print(f"[RUN-SUITE] 시작: {FREE_BETA_SUITE}")
    print(f"[RUN-SUITE] 저장소: {repo_root}")
    print(f"[RUN-SUITE] 검증 대상 항목({len(REQUIRED_CHECKS)}개): {', '.join(REQUIRED_CHECKS)}")

    checks_results: List[Dict[str, str]] = []
    all_passed = True

    start_time = time.time()
    for name in REQUIRED_CHECKS:
        runner = CHECK_RUNNERS.get(name)
        if not runner:
            print(f"[RUN-SUITE] ERROR: 알려지지 않은 check runner: {name}", file=sys.stderr)
            all_passed = False
            checks_results.append({"name": name, "result": "FAIL"})
            break

        print(f"\n========================================================")
        print(f"[RUN-SUITE] Check 시작: {name}")
        print(f"========================================================")
        ok = runner(repo_root)
        if ok:
            print(f"[RUN-SUITE] Check 성공: {name} -> PASS")
            checks_results.append({"name": name, "result": "PASS"})
        else:
            print(f"[RUN-SUITE] Check 실패: {name} -> FAIL", file=sys.stderr)
            checks_results.append({"name": name, "result": "FAIL"})
            all_passed = False
            break

    elapsed = time.time() - start_time
    suite_result = "PASS" if all_passed and len(checks_results) == len(REQUIRED_CHECKS) else "FAIL"

    output_data = {
        "suite_version": FREE_BETA_SUITE,
        "result": suite_result,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "checks": checks_results,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True) if os.path.dirname(out_path) else None
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n========================================================")
    print(f"[RUN-SUITE] 최종 결과: {suite_result} (소요 시간: {round(elapsed, 2)}초)")
    print(f"[RUN-SUITE] 결과 저장: {out_path}")
    print(f"========================================================")

    if suite_result != "PASS":
        print("[RUN-SUITE] 하나 이상의 check가 실패하여 종료합니다.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
