#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파서 출력 검증 — 두 방향으로 본다.

  (1) 무손실  파서가 뱉은 블록이 Kanripo 원본에 글자 그대로 있는가.
               파서가 글자를 바꾸거나 지어내지 않았다는 확인이다.
  (2) 보존    기존 hexagrams.json의 블록이 새 출력에 남아 있는가.
               이관으로 내용이 사라지지 않았다는 확인이다.

(2)는 100%가 나오지 않는다. 블록을 나누는 자리가 다르기 때문이다 — 특히
기존 데이터는 괘 서두 序卦 해설을 앞 괘 끝에 붙여놨어서, 그 블록들은 새
출력에서 경계를 넘나든다. 그래서 완전일치 / ≥95% 근사 / 미확인을 나눠 센다.
미확인으로 남는 것만 손으로 보면 된다.

사용법:
    python scripts/verify_kanripo.py
    python scripts/verify_kanripo.py --show 20     # 미확인 블록 20개 출력
"""

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kanripo_decisions import DECISIONS  # noqa: E402
from kanripo_variants import loose_key   # noqa: E402
from parse_kanripo import PB_TAG         # noqa: E402

# 확장A(㐀-䶿)·확장B까지 남긴다. 사고전서본은 㢲·𧰼·𥘉 같은 확장 영역 글자를
# 쓰므로, 정규화보다 먼저 걸러내면 멀쩡한 글자가 통째로 사라진다.
NON_HANJA = re.compile(r"[^㐀-䶿一-鿿\U00020000-\U0002ffff]")


def fingerprint(text: str) -> str:
    """비교 전용 지문. 정규화를 먼저 하고 한자만 남긴다 (순서 중요)."""
    return NON_HANJA.sub("", loose_key(text))


def blocks_of(hexes: list[dict]) -> tuple[list, list]:
    orig, comm = [], []
    for x in hexes:
        # 序卦 해설은 별도 필드다. 안 세면 무손실 검사가 62블록을 놓친다.
        comm += [(x["hexagram_id"], "intro", c) for c in x.get("intro") or []]
        for k in ("guasa", "danjeon", "daesang", "munon"):
            orig.append((x["hexagram_id"], k, x[k]["original"]))
            comm += [(x["hexagram_id"], k, c) for c in x[k]["commentary"]]
        for ln in x["lines"]:
            orig.append((x["hexagram_id"], "hyo", ln["original"]))
            orig.append((x["hexagram_id"], "sosang", ln["sosang"]))
            comm += [(x["hexagram_id"], "hyo", c) for c in ln["commentary"]]
            comm += [(x["hexagram_id"], "sosang", c) for c in ln["sosang_commentary"]]
    return orig, comm


def raw_corpus(src: Path) -> tuple[str, str]:
    """원본 경문·정전 주석부를 지문으로 만든다."""
    gy = "".join((src / f"KR1a0001_{i:03d}.txt").read_text(encoding="utf-8")
                 for i in range(1, 70))
    gy = "".join(l for l in PB_TAG.sub("", gy).split("\n")
                 if l and not l.startswith(("#", "**")))
    jn = "".join((src / f"KR1a0016_{v:03d}.txt").read_text(encoding="utf-8")
                 for v in range(1, 5))
    jn = "".join(l.strip("　") for l in PB_TAG.sub("", jn).split("\n")
                 if l.startswith("　"))
    return fingerprint(gy.replace("¶", "")), fingerprint(jn.replace("¶", ""))


def near_ratio(needle: str, hay: str) -> float:
    """앵커로 후보 위치를 좁힌 뒤 국소 비교한다. 전체 O(n·m)을 피한다."""
    length = len(needle)
    best = 0.0
    for off in (0, length // 4, length // 3, length // 2):
        anchor = needle[off:off + 10]
        if len(anchor) < 8:
            continue
        pos, tried = hay.find(anchor), 0
        while pos != -1 and tried < 40:
            start = max(0, pos - off)
            best = max(best, difflib.SequenceMatcher(
                None, needle, hay[start:start + length], autojunk=False).ratio())
            if best >= 0.995:
                return best
            pos, tried = hay.find(anchor, pos + 1), tried + 1
        if best >= 0.95:
            break
    return best


def report(blocks, hay, label, collect):
    exact = near = unknown = 0
    for hid, kind, text in blocks:
        fp = fingerprint(text)
        if not fp:
            continue
        if fp in hay:
            exact += 1
        elif near_ratio(fp, hay) >= 0.95:
            near += 1
        else:
            unknown += 1
            collect.append((hid, kind, fp))
    total = exact + near + unknown
    if not total:
        return
    print(f"  {label:<12} 완전 {exact:>5} ({exact/total:6.1%})   "
          f"≥95% {near:>4} ({near/total:6.1%})   "
          f"미확인 {unknown:>4} ({unknown/total:6.1%})")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Kanripo 파서 출력 검증")
    ap.add_argument("--src", type=Path, default=root / "data" / "kanripo")
    ap.add_argument("--new", type=Path, default=root / "data" / "hexagrams_kanripo.json")
    ap.add_argument("--old", type=Path, default=root / "data" / "hexagrams.json")
    ap.add_argument("--show", type=int, default=0, help="미확인 블록을 N개 출력")
    args = ap.parse_args()

    new = json.loads(args.new.read_text(encoding="utf-8"))
    raw_gy, raw_jn = raw_corpus(args.src)
    n_orig, n_comm = blocks_of(new)

    print("── (1) 무손실: 파서 출력이 원본에 글자 그대로 있는가 ──")
    lossy: list = []
    report(n_orig, raw_gy, "원문", lossy)
    report(n_comm, raw_jn, "주석", lossy)

    # apply_decisions.py를 돌린 뒤에는 확정 판정만큼 원본에서 벗어난다.
    # 그건 의도한 것이므로 파서 버그와 갈라서 센다.
    fixes = [fingerprint(d["replace"]) for d in DECISIONS]
    decided = [b for b in lossy if any(f and f in fingerprint(b[2]) for f in fixes)]
    bugs = [b for b in lossy if b not in decided]
    if decided:
        print(f"  · 판정 반영으로 원본과 달라진 블록 {len(decided)}건 — 정상")
    if bugs:
        print(f"  ⚠ 설명되지 않는 블록 {len(bugs)}건 — 파서 버그 가능성")
        for hid, kind, fp in bugs[:5]:
            print(f"      [{hid}/{kind}] {fp[:60]}")
    lossy = bugs

    if args.old.exists():
        old = json.loads(args.old.read_text(encoding="utf-8"))
        o_orig, o_comm = blocks_of(old)
        hay_o = fingerprint("".join(t for _, _, t in n_orig))
        hay_c = fingerprint("".join(t for _, _, t in n_comm))
        print("\n── (2) 보존: 기존 데이터 블록이 새 출력에 남아 있는가 ──")
        missing: list = []
        report(o_orig, hay_o, "원문", missing)
        report(o_comm, hay_c, "주석", missing)
        print(f"\n  손검토 대상 {len(missing)}블록"
              f"   괘 분포 {Counter(h for h, _, _ in missing).most_common(5)}")
        for hid, kind, fp in missing[:args.show]:
            print(f"    [{hid}/{kind}] {fp[:70]}")

    return 1 if lossy else 0


if __name__ == "__main__":
    sys.exit(main())
