"""번역 결과를 DB에 적재한다 — `judgment_ko`, `statement_ko`만.

    python scripts/load_translations.py data/translations/claude.json
    python scripts/load_translations.py data/translations/claude.json --dry-run

원칙(pilot/HANDOFF.md):
  - 원문 필드(`judgment_text`, `statement_text`, `small_xiang_text`)는 읽기 전용이다.
    이 스크립트는 그 필드들을 손대지 않는다.
  - 멱등하다. 있으면 갱신, 없으면 오류. 행 자체는 seed_hexagrams.py가 만든다.
  - 실패 레코드는 적재하지 않는다. translate.py는 실패해도 레코드를 남기는데
    translation_ko가 None이라, 거르지 않으면 빈 번역이 DB에 들어간다.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select

from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line

ID_RE = re.compile(r"^(?:H(\d{1,2})|L(\d{1,2})-(\d))$")


def parse_id(item_id: str) -> Tuple[str, int, int]:
    """'H29' -> ('gua', 29, 0),  'L29-2' -> ('hyo', 29, 2)"""
    m = ID_RE.match(item_id)
    if not m:
        raise ValueError(f"알 수 없는 id 형식: {item_id}")
    if m.group(1):
        return "gua", int(m.group(1)), 0
    return "hyo", int(m.group(2)), int(m.group(3))


def split_records(records: List[Dict[str, Any]]):
    """적재 가능한 것과 걸러낼 것을 나눈다."""
    ok, skipped = [], []
    for r in records:
        status = (r.get("_meta") or {}).get("status")
        text = (r.get("translation_ko") or "").strip()
        if status == "failed":
            skipped.append((r.get("id"), "번역 실패 레코드"))
        elif not text:
            skipped.append((r.get("id"), "translation_ko가 비어 있음"))
        else:
            ok.append(r)
    return ok, skipped


async def load(path: str, dry_run: bool) -> int:
    records = json.load(open(path, encoding="utf-8"))
    ok, skipped = split_records(records)
    print(f"{path}: 총 {len(records)}건 → 적재 대상 {len(ok)}건 / 제외 {len(skipped)}건")

    updated_gua = updated_hyo = 0
    missing = []

    async with AsyncSessionLocal() as session:
        for r in ok:
            kind, hid, pos = parse_id(str(r["id"]))
            text = r["translation_ko"].strip()

            if kind == "gua":
                row = (await session.execute(
                    select(Hexagram).where(Hexagram.id == hid)
                )).scalar_one_or_none()
                if row is None:
                    missing.append(r["id"]); continue
                row.judgment_ko = text
                updated_gua += 1
            else:
                row = (await session.execute(
                    select(Line).where(Line.hexagram_id == hid, Line.line_number == pos)
                )).scalar_one_or_none()
                if row is None:
                    missing.append(r["id"]); continue
                row.statement_ko = text
                updated_hyo += 1

        if dry_run:
            await session.rollback()
            print("--dry-run: 되돌렸다. DB는 그대로다.")
        else:
            await session.commit()

    print(f"괘사 {updated_gua}건 / 효사 {updated_hyo}건")
    if skipped:
        print(f"\n제외 {len(skipped)}건 — 다시 돌려서 채워야 한다:")
        for iid, why in skipped[:20]:
            print(f"  {iid}: {why}")
        if len(skipped) > 20:
            print(f"  … 외 {len(skipped) - 20}건")
    if missing:
        print(f"\n⚠️ DB에 행이 없는 id {len(missing)}건: {', '.join(map(str, missing[:10]))}")
        print("   seed_hexagrams.py를 먼저 돌렸는지 확인할 것.")
    return len(skipped) + len(missing)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="번역 결과 JSON (translate.py 출력)")
    ap.add_argument("--dry-run", action="store_true", help="적재하지 않고 결과만 본다")
    args = ap.parse_args()

    problems = asyncio.run(load(args.input, args.dry_run))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
