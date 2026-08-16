#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주자 『본의(本義)』 파서 — 原本周易本義(KR1a0031) → data/benui.json.

사용법:
    python scripts/fetch_kanripo.py --with-benui
    python scripts/parse_benui.py -o data/benui.json

--------------------------------------------------------------------------
왜 별도 파일인가

`data/hexagrams_kanripo.json`에 섞지 않는다. 그 파일은 경문 + 정전의 산출물이고
`verify_kanripo.py`가 무손실을 검증하는 대상이다. 다른 저작을 그 안에 합치면
어느 글자가 어느 책에서 왔는지가 흐려지고, 손검토 판정 50건을 다시 얹는 절차도
꼬인다. 序卦 해설을 `gwa_intro`로 갈라둔 것과 같은 판단이다 — 갈라 두어야
나중에 가중치를 달리 주거나 뺄 수 있다.

--------------------------------------------------------------------------
저본의 생김새

원본주역본의는 경문을 본문으로 두고 주석을 **인라인 괄호**로 넣는다.

    ䷀(乾下/乾上)乾元亨利貞(六畫者伏羲所畫之卦也一者/竒也陽之數也乾者健也陽之)¶
    (性也本注乾字三畫卦之名也下者内卦也上者外卦/也經文乾字六畫卦之名也...)¶

읽을 때 걸리는 것이 셋이다.

1. `/`는 割註(소자쌍행)의 **행 나눔 표시**다. 판면에서 두 줄로 조판된 것이라
   지우고 이어 붙이면 원문이 된다. 다만 괘 머리의 `(乾下/乾上)`은 割註가 아니라
   괘체 표기다 — 여기서 `/`를 지우면 안 된다. 그래서 괘체 헤더를 먼저 떼어낸다.
2. 괄호가 판면 행 끝에서 닫히고 다음 행에서 다시 열린다. `)(`로 맞붙은 자리는
   같은 주석의 이어짐이므로 합친다.
3. 효 머리(初九·六二…)가 주석 **안에도** 나온다("九二雖未得位而…"). 그래서
   괄호 밖 텍스트에서만 효를 가른다. 괄호 깊이를 세며 훑는 이유가 이것이다.

卷一(上經)·卷二(下經)은 괘사와 효사, 卷三~六은 단전과 상전이다. 卷七 이하는
계사·설괘·서괘·잡괘·문언이라 읽지 않는다 — 정전에서 뺀 것과 같은 이유다
(CLAUDE.md 데이터 레이어 절: 특정 괘에 붙지 않는 일반론은 검색에 섞이면 안 된다).
--------------------------------------------------------------------------
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kanripo_variants import normalize  # noqa: E402

KANRIPO_DIR = Path(__file__).resolve().parent.parent / "data" / "kanripo"

# 효(爻) 머리. parse_kanripo.py와 같은 표를 쓴다. 용구·용육은 7번이다.
LINE_MARKERS = {
    "初九": 1, "初六": 1, "九二": 2, "六二": 2, "九三": 3, "六三": 3,
    "九四": 4, "六四": 4, "九五": 5, "六五": 5, "上九": 6, "上六": 6,
    "用九": 7, "用六": 7,
}
MARKER_RE = re.compile("|".join(LINE_MARKERS))

# 괘 머리: "䷀(乾下/乾上)". 기호는 못 믿고(정전 저본에 오류 3건) 괘체와 순서를 쓴다.
HEX_HEADER = re.compile(r"[䷀-䷿]?\(([^/()]{1,2})下/([^/()]{1,2})上\)")

PB_TAG = re.compile(r"<pb:[^>]*>")
# 권말 꼬리("原本周易本義卷一"). 그냥 두면 그 권 마지막 괘의 상효 본문에 붙는다.
JUAN_TAIL = re.compile(r"原本周易本義卷[一二三四五六七八九十]+\s*$")
TRIGRAM_ALIAS = {"兊": "兌", "兑": "兌", "㢲": "巽"}

