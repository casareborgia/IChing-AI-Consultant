#!/usr/bin/env python
"""v2 리포트의 JSON Schema와 fixture를 파일로 내보낸다.

프런트엔드가 TypeScript 타입을 옮길 때 보는 것은 이 산출물이지 파이썬 클래스가
아니다. 손으로 옮겨 적으면 어긋나므로 생성해서 커밋한다.

    python scripts/export_report_v2_contract.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from schemas.report_v2 import NarrativeDraft, PreCounselingReport
from tests.fixtures.report_v2_builder import ALL_FIXTURES

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_DIR = os.path.join(ROOT, "schemas", "json")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "report_v2")


def write(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2, sort_keys=True)
        fp.write("\n")
    print(f"wrote {os.path.relpath(path, ROOT)}")


def main() -> None:
    os.makedirs(SCHEMA_DIR, exist_ok=True)
    os.makedirs(FIXTURE_DIR, exist_ok=True)

    write(
        os.path.join(SCHEMA_DIR, "pre_counseling_report_v2.schema.json"),
        PreCounselingReport.model_json_schema(),
    )
    write(
        os.path.join(SCHEMA_DIR, "report_v2_narrative_draft.schema.json"),
        NarrativeDraft.model_json_schema(),
    )

    for name, builder in ALL_FIXTURES.items():
        write(os.path.join(FIXTURE_DIR, f"{name}.json"), builder())


if __name__ == "__main__":
    main()
