"""3단계 본배치 450건(괘사 64 + 효사 386)을 data/hexagrams.json에서 뽑는다.

    python scripts/build_batch_items.py -o data/translation_items.json

pilot/build_items.py와 **같은 스키마·같은 id 규칙**으로 낸다. 여기가 어긋나면
파일럿에서 검증한 조건이 본배치에서 조용히 달라진다. 주석 발췌 상한도 파일럿과
같은 420자다.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

COMMENTARY_CAP = 420   # pilot/build_items.py와 같아야 한다


def build(hexagrams: list) -> list:
    items = []
    for h in hexagrams:
        hid = h["hexagram_id"]
        label = f"제{hid}괘 {h['name_hanja']}"
        items.append({
            "id": f"H{hid}",
            "target": "괘사",
            "hexagram": label,
            "source": h["guasa"]["original"],
            "xiang": None,
            "commentary": (h["guasa"]["commentary"] or [""])[0][:COMMENTARY_CAP],
        })
        for line in h["lines"]:
            pos = line["position"]
            items.append({
                "id": f"L{hid}-{pos}",
                "target": f"{pos}효 효사",
                "hexagram": label,
                "source": line["original"],
                "xiang": line.get("sosang") or None,
                "commentary": (line["commentary"] or [""])[0][:COMMENTARY_CAP],
            })
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="data/translation_items.json")
    args = ap.parse_args()

    root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
    hexagrams = json.load(open(os.path.join(root, "data", "hexagrams.json"), encoding="utf-8"))
    items = build(hexagrams)

    # 건수와 id 유일성은 여기서 막는다. 450건이 아니면 원문 데이터가 변한 것이다.
    gua = [i for i in items if i["id"].startswith("H")]
    hyo = [i for i in items if i["id"].startswith("L")]
    assert len(gua) == 64, f"괘사 {len(gua)}건 (기대 64)"
    assert len(hyo) == 386, f"효사 {len(hyo)}건 (기대 386)"
    assert len(items) == len({i["id"] for i in items}), "id 중복"
    assert all(i["source"].strip() for i in items), "원문이 빈 항목이 있다"

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    longest = max(items, key=lambda i: len(i["source"]))
    print(f"{len(items)}건 생성 → {args.output} (괘사 {len(gua)} + 효사 {len(hyo)})")
    print(f"  원문 최장: {longest['id']} {len(longest['source'])}자")


if __name__ == "__main__":
    main()
