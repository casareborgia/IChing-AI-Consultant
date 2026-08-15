#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`kanripo_decisions.py`의 확정 판정을 파서 산출물에 반영한다.

보류 항목은 고치지 않고 해당 괘에 `open_questions`로 표시만 남긴다.
파서를 다시 돌리면 이 파일도 다시 돌려야 한다 — 파서 산출물은 원본 그대로고,
판정 반영은 그 위에 얹는 별도 단계다.

여러 번 돌려도 결과가 같다. 이미 반영된 자리는 건너뛴다.

사용법:
    python scripts/parse_kanripo.py
    python scripts/apply_decisions.py            # 제자리 반영
    python scripts/apply_decisions.py --dry-run  # 무엇이 바뀌는지만 본다
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kanripo_decisions import DECISIONS, KEPT, OPEN  # noqa: E402


def resolve(hexa: dict, slot: tuple):
    """slot이 가리키는 (컨테이너, 키) 목록. 주석 슬롯은 여러 개일 수 있다."""
    if slot[0] == "commentary":
        out = []
        for key in ("guasa", "danjeon", "daesang", "munon"):
            out += [(hexa[key]["commentary"], i)
                    for i in range(len(hexa[key]["commentary"]))]
        for ln in hexa["lines"]:
            out += [(ln["commentary"], i) for i in range(len(ln["commentary"]))]
            out += [(ln["sosang_commentary"], i)
                    for i in range(len(ln["sosang_commentary"]))]
        return out
    if slot[0] == "line":
        return [(hexa["lines"][slot[1] - 1], slot[2])]
    return [(hexa[slot[0]], slot[1])]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="손검토 확정 판정 반영")
    ap.add_argument("-f", "--file", type=Path,
                    default=root / "data" / "hexagrams_kanripo.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    hexes = json.loads(args.file.read_text(encoding="utf-8"))
    by_id = {h["hexagram_id"]: h for h in hexes}

    applied, already, missing = [], [], []
    for d in DECISIONS:
        hexa = by_id[d["hexagram"]]
        targets = resolve(hexa, d["slot"])
        hit = False
        for container, key in targets:
            text = container[key]
            if d["find"] in text:
                if not args.dry_run:
                    container[key] = text.replace(d["find"], d["replace"])
                applied.append(d)
                hit = True
                break
            if d["replace"] in text:
                already.append(d)
                hit = True
                break
        if not hit:
            missing.append(d)

    # 보류 항목은 고치지 않고 표시만 남긴다.
    for h in hexes:
        h.pop("open_questions", None)
    for q in OPEN:
        hexa = by_id[q["hexagram"]]
        hexa.setdefault("open_questions", []).append({
            "slot": list(q["slot"]), "old": q["old"], "new": q["new"],
            "status": "보류", "note": q["note"],
        })

    print(f"확정 {len(DECISIONS)}건 — 반영 {len(applied)} / 이미 반영 {len(already)}"
          f" / 못 찾음 {len(missing)}")
    for d in applied:
        print(f"  ✎ {d['hexagram']:>2} {'/'.join(map(str, d['slot'])):<20} "
              f"{d['find'][:22]} → {d['replace'][:22]}")
    for d in missing:
        print(f"  ✗ {d['hexagram']:>2} {'/'.join(map(str, d['slot']))}: "
              f"`{d['find'][:26]}` 없음 — 판정표와 원본이 어긋난다")

    print(f"\n신본 유지 {len(KEPT)}건 (변경 없음)")
    for hid, what, why in KEPT:
        print(f"  · {hid:>2} {what}")

    print(f"\n보류 {len(OPEN)}건 — open_questions로 표시")
    for q in OPEN:
        print(f"  ? {q['hexagram']:>2} {'/'.join(map(str, q['slot'])):<22} "
              f"{q['old']} / {q['new']}")

    if args.dry_run:
        print("\n--dry-run: 파일을 쓰지 않았다.")
        return 1 if missing else 0

    args.file.write_text(json.dumps(hexes, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print(f"\n→ {args.file}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
