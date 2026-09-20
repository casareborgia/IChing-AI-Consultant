# -*- coding: utf-8 -*-
"""기계 판독 가능한 실행 기록.

보고서에 사용자 식별자·상담 발화·토큰·DB 접속정보를 넣지 않는다. 대신 실행
안에서만 뜻이 통하는 별칭(user_a, op-S04-1)으로 바꾼다. 별칭은 상태 변화를
추적하기에 충분하고, 바깥으로 새어도 아무것도 식별하지 못한다.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# 헤더가 "eyJ"로 시작하는 JWT. 각 구간의 하한을 낮게 잡는다. 하한이 높으면
# 짧은 토큰이 그물을 빠져나가는데, 비밀 제거에서 빠져나감은 곧 유출이다.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]{2,}\.[A-Za-z0-9_\-]{2,}\.[A-Za-z0-9_\-]{2,}")
_PG_URL_RE = re.compile(r"postgresql(\+\w+)?://[^\s\"']+")

# 보고서에 그대로 실어도 되는 응답 필드. 상담 본문과 사용자 식별자는 제외한다.
SAFE_BODY_FIELDS = (
    "code",
    "operation_status",
    "credit_delta",
    "remaining_credits",
    "retry_after_seconds",
    "turn_number",
    "needs_followup",
    "is_final",
    "is_crisis",
    "is_duplicate",
    "error_code",
    "report_status",
    "welcome_granted",
)


class Aliases:
    """실제 식별자 → 실행 국소 별칭."""

    def __init__(self) -> None:
        self._map: Dict[str, str] = {}
        self._counts: Dict[str, int] = {}

    def auto(self, value: str) -> str:
        """등록된 적 없는 식별자에도 별칭을 준다. 원본은 보고서에 남지 않는다."""
        return self.alias("id", value) or "[REDACTED_ID]"

    def alias(self, kind: str, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value in self._map:
            return self._map[value]
        self._counts[kind] = self._counts.get(kind, 0) + 1
        label = "{0}-{1}".format(kind, self._counts[kind])
        self._map[value] = label
        return label

    def known(self, value: Optional[str]) -> Optional[str]:
        return self._map.get(value or "")


def scrub(text: Optional[str], aliases: Aliases) -> Optional[str]:
    """자유 문자열에서 식별자와 비밀을 지운다."""
    if text is None:
        return None
    out = _JWT_RE.sub("[REDACTED_JWT]", str(text))
    out = _PG_URL_RE.sub("[REDACTED_DB_URL]", out)

    def _swap(match: "re.Match") -> str:
        return aliases.known(match.group(0)) or "[REDACTED_ID]"

    return _UUID_RE.sub(_swap, out)


@dataclass
class HttpRecord:
    method: str
    path: str
    status: int
    scenario: str
    actor: str
    idempotency_key_ref: Optional[str] = None
    authenticated: bool = True
    body: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "status": self.status,
            "scenario": self.scenario,
            "actor": self.actor,
            "idempotency_key_ref": self.idempotency_key_ref,
            "authenticated": self.authenticated,
            "body_fields": self.body,
        }


def digest(value: Any) -> str:
    """자유 텍스트를 비교 가능하되 읽을 수 없는 형태로 바꾼다."""
    if value is None:
        return "null"
    raw = value if isinstance(value, str) else repr(value)
    return "sha256:{0} (len={1})".format(
        hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12], len(raw)
    )


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    aliases: Optional[Aliases] = None
    result: str = "NOT_RUN"
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    operation_transitions: List[Dict[str, Any]] = field(default_factory=list)
    balance_before: Optional[int] = None
    balance_after: Optional[int] = None
    failure_reason: Optional[str] = None

    def _reportable(self, value: Any) -> Any:
        """보고서에 실을 수 있는 형태로 바꾼다. 비교는 이미 끝난 뒤에 부른다."""
        if not isinstance(value, str):
            return value
        if _JWT_RE.search(value):
            return "[REDACTED_JWT]"
        if _PG_URL_RE.search(value):
            return "[REDACTED_DB_URL]"
        if _UUID_RE.fullmatch(value):
            if self.aliases is None:
                return "[REDACTED_ID]"
            return self.aliases.known(value) or self.aliases.auto(value)
        if _UUID_RE.search(value):
            return scrub(value, self.aliases) if self.aliases else "[REDACTED_ID]"
        return value

    def check(self, name: str, expected: Any, actual: Any) -> bool:
        ok = expected == actual
        self.assertions.append(
            {
                "name": name,
                "expected": self._reportable(expected),
                "actual": self._reportable(actual),
                "ok": ok,
            }
        )
        if not ok and self.result != "FAIL":
            self.result = "FAIL"
            self.failure_reason = "단언 실패: {0}".format(name)
        return ok

    def check_true(self, name: str, actual: bool) -> bool:
        return self.check(name, True, bool(actual))

    def check_opaque(self, name: str, expected: Any, actual: Any) -> bool:
        """상담 본문처럼 보고서에 실으면 안 되는 값의 일치 검사.

        비교는 원문으로 하고, 기록은 digest로만 한다. digest가 같으면 원문이
        같았다는 뜻이므로 검증 가치는 그대로다.
        """
        ok = expected == actual
        self.assertions.append(
            {
                "name": name,
                "expected": digest(expected),
                "actual": digest(actual),
                "ok": ok,
                "comparison": "opaque_digest",
            }
        )
        if not ok and self.result != "FAIL":
            self.result = "FAIL"
            self.failure_reason = "단언 실패: {0}".format(name)
        return ok

    def transition(self, op_ref: Optional[str], status: Optional[str], source: str) -> None:
        self.operation_transitions.append(
            {"operation_ref": op_ref, "operation_status": status, "observed_via": source}
        )

    def finish(self) -> None:
        if self.result != "FAIL":
            self.result = "PASS"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "result": self.result,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "operation_transitions": self.operation_transitions,
            "assertions": self.assertions,
            "failure_reason": self.failure_reason,
        }


class Report:
    """최종 JSON 한 장."""

    def __init__(self, *, run_sha: str) -> None:
        self.run_sha = run_sha
        self.aliases = Aliases()
        self.started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self.http: List[HttpRecord] = []
        self.scenarios: List[ScenarioResult] = []
        self.environment: Dict[str, Any] = {}
        self.artifacts: Dict[str, Any] = {}
        self.notes: List[str] = []
        self.run_id = uuid.uuid4().hex[:12]

    def record_http(self, record: HttpRecord) -> None:
        self.http.append(record)

    def scenario(self, scenario_id: str, title: str) -> ScenarioResult:
        result = ScenarioResult(
            scenario_id=scenario_id, title=title, aliases=self.aliases
        )
        self.scenarios.append(result)
        return result

    def verdict(self) -> str:
        if not self.scenarios:
            return "NOT_RUN"
        if any(s.result == "FAIL" for s in self.scenarios):
            return "NEEDS_FIX"
        if any(s.result == "NOT_RUN" for s in self.scenarios):
            return "PARTIAL"
        return "HARNESS_READY"

    def to_dict(self) -> Dict[str, Any]:
        passed = sum(1 for s in self.scenarios if s.result == "PASS")
        return {
            "schema": "iching.e2e-harness-report/v1",
            "cycle": "CYCLE-06",
            "run_id": self.run_id,
            "run_sha": self.run_sha,
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat(),
            "environment": self.environment,
            "sensitive_data_removed": True,
            "sensitive_data_policy": {
                "user_ids": "실행 국소 별칭(user-N)으로 치환",
                "counsel_content": "본문 미수록 (필드 이름과 boolean/정수만 기록)",
                "tokens": "미수록",
                "database_credentials": "비밀번호 제거된 URL만 기록",
                "operation_ids": "실행 국소 별칭(op-N)으로 치환",
            },
            "totals": {
                "scenarios": len(self.scenarios),
                "passed": passed,
                "failed": sum(1 for s in self.scenarios if s.result == "FAIL"),
                "not_run": sum(1 for s in self.scenarios if s.result == "NOT_RUN"),
                "http_requests": len(self.http),
            },
            "verdict": self.verdict(),
            "scenarios": [s.to_dict() for s in self.scenarios],
            "http_trace": [r.to_dict() for r in self.http],
            "artifacts": self.artifacts,
            "notes": self.notes,
        }

    def write(self, path: str) -> str:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return path


def safe_body(payload: Any) -> Dict[str, Any]:
    """응답에서 보고해도 되는 필드만 뽑는다."""
    if not isinstance(payload, dict):
        return {"_non_object_body": True}
    out: Dict[str, Any] = {}
    for key in SAFE_BODY_FIELDS:
        if key in payload:
            out[key] = payload[key]
    out["_field_names"] = sorted(str(k) for k in payload.keys())
    return out
