"""로깅 설정 회귀 테스트.

운영에서 리포트 생성의 status/duration_ms 로그가 통째로 유실됐던 원인은 root
로거에 핸들러가 없어 logger.info()가 버려진 것이었다. 아래 테스트는 그 상태로
되돌아가지 않는지를 지킨다.
"""

import json
import logging
import logging.config

import pytest

from core.logging_config import _NOISY_LOGGERS, build_logging_config, configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """테스트가 전역 로깅 상태를 바꾸므로 원래대로 되돌린다.

    root뿐 아니라 서드파티 로거 레벨도 되돌린다. 안 그러면 이 파일이 올려둔
    WARNING이 같은 세션의 다른 테스트까지 조용히 시킨다.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_third_party = {name: logging.getLogger(name).level for name in _NOISY_LOGGERS}
    yield
    root.handlers[:] = saved_handlers
    root.level = saved_level
    for name, level in saved_third_party.items():
        logging.getLogger(name).setLevel(level)


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


def test_noisy_third_party_loggers_are_quieted(capsys):
    """httpx/google_genai의 호출별 INFO는 버리고 WARNING 이상만 남긴다."""
    configure_logging("INFO", "production")

    logging.getLogger("httpx").info("HTTP Request: POST https://example.invalid/x 200 OK")
    # 실제 로거 이름은 google_genai.models다. 부모에 건 레벨이 상속되는지 본다.
    logging.getLogger("google_genai.models").info("AFC is enabled with max remote calls: 10.")
    logging.getLogger("httpx").warning("호출 실패는 그대로 보여야 한다")

    lines = [ln for ln in capsys.readouterr().out.strip().splitlines() if ln]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["severity"] == "WARNING"
    assert payload["logger"] == "httpx"


def test_app_logger_is_not_quieted(capsys):
    """서드파티를 조용히 시키느라 앱 로거까지 막으면 안 된다."""
    configure_logging("INFO", "production")

    logging.getLogger("agents.pipeline").info("리포트 생성 완료: session=s status=ready duration_ms=1")

    assert "duration_ms=1" in capsys.readouterr().out


def test_unknown_level_falls_back_to_info():
    """오타 난 LOG_LEVEL 때문에 앱이 죽거나 로그가 조용해지면 안 된다."""
    assert build_logging_config("verbose", "production")["root"]["level"] == "INFO"
    assert build_logging_config("", "production")["root"]["level"] == "INFO"
    assert build_logging_config("warning", "production")["root"]["level"] == "WARNING"