# 卷 → 무엇이 실려 있는가
JUAN_ROLE = {
    "001": "gyeong",   # 周易上經 — 괘사·효사
    "002": "gyeong",   # 周易下經
    "003": "danjeon",  # 彖上傳
    "004": "danjeon",  # 彖下傳
    "005": "sang",     # 象上傳 — 대상전 + 소상전
    "006": "sang",     # 象下傳
}


def load_juan(num: str) -> str:
    """卷 하나를 읽어 판면 표시를 걷어낸 한 줄짜리 문자열로 만든다."""
    path = KANRIPO_DIR / f"KR1a0031_{num}.txt"
    lines = [
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("#")
    ]
    s = "".join(lines).replace("¶", "")
    s = PB_TAG.sub("", s)
    s = s.replace("　", "")  # 전각 들여쓰기는 의미를 갖지 않는다
    s = JUAN_TAIL.sub("", s)

    # 이체자 정규화를 **가르기 전에** 건다. 사고전서본은 初를 𥘉로 쓴 자리가 있고
    # (卷一에만 20회), 나중에 정규화하면 효 머리 매칭이 그 스무 자리를 놓친다.
    # 실제로 그렇게 했다가 초효 열 개가 통째로 빠졌다.
    return normalize(s)


def tokenize(seg: str):
    """괄호 깊이를 세며 (본문|주석) 토큰으로 가른다.

    중첩 괄호가 있어도 바깥 괄호 하나를 주석 한 덩이로 본다.
    """
    out = []
    buf = []
    depth = 0
    for ch in seg:
        if ch == "(":
            if depth == 0:
                if buf:
                    out.append(("text", "".join(buf)))
                    buf = []
            else:
                buf.append(ch)
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth <= 0:
                depth = 0
                if buf:
                    out.append(("note", "".join(buf)))
                    buf = []
            else:
                buf.append(ch)
        else:
            buf.append(ch)
    if buf:
        out.append(("note" if depth else "text", "".join(buf)))

    # 판면 행 끝에서 닫히고 다음 행에서 열린 주석을 다시 잇는다
    merged = []
    for kind, text in out:
        if merged and kind == "note" and merged[-1][0] == "note":
            merged[-1] = ("note", merged[-1][1] + text)
        else:
            merged.append((kind, text))

    # 割註의 행 나눔 표시를 지운다
    return [(k, t.replace("/", "") if k == "note" else t) for k, t in merged]


def split_hexagrams(raw: str):
    """卷 하나를 괘 단위로 가른다. 괘체 헤더가 경계다."""
    marks = list(HEX_HEADER.finditer(raw))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
        lower = TRIGRAM_ALIAS.get(m.group(1), m.group(1))
        upper = TRIGRAM_ALIAS.get(m.group(2), m.group(2))
        out.append({"lower": lower, "upper": upper, "body": raw[m.end():end]})
    return out


def split_units(tokens):
    """토큰을 괘사/효사 단위로 묶는다. 효 머리는 괄호 밖에서만 찾는다."""
    units = [{"marker": None, "text": "", "notes": []}]
    for kind, text in tokens:
        if kind == "note":
            units[-1]["notes"].append(text)
            continue
        pos = 0
        for m in MARKER_RE.finditer(text):
            units[-1]["text"] += text[pos:m.start()]
            units.append({"marker": m.group(0), "text": "", "notes": []})
            pos = m.start()
        units[-1]["text"] += text[pos:]
    return units


