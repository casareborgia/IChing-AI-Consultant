# -*- coding: utf-8 -*-
"""폐기용 PostgreSQL 수명주기.

컨테이너를 새로 띄우고, marker를 심고, 끝나면 지운다. 운영자가 이미 돌리고
있는 컨테이너(`iching-db` 등)는 조회도 종료도 하지 않는다. 이름과 포트가 이
실행 전용이라 충돌하지 않는다.

여기서 하는 일은 migration 적용이 아니다. Supabase에 적용된 migration은 다시
쓰지 않는다. 빈 DB에 제품 SQLAlchemy 모델의 metadata로 스키마를 만든다.
"""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from tests.e2e.harness.safety import DATABASE_MARKER

IMAGE = "pgvector/pgvector:pg16"
DB_NAME = "iching_e2e_test"
DB_USER = "iching_e2e"
STARTUP_TIMEOUT_SECONDS = 90


@dataclass
class DisposableDatabase:
    container_name: str
    host_port: int
    database: str
    user: str
    password: str

    @property
    def async_url(self) -> str:
        return "postgresql+asyncpg://{u}:{p}@127.0.0.1:{port}/{db}".format(
            u=self.user, p=self.password, port=self.host_port, db=self.database
        )

    @property
    def redacted_url(self) -> str:
        """보고서용. 비밀번호를 지운다."""
        return "postgresql+asyncpg://{u}:[REDACTED]@127.0.0.1:{port}/{db}".format(
            u=self.user, port=self.host_port, db=self.database
        )


def _run(args: List[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


def docker_available() -> Optional[str]:
    """docker를 쓸 수 없으면 사유 문자열, 쓸 수 있으면 None."""
    probe = _run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=30)
    if probe.returncode != 0:
        return "docker 데몬에 연결할 수 없습니다"
    image = _run(["docker", "image", "inspect", IMAGE], timeout=30)
    if image.returncode != 0:
        return "필요한 이미지가 로컬에 없습니다: {0}".format(IMAGE)
    return None


def start(host_port: int) -> DisposableDatabase:
    """폐기용 컨테이너를 띄우고 준비될 때까지 기다린다."""
    name = "iching-e2e-cycle06-{0}".format(uuid.uuid4().hex[:10])
    password = uuid.uuid4().hex

    created = _run(
        [
            "docker", "run", "--rm", "--detach",
            "--name", name,
            # 데이터 디렉터리를 tmpfs에 두어 디스크에 남기지 않는다.
            "--tmpfs", "/var/lib/postgresql/data:rw,size=512m",
            "--publish", "127.0.0.1:{0}:5432".format(host_port),
            "--env", "POSTGRES_DB={0}".format(DB_NAME),
            "--env", "POSTGRES_USER={0}".format(DB_USER),
            "--env", "POSTGRES_PASSWORD={0}".format(password),
            "--env", "POSTGRES_INITDB_ARGS=--encoding=UTF-8 --locale=C",
            IMAGE,
        ]
    )
    if created.returncode != 0:
        raise RuntimeError(
            "폐기 DB 컨테이너를 만들지 못했습니다: {0}".format(created.stderr.strip()[:400])
        )

    db = DisposableDatabase(
        container_name=name,
        host_port=host_port,
        database=DB_NAME,
        user=DB_USER,
        password=password,
    )

    deadline = time.time() + STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        ready = _run(
            ["docker", "exec", name, "pg_isready", "-U", DB_USER, "-d", DB_NAME],
            timeout=30,
        )
        if ready.returncode == 0:
            return db
        time.sleep(1.0)

    stop(db)
    raise RuntimeError("폐기 DB가 제한 시간 안에 준비되지 않았습니다")


def stop(db: DisposableDatabase) -> bool:
    """이 실행이 만든 컨테이너만 지운다."""
    if not db.container_name.startswith("iching-e2e-cycle06-"):
        # 하네스가 만들지 않은 컨테이너는 어떤 경우에도 건드리지 않는다.
        return False
    killed = _run(["docker", "rm", "--force", db.container_name], timeout=60)
    return killed.returncode == 0


async def prepare_schema(engine) -> None:
    """marker를 심고 제품 모델 metadata로 스키마를 만든다."""
    from sqlalchemy import text

    from core.db import Base
    # metadata 등록을 위해 모든 모델 모듈을 import한다.
    import core.models.counsel  # noqa: F401
    import core.models.hexagram  # noqa: F401
    import core.models.rag  # noqa: F401

    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS public.test_environment_marker ("
                "marker_key text PRIMARY KEY, marker_value text NOT NULL)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO public.test_environment_marker(marker_key, marker_value) "
                "VALUES ('purpose', :marker) ON CONFLICT (marker_key) DO UPDATE "
                "SET marker_value = EXCLUDED.marker_value"
            ),
            {"marker": DATABASE_MARKER},
        )
        await connection.run_sync(Base.metadata.create_all)


async def verify_marker(engine) -> str:
    """쓰기 전에 marker를 확인한다. 틀리면 예외."""
    from sqlalchemy import text

    async with engine.connect() as connection:
        found = (
            await connection.execute(
                text(
                    "SELECT marker_value FROM public.test_environment_marker "
                    "WHERE marker_key = 'purpose'"
                )
            )
        ).scalar_one_or_none()

    if found != DATABASE_MARKER:
        raise SystemExit(
            "[E2E-ABORT] 대상 DB에서 폐기 marker를 확인하지 못했습니다. 쓰기를 중단합니다."
        )
    return found


def leftover_containers() -> List[str]:
    """이전 실행이 남긴 하네스 컨테이너 이름."""
    listed = _run(
        ["docker", "ps", "-a", "--filter", "name=iching-e2e-cycle06-",
         "--format", "{{.Names}}"],
        timeout=30,
    )
    if listed.returncode != 0:
        return []
    return [n for n in listed.stdout.split() if n.startswith("iching-e2e-cycle06-")]


def env_override_url() -> Optional[str]:
    """운영자가 승인한 임시 복원본을 쓰도록 지정했을 때만 값이 있다."""
    value = os.getenv("E2E_RESTORE_DATABASE_URL", "").strip()
    return value or None
