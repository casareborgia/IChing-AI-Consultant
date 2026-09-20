# -*- coding: utf-8 -*-
"""CYCLE-06 E2E 하네스 실행기.

    python -m tests.e2e.run_harness --out artifacts/e2e

하는 일의 순서는 고정되어 있다.

1. 안전 가드: 원격 DB·운영 URL이면 연결 전에 중단한다.
2. 폐기 PostgreSQL 컨테이너를 새로 띄우고 marker를 심는다.
3. 제품 모델 metadata로 스키마를 만든다 (Supabase migration 재적용 아님).
4. 제품 FastAPI 앱을 고유 loopback 포트에 올린다.
5. 시나리오를 돌리고 기계 판독 JSON을 쓴다.
6. 이 실행이 만든 컨테이너만 지운다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.e2e.harness import disposable_db, ports, safety, tokens  # noqa: E402


def current_sha() -> str:
    probe = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=False,
    )
    return probe.stdout.strip() or "unknown"


def working_tree_dirty() -> bool:
    probe = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=False,
    )
    return bool(probe.stdout.strip())


def default_out_dir() -> str:
    """저장소 **바깥**에 둔다. 산출물이 git에 들어갈 경로를 기본값으로 쓰지 않는다."""
    base = os.environ.get("TMPDIR") or "/tmp"
    return os.path.join(base, "iching-e2e-cycle06")


def parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CYCLE-06 E2E 하네스")
    parser.add_argument(
        "--out", default=default_out_dir(),
        help="산출물 디렉터리. 기본값은 저장소 바깥의 임시 디렉터리다 — "
             "로그·토큰·dump가 실수로도 커밋되지 않게 하기 위해서다.",
    )
    parser.add_argument(
        "--with-frontend", action="store_true",
        help="시나리오 뒤에 프런트엔드를 띄우고 브라우저 검증을 기다린다",
    )
    parser.add_argument(
        "--keep-db", action="store_true",
        help="종료 후에도 폐기 DB 컨테이너를 남긴다 (기본은 삭제)",
    )
    parser.add_argument(
        "--supabase-url", default="",
        help="브라우저 모드에서 실제 OAuth를 쓸 때의 프로젝트 URL (JWKS 읽기 전용)",
    )
    parser.add_argument("--supabase-anon-key", default="")
    return parser.parse_args(argv)


async def run_scenarios(*, base_url: str, issuer: str, secret: str, report, app) -> None:
    import httpx

    from tests.e2e import scenarios

    async with httpx.AsyncClient(base_url=base_url) as client:
        context = scenarios.Context(
            client=client, report=report, issuer=issuer, secret=secret
        )
        await scenarios.run_all(context, app=app)


def start_frontend(*, port: int, backend_base_url: str, supabase_url: str,
                   supabase_anon_key: str) -> Optional[subprocess.Popen]:
    """Next.js 개발 서버를 고유 포트에 띄운다. 사용자 프로세스는 건드리지 않는다."""
    frontend_dir = os.path.join(REPO_ROOT, "frontend")
    if not os.path.isdir(os.path.join(frontend_dir, "node_modules")):
        print("[E2E] frontend/node_modules가 없어 프런트엔드를 띄우지 않습니다.")
        return None
    if not supabase_url or not supabase_anon_key:
        print("[E2E] Supabase URL/anon key가 없어 프런트엔드를 띄우지 않습니다.")
        return None

    from tests.e2e.harness import testapp

    env = testapp.frontend_env(
        backend_base_url=backend_base_url,
        supabase_url=supabase_url,
        supabase_anon_key=supabase_anon_key,
    )
    return subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=frontend_dir, env=env,
    )


def main(argv) -> int:
    args = parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    run_sha = current_sha()

    # 1. docker 가용성 --------------------------------------------------
    blocked = disposable_db.docker_available()
    if blocked:
        print(json.dumps({
            "schema": "iching.e2e-harness-report/v1",
            "run_sha": run_sha,
            "verdict": "BLOCKED",
            "blocked_reason": blocked,
            "remediation": "docker를 켜거나 {0} 이미지를 받은 뒤 다시 실행한다. "
                           "원격 Supabase로 대체하지 않는다.".format(disposable_db.IMAGE),
        }, ensure_ascii=False, indent=2))
        return 3

    restore_url = disposable_db.env_override_url()
    database = None
    db_kind = "disposable"

    if restore_url:
        # 운영자가 승인한 임시 복원본. 이름·호스트·marker 검사는 똑같이 건다.
        db_kind = "restore"
        database_url = restore_url
    else:
        db_port = ports.find_free_port(15432)
        database = disposable_db.start(db_port)
        database_url = database.async_url

    safety.assert_safe_or_die(safety.database_url_problems(database_url), "DATABASE_URL")

    backend_port = ports.find_free_port(18000)
    frontend_port = ports.find_free_port(backend_port + 1)

    browser_mode = bool(args.with_frontend and args.supabase_url)
    supabase_url = args.supabase_url.strip() if browser_mode else \
        "http://127.0.0.1:{0}".format(backend_port)
    safety.assert_safe_or_die(
        safety.supabase_url_problems(supabase_url, allow_remote_jwks=browser_mode),
        "SUPABASE_URL",
    )

    jwt_secret = tokens.new_secret()
    frontend_origin = "http://127.0.0.1:{0}".format(frontend_port)

    # 2. 제품 설정 모듈을 import하기 전에 환경을 확정한다 ------------------
    from tests.e2e.harness import testapp

    testapp.apply_environment(
        database_url=database_url,
        supabase_url=supabase_url,
        jwt_secret=jwt_secret,
        cors_origins=",".join([
            frontend_origin,
            "http://localhost:{0}".format(frontend_port),
        ]),
    )

    from tests.e2e.harness.recorder import Report

    report = Report(run_sha=run_sha)
    report.environment = {
        "repo_root": "[REPO_ROOT]",
        "run_sha": run_sha,
        "working_tree_dirty": working_tree_dirty(),
        "backend_url": "http://127.0.0.1:{0}".format(backend_port),
        "frontend_url": frontend_origin if args.with_frontend else None,
        "database_kind": db_kind,
        "database_url": database.redacted_url if database else "[REDACTED_RESTORE_URL]",
        "database_container": database.container_name if database else None,
        "database_marker": safety.DATABASE_MARKER,
        "llm_kind": "deterministic_fake",
        "llm_external_calls": 0,
        "token_issuer_kind": "remote_supabase_jwks" if browser_mode else "local_test_issuer",
        "jwt_algorithm": "HS256" if not browser_mode else "ES256(browser)/HS256(api)",
        "jwt_secret": "[REDACTED]",
        "service_gate": "S01은 제품 기본값(fail-closed), S02 이후는 테스트 override",
        "reserved_ports_untouched": sorted(ports.RESERVED_PORTS),
    }

    engine = testapp.build_engine_for_schema(database_url)
    server = None
    frontend_process = None
    exit_code = 0

    try:
        asyncio.get_event_loop().run_until_complete(
            disposable_db.prepare_schema(engine)
        )
        asyncio.get_event_loop().run_until_complete(
            disposable_db.verify_marker(engine)
        )

        app = testapp.build_app(install_fake_pipeline=True)
        server = testapp.start_server(app, backend_port)

        issuer = tokens.issuer_for(supabase_url)
        asyncio.get_event_loop().run_until_complete(
            run_scenarios(
                base_url=server.base_url, issuer=issuer, secret=jwt_secret,
                report=report, app=app,
            )
        )

        if args.with_frontend:
            frontend_process = start_frontend(
                port=frontend_port,
                backend_base_url=server.base_url,
                supabase_url=args.supabase_url,
                supabase_anon_key=args.supabase_anon_key,
            )

    except Exception as exc:  # noqa: BLE001
        report.notes.append("하네스 실행 중 예외: {0}".format(type(exc).__name__))
        exit_code = 2
    finally:
        report.artifacts = {
            "report_json": os.path.join(args.out, "cycle06-e2e-report.json"),
            "browser_console_log": os.path.join(args.out, "browser-console.json"),
            "browser_network_log": os.path.join(args.out, "browser-network.json"),
            "browser_screenshots": os.path.join(args.out, "screenshots"),
            "note": "기본 출력 경로는 저장소 바깥의 임시 디렉터리다. 산출물을 커밋하지 않는다.",
        }
        os.makedirs(os.path.join(args.out, "screenshots"), exist_ok=True)
        path = report.write(report.artifacts["report_json"])
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        print("\n[E2E] 보고서: {0}".format(path))

        if args.with_frontend and frontend_process is not None:
            print("[E2E] 프런트엔드: {0}".format(frontend_origin))
            print("[E2E] 백엔드:   {0}".format(server.base_url if server else "(미기동)"))
            print("[E2E] 브라우저 검증을 마친 뒤 Ctrl-C로 종료하십시오.")
            try:
                frontend_process.wait()
            except KeyboardInterrupt:
                frontend_process.terminate()

        if server is not None:
            server.shutdown()
        asyncio.get_event_loop().run_until_complete(engine.dispose())
        if database is not None and not args.keep_db:
            removed = disposable_db.stop(database)
            print("[E2E] 폐기 DB 제거: {0}".format("성공" if removed else "실패"))

    if exit_code == 0 and report.verdict() != "HARNESS_READY":
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
