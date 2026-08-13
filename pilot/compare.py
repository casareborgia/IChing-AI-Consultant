"""파일럿 출력을 모델명 가린 대조표로 만든다.

    python pilot/compare.py runs/gemini-1.json runs/claude-1.json

브랜드를 알고 채점하면 결과가 오염되므로, 항목마다 좌우를 무작위로 뒤집어
A/B로만 표시한다. 어느 쪽이 어느 모델인지는 마지막 정답표에 적어 두고,
채점을 마친 뒤에 확인한다.
"""
import argparse
import json
import random
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):          # {"results": [...]} 형태도 받아준다
        data = data.get("results", list(data.values()))
    return {str(r["id"]): r for r in data}


def field(rec: dict, key: str) -> str:
    v = rec.get(key) if rec else None
    if v is None or v == "":
        return "—"
    if isinstance(v, dict):
        return ", ".join(f"{k}={x}" for k, x in v.items()) or "—"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("left")
    ap.add_argument("right")
    ap.add_argument("-o", "--output", default="pilot/blind_sheet.md")
    ap.add_argument("--seed", type=int, default=None, help="뒤섞기 재현용")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    lp, rp = Path(args.left), Path(args.right)
    left, right = load(lp), load(rp)

    items = json.loads(Path("pilot/items.json").read_text(encoding="utf-8"))

    lines = ["# 블라인드 채점지", "",
             "각 항목 A/B 중 어느 쪽이 어느 모델인지는 맨 아래 정답표에 있다.",
             "**채점을 끝낸 뒤에** 펼쳐볼 것.", ""]
    key = []
    missing = []

    for it in items:
        iid = it["id"]
        a_src, b_src = (lp.stem, rp.stem), None
        flip = rng.random() < 0.5
        a = right.get(iid) if flip else left.get(iid)
        b = left.get(iid) if flip else right.get(iid)
        key.append(f"| {iid} | {(rp if flip else lp).stem} | {(lp if flip else rp).stem} |")

        for label, rec in (("A", a), ("B", b)):
            if rec is None:
                missing.append(f"{iid}/{label}")

        lines += [
            f"## {iid} — {it['hexagram']} {it['target']}",
            "",
            f"> {it['source']}",
            "",
            f"*시험 항목: {it['tests']}*",
            "",
            "| | A | B |",
            "|---|---|---|",
            f"| 번역 | {field(a,'translation_ko')} | {field(b,'translation_ko')} |",
            f"| 소상전 | {field(a,'xiang_ko')} | {field(b,'xiang_ko')} |",
            f"| 용어 | {field(a,'key_terms')} | {field(b,'key_terms')} |",
            f"| 독음 근거 | {field(a,'reading_notes')} | {field(b,'reading_notes')} |",
            f"| 확신도 | {field(a,'confidence')} | {field(b,'confidence')} |",
            f"| flag | {field(a,'flag')} | {field(b,'flag')} |",
            "",
            "채점 — A: 정확 __ / 절제 __ / 용어 __ / 정직 __      "
            "B: 정확 __ / 절제 __ / 용어 __ / 정직 __",
            "",
        ]

    lines += ["---", "", "<details><summary>정답표 (채점 후 열기)</summary>", "",
              "| id | A | B |", "|---|---|---|", *key, "", "</details>", ""]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"채점지 생성 → {out}  (항목 {len(items)}건)")
    if missing:
        print(f"⚠️ 출력 누락 {len(missing)}건: {', '.join(missing)}")


if __name__ == "__main__":
    main()
