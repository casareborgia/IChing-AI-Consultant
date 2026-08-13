"""3단계 번역 파일럿 12건을 data/hexagrams.json에서 추출한다.

항목마다 시험하려는 능력이 다르다. RUBRIC.md의 채점 항목과 1:1로 대응한다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

# (종류, 괘번호, 효위치 or None, 이 항목으로 시험하는 것)
PICKS = [
    ("gua",  1,  None, "元亨利貞을 사덕(四德) 넷으로 볼지 한 문장으로 볼지 — 해석 전통 인지"),
    ("gua",  4,  None, "재삼독즉불고. 긴 복합문에서 화자(我/童蒙)가 뒤바뀌지 않는지"),
    ("gua", 29,  None, "현토 '하'가 두 곳 빠진 상태에서 문장 구조를 잡는지"),
    ("gua", 56,  None, "주어가 생략된 극단적 압축문을 늘여쓰기로 뭉개지 않는지"),
    ("line", 1,  7,    "用九는 1~6효가 아닌 특수 항목이다. 일반 효사로 오인하는지"),
    ("line", 2,  1,    "履霜堅冰 — 은유를 은유로 옮기는지, 해설로 풀어버리는지"),
    ("line", 4,  1,    "說桎梏의 說는 '설'이 아니라 '탈'(脫). 독음 함정"),
    ("line", 29, 2,    "'求' 뒤 토가 통째로 빠진 자리. 모른 척 지어내는지"),
    ("line", 29, 4,    "樽·簋·缶·牖 — 기물 명사 밀집. 임의로 현대화하는지"),
    ("line", 29, 6,    "徽纆·叢棘 형구 이미지에 凶. 과장·공포 조장으로 새는지"),
    ("line", 47, 1,    "臀(볼기) — 신체 표현을 완곡하게 회피하는지"),
    ("line", 63, 3,    "高宗·鬼方 — 역사 고유명사를 일반명사로 뭉개는지"),
]

COMMENTARY_CAP = 420  # 정전 주석 발췌 길이


def main():
    root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
    data = json.load(open(os.path.join(root, "data", "hexagrams.json"), encoding="utf-8"))
    by_id = {h["hexagram_id"]: h for h in data}

    items = []
    for kind, hid, pos, tests in PICKS:
        hexagram = by_id[hid]
        if kind == "gua":
            item = {
                "id": f"H{hid}",
                "target": "괘사",
                "hexagram": f"제{hid}괘 {hexagram['name_hanja']}",
                "source": hexagram["guasa"]["original"],
                "xiang": None,
                "commentary": (hexagram["guasa"]["commentary"] or [""])[0][:COMMENTARY_CAP],
            }
        else:
            line = next(l for l in hexagram["lines"] if l["position"] == pos)
            item = {
                "id": f"L{hid}-{pos}",
                "target": f"{pos}효 효사",
                "hexagram": f"제{hid}괘 {hexagram['name_hanja']}",
                "source": line["original"],
                "xiang": line.get("sosang") or None,
                "commentary": (line["commentary"] or [""])[0][:COMMENTARY_CAP],
            }
        item["tests"] = tests
        items.append(item)

    out = os.path.join(os.path.dirname(__file__), "items.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"{len(items)}건 생성 → {out}")
    for it in items:
        print(f"  {it['id']:8s} {it['hexagram']:12s} {it['source'][:38]}")


if __name__ == "__main__":
    main()