def parse_gyeong(nums=("001", "002")):
    """卷一·二 → 괘별 괘사·효사 본의."""
    result = []
    for num in nums:
        raw = load_juan(num)
        # 권 머리(欽定四庫全書 … 周易上經)는 첫 괘체 헤더 앞이라 자동으로 버려진다
        for hexa in split_hexagrams(raw):
            units = split_units(tokenize(hexa["body"]))
            guasa = units[0]

            # 효 번호는 **순서로** 매긴다. 효 머리를 그대로 믿지 않는다.
            #
            # 이 저본에는 판각 오자가 있다. 中孚 이효가 "九三"으로 찍혀 있는데,
            # 바로 뒤 割註가 "九二中孚…"로 시작해 스스로 이효임을 밝힌다.
            # 剝 오효(六四로 찍힘)와 巽 삼효(九二로 찍힘)도 같다.
            #
            # 순서로 매기는 것이 안전한 이유는 검산이 되기 때문이다 — 괘마다
            # 단위가 정확히 6개(건·곤은 용구·용육까지 7개)여야 하고, 전체가
            # 386이어야 한다. 하나라도 어긋나면 아래 경고가 뜬다.
            raw_lines = [u for u in units[1:] if u["marker"] in LINE_MARKERS]
            lines = []
            for pos, u in enumerate(raw_lines, start=1):
                번호 = 7 if u["marker"] in ("用九", "用六") else pos
                lines.append({
                    "line_number": 번호,
                    "marker": u["marker"],
                    "marker_mismatch": LINE_MARKERS[u["marker"]] != 번호,
                    "text": normalize(u["text"].strip()),
                    "commentary": [normalize(n) for n in u["notes"] if n.strip()],
                })
            if len(lines) not in (6, 7):
                print(f"  ! 효 단위가 {len(lines)}개인 괘가 있다 "
                      f"({hexa['lower']}下{hexa['upper']}上)", file=sys.stderr)
            result.append({
                "trigrams": {"lower": hexa["lower"], "upper": hexa["upper"]},
                "guasa": {
                    "text": normalize(guasa["text"].strip()),
                    "commentary": [normalize(n) for n in guasa["notes"] if n.strip()],
                },
                "lines": lines,
            })
    return result


HANJA_ONLY = re.compile(r"[^一-鿿㐀-䶵𠀀-𪛖]")
JEON_HEAD = re.compile(r"^(彖曰|象曰)")


def hanja(s: str) -> str:
    return HANJA_ONLY.sub("", s or "")


def attach_notes(raw: str, expected):
    """단전·상전 권에 붙은 割註를 기준 원문에 귀속시킨다.

    이 권들에는 괘 구분 표시가 없다. 전각 공백을 경계로 써봤지만 卷三은
    44개인데 실린 괘는 30개다 — 들여쓰기와 구분이 섞여 있어 못 믿는다.

    대신 **기준 데이터의 원문 순서로 정렬한다.** 단전·대상전·소상전은 이미
    `hexagrams_kanripo.json`에 있고 저본의 배열 순서와 같으므로, 괄호 밖
    본문에서 그 원문이 시작하는 자리를 차례로 찾으면 된다. 뒤따르는 주석은
    다음 원문이 시작하기 전까지 그 항목의 것이다.

    이문이 있어 완전 일치는 기대하지 않는다. 앞머리 8→6→4자로 줄여가며 찾고,
    그래도 못 찾으면 그 항목은 비워 둔다(조용히 엉뚱한 데 붙이지 않는다).
    """
    tokens = tokenize(raw)

    stream = []  # (글자, 토큰 인덱스)
    for i, (kind, text) in enumerate(tokens):
        if kind != "text":
            continue
        for ch in hanja(text):
            stream.append((ch, i))
    T = "".join(c for c, _ in stream)

    starts = []
    cursor = 0
    for item in expected:
        key = hanja(JEON_HEAD.sub("", item["text"]))
        pos = -1
        for probe in (key, key[:8], key[:6], key[:4]):
            if len(probe) < 3:
                break
            pos = T.find(probe, cursor)
            if pos >= 0:
                break
        if pos >= 0:
            cursor = pos + 1
        starts.append(stream[pos][1] if pos >= 0 else -1)

    # 주석 토큰을, 자기 앞에 있는 가장 가까운 원문에 붙인다
    notes = {i: [] for i in range(len(expected))}
    order = sorted((tok_i, i) for i, tok_i in enumerate(starts) if tok_i >= 0)
    for j, (kind, text) in enumerate(tokens):
        if kind != "note" or not text.strip():
            continue
        owner = None
        for tok_i, i in order:
            if tok_i <= j:
                owner = i
            else:
                break
        if owner is not None:
            notes[owner].append(normalize(text))

    matched = sum(1 for s in starts if s >= 0)
    return notes, matched


