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

# 효 표시 한글화. 모델이 '初六은'으로 남기기도 하고 '구삼은'으로 옮기기도 해서
# 386건 안에서 표기가 섞인다(측정: 95건이 한자, 282건이 한글). 뜻에는 영향이
# 없지만 [3] 상담 에이전트가 인용할 때 두 표기가 섞여 나온다.
#
# 원본 JSON은 모델 출력 그대로 두고 여기서만 바꾼다. 원본은 증거로 남겨야 한다.
LINE_MARKERS = {
    "初九": "초구", "初六": "초육",
    "九二": "구이", "六二": "육이",
    "九三": "구삼", "六三": "육삼",
    "九四": "구사", "六四": "육사",
    "九五": "구오", "六五": "육오",
    "上九": "상구", "上六": "상육",
    "用九": "용구", "用六": "용육",
}


def normalize_marker(text: str, source: str) -> Tuple[str, str]:
    """앞머리의 한자 효 표시를 한글로 바꾼다.

    문장 맨 앞만 본다. 실제로 중간에 나온 사례는 없었고, 본문 속 한자까지
    건드리면 괘 이름 같은 것을 망가뜨린다.

    원문의 효 표시와 다른 것을 붙였으면 바꾸지 않고 경고로 돌려준다.
    번역이 엉뚱한 효를 가리키고 있다는 뜻이라 조용히 고칠 일이 아니다.
    """
    for hanja, korean in LINE_MARKERS.items():
        if text.startswith(hanja):
            if not source.startswith(hanja):
                return text, f"효 표시 불일치: 번역 '{hanja}' / 원문 '{source[:2]}'"
            return korean + text[len(hanja):], ""
    return text, ""


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


async def load(path: str, dry_run: bool, items_path: str) -> int:
    records = json.load(open(path, encoding="utf-8"))
    sources = {str(i["id"]): i["source"] for i in json.load(open(items_path, encoding="utf-8"))}
    ok, skipped = split_records(records)
    print(f"{path}: 총 {len(records)}건 → 적재 대상 {len(ok)}건 / 제외 {len(skipped)}건")

    updated_gua = updated_hyo = normalized = 0
    missing, marker_warn = [], []

    async with AsyncSessionLocal() as session:
        for r in ok:
            kind, hid, pos = parse_id(str(r["id"]))
            text = r["translation_ko"].strip()

            if kind == "hyo":
                fixed, warn = normalize_marker(text, sources.get(str(r["id"]), ""))
                if warn:
                    marker_warn.append(f"{r['id']}: {warn}")
                elif fixed != text:
                    text = fixed
                    normalized += 1

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

    print(f"괘사 {updated_gua}건 / 효사 {updated_hyo}건 (효 표시 한글화 {normalized}건)")
    if marker_warn:
        print(f"\n⚠️ 효 표시가 원문과 다른 항목 {len(marker_warn)}건 — 그대로 두었다:")
        for w in marker_warn:
            print(f"  {w}")
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
    ap.add_argument("--items", default="data/translation_items.json", help="원문 항목 파일 (효 표시 대조용)")
    args = ap.parse_args()

    problems = asyncio.run(load(args.input, args.dry_run, args.items))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
