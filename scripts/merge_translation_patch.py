#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
번역 배치에 패치분을 덮어쓴다.

전량 배치가 도는 동안 손검토 판정이 더 확정되면 원문이 바뀐 항목이 생긴다.
그 몇 건만 다시 돌려(`translation_patch.json`) 여기서 합친다. 전량을 다시
돌리지 않는 이유는 그것 말고는 입력이 같기 때문이다.

id 순서는 원본 배치를 따른다. 패치에만 있는 id는 뒤에 붙이지 않고 오류로
잡는다 — 그런 id가 있다면 입력이 어긋난 것이다.

사용법:
    python scripts/merge_translation_patch.py \\
        --base data/translations/kanripo/claude.json \\
        --patch data/translations/kanripo/_patch_claude.json
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="번역 패치 병합")
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--patch", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, help="기본값: --base 자리에 덮어쓴다")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = json.loads(args.base.read_text(encoding="utf-8"))
    patch = {r["id"]: r for r in json.loads(args.patch.read_text(encoding="utf-8"))}

    unknown = sorted(patch.keys() - {r["id"] for r in base})
    if unknown:
        print(f"✗ 배치에 없는 id {len(unknown)}건: {unknown[:5]} — 입력이 어긋났다")
        return 1

    failed = [i for i, r in patch.items() if r.get("_meta", {}).get("status") != "success"]
    if failed:
        print(f"✗ 패치에 실패 건이 있다: {failed}")
        return 1

    merged, changed = [], []
    for rec in base:
        new = patch.get(rec["id"])
        if new is None:
            merged.append(rec)
            continue
        if new.get("translation_ko") != rec.get("translation_ko"):
            changed.append((rec["id"], rec.get("translation_ko"), new.get("translation_ko")))
        merged.append(new)

    print(f"{len(base)}건 중 {len(patch)}건 교체 (번역문이 실제로 달라진 것 {len(changed)}건)")
    for rid, before, after in changed:
        print(f"  {rid}")
        print(f"    구 {before}")
        print(f"    신 {after}")

    if args.dry_run:
        print("\n--dry-run: 파일을 쓰지 않았다.")
        return 0

    dest = args.out or args.base
    dest.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