def parse_jeon(hexagrams, ref):
    """卷三~六 → 단전·대상전·소상전 본의를 괘별로 붙인다."""
    plans = [
        ("003", "danjeon", range(0, 30)),
        ("004", "danjeon", range(30, 64)),
        ("005", "sang", range(0, 30)),
        ("006", "sang", range(30, 64)),
    ]
    stats = {"danjeon": [0, 0], "daesang": [0, 0], "sosang": [0, 0]}

    for num, kind, idx in plans:
        expected = []
        for i in idx:
            r = ref[i]
            if kind == "danjeon":
                expected.append({"i": i, "slot": "danjeon", "line": None,
                                 "text": r["danjeon"]["original"]})
            else:
                expected.append({"i": i, "slot": "daesang", "line": None,
                                 "text": r["daesang"]["original"]})
                for ln in r["lines"]:
                    expected.append({"i": i, "slot": "sosang", "line": ln["position"],
                                     "text": ln.get("sosang") or ""})

        expected = [e for e in expected if hanja(e["text"])]
        notes, matched = attach_notes(load_juan(num), expected)

        for k, item in enumerate(expected):
            h = hexagrams[item["i"]]
            got = notes[k]
            if item["slot"] == "danjeon":
                h.setdefault("danjeon", {"commentary": []})["commentary"] = got
            elif item["slot"] == "daesang":
                h.setdefault("daesang", {"commentary": []})["commentary"] = got
            else:
                for ln in h["lines"]:
                    if ln["line_number"] == item["line"]:
                        ln["sosang_commentary"] = got
                        break
            stats[item["slot"]][0] += 1 if got else 0
            stats[item["slot"]][1] += 1

        print(f"  卷{num}: 원문 {matched}/{len(expected)} 정렬")

    return stats


def main():
    ap = argparse.ArgumentParser(description="주자 『본의』 파서 (原本周易本義)")
    ap.add_argument("-o", "--out", default="data/benui.json")
    ap.add_argument("--ref", default="data/hexagrams_kanripo.json",
                    help="정렬 기준 데이터 (단전·상전 원문을 여기서 가져온다)")
    args = ap.parse_args()

    hexagrams = parse_gyeong()
    ref = json.loads(Path(args.ref).read_text(encoding="utf-8"))
    for h, r in zip(hexagrams, ref):
        h["hexagram_id"] = r["hexagram_id"]
        h["name_hanja"] = r["name_hanja"]
    stats = parse_jeon(hexagrams, ref)
    for slot, (got, total) in stats.items():
        print(f"  {slot} 본의 {got}/{total}건")

    괘사주석 = sum(1 for h in hexagrams if h["guasa"]["commentary"])
    효 = sum(len(h["lines"]) for h in hexagrams)
    효주석 = sum(1 for h in hexagrams for ln in h["lines"] if ln["commentary"])

    print(f"괘 {len(hexagrams)}개 / 효 {효}개")
    print(f"  괘사 본의 {괘사주석}건, 효사 본의 {효주석}건")

    총 = (괘사주석 + 효주석
          + sum(len(h.get("danjeon", {}).get("commentary", [])) for h in hexagrams)
          + sum(len(h.get("daesang", {}).get("commentary", [])) for h in hexagrams)
          + sum(len(l.get("sosang_commentary", [])) for h in hexagrams for l in h["lines"]))
    print(f"  본의 주석 총 {총}건")

    out = Path(args.out)
    out.write_text(
        json.dumps(hexagrams, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"→ {out}")


if __name__ == "__main__":
    main()
