"""로깅 설정 회귀 테스트.

운영에서 리포트 생성의 status/duration_ms 로그가 통째로 유실됐던 원인은 root
로거에 핸들러가 없어 logger.info()가 버려진 것이었다. 아래 테스트는 그 상태로
되돌아가지 않는지를 지킨다.
"""

import json
import logging
import logging.config

import pytest

from core.logging_config import build_logging_config, configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """테스트가 전역 로깅 상태를 바꾸므로 원래대로 되돌린다."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.level = saved_level


def test_root_logger_emits_info_after_configure(capsys):
    """앱 로거의 info가 stdout으로 나가야 한다 (예전에는 전부 사라졌다)."""
    configure_logging("INFO", "development")

    logging.getLogger("agents.pipeline").info(
        "리포트 생성 완료: session=%s status=%s duration_ms=%d", "sid-1", "ready", 1234
    )

    out = capsys.readouterr().out
    assert "리포트 생성 완료: session=sid-1 status=ready duration_ms=1234" in out


def test_production_emits_json_with_severity(capsys):
    """Cloud Run에서 severity를 잃지 않도록 운영은 JSON 한 줄로 내보낸다."""
    configure_logging("INFO", "production")

    logging.getLogger("agents.pipeline").error(
        "리포트 에이전트 실행 실패: session=%s error_code=%s", "sid-2", "ValueError"
    )

    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["severity"] == "ERROR"
    assert payload["logger"] == "agents.pipeline"
    assert payload["message"] == "리포트 에이전트 실행 실패: session=sid-2 error_code=ValueError"


def test_existing_loggers_are_not_disabled():
    """uvicorn 로거를 끄면 액세스 로그가 사라진다. dictConfig가 이를 건드리면 안 된다."""
    assert build_logging_config("INFO", "production")["disable_existing_loggers"] is False

    access = logging.getLogger("uvicorn.access")
    configure_logging("INFO", "production")
    assert access.disabled is False


def test_unknown_level_falls_back_to_info():
    """오타 난 LOG_LEVEL 때문에 앱이 죽거나 로그가 조용해지면 안 된다."""
    assert build_logging_config("verbose", "production")["root"]["level"] == "INFO"
    assert build_logging_config("", "production")["root"]["level"] == "INFO"
    assert build_logging_config("warning", "production")["root"]["level"] == "WARNING"
