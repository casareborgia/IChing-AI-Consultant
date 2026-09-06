# -*- coding: utf-8 -*-
"""
애플리케이션 로깅 설정.

`uvicorn api.main:app`으로 띄우면 uvicorn이 자기 로거("uvicorn", "uvicorn.error",
"uvicorn.access")만 설정하고 root 로거는 그대로 둔다. root에 핸들러가 없으면
파이썬은 lastResort 핸들러(WARNING 이상, stderr)로만 내보내므로, 앱 코드의
`logger.info(...)`는 어디에도 남지 않는다. 운영에서 리포트 생성의
`status`/`duration_ms` 로그가 한 줄도 쌓이지 않은 원인이 이것이었다.

Cloud Run은 stdout을 INFO, stderr를 ERROR로 뭉뚱그려 기록한다. 그래서 운영에서는
JSON 한 줄로 내보내 `severity`를 명시한다. Cloud Logging이 이 필드를 읽어 실제
레벨을 붙이므로 `severity>=WARNING` 같은 조회가 그대로 동작한다. 로컬에서는
사람이 읽는 형식이 낫기 때문에 평문을 쓴다.
"""

import json
import logging
import logging.config
import sys
from typing import Any, Dict

# 파이썬 로그 레벨 -> Cloud Logging severity.
# 이름이 겹치는 것이 대부분이지만 WARNING/CRITICAL은 표기가 다르다.
_SEVERITY_BY_LEVEL = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class CloudRunJsonFormatter(logging.Formatter):
    """Cloud Logging이 구조화 로그로 인식하는 JSON 한 줄로 직렬화한다."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "severity": _SEVERITY_BY_LEVEL.get(record.levelno, record.levelname),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            # 스택 트레이스는 message에 붙여야 Cloud Logging UI에서 함께 보인다.
            payload["message"] = f"{payload['message']}\n{self.formatException(record.exc_info)}"
        return json.dumps(payload, ensure_ascii=False)


# root에 핸들러를 붙이면 서드파티 로거도 함께 흘러나온다. 이 둘은 LLM·임베딩을
# 호출할 때마다 요청 URL을 INFO로 남겨, 상담 1건에 20줄 넘게 쌓였다. 앱 로그를
# 보려고 붙인 핸들러이므로 여기서만 레벨을 올려 조용히 시킨다. 호출 실패는
# WARNING 이상이라 그대로 보인다.
_NOISY_LOGGERS = ("httpx", "httpcore", "google_genai")


def build_logging_config(level: str, environment: str) -> Dict[str, Any]:
    """dictConfig에 넘길 설정을 만든다.

    `disable_existing_loggers`는 반드시 False다. True면 이 설정보다 먼저 만들어진
    uvicorn 로거들이 꺼져 액세스 로그가 사라진다.
    """
    normalized = (level or "INFO").upper()
    if normalized not in _SEVERITY_BY_LEVEL.values():
        normalized = "INFO"

    formatter = "json" if environment == "production" else "plain"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": f"{CloudRunJsonFormatter.__module__}.CloudRunJsonFormatter"},
            "plain": {"format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s"},
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": formatter,
                "stream": sys.stdout,
            }
        },
        "loggers": {name: {"level": "WARNING"} for name in _NOISY_LOGGERS},
        "root": {"handlers": ["default"], "level": normalized},
    }


def configure_logging(level: str = "INFO", environment: str = "development") -> None:
    """root 로거에 핸들러를 붙인다. 앱 임포트 시점에 한 번 호출한다."""
    logging.config.dictConfig(build_logging_config(level, environment))
