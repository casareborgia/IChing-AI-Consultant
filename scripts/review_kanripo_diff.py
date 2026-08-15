#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이관 손검토용 대조표를 만든다.

`verify_kanripo.py`는 "블록이 남아 있는가"를 코퍼스 단위로 센다. 그 방식은
블록 나누는 자리가 다르면 실제 차이와 경계 차이를 구별하지 못한다.

여기서는 **슬롯 단위로 1:1 정렬**한다. 괘사는 괘사끼리, 3효 소상은 3효
소상끼리. 자리가 고정되므로 나오는 차이는 전부 진짜 차이다.

차이를 두 갈래로 가른다:

  이체자 후보   같은 1자 치환이 여러 자리에서 반복된다. 정규화표에 넣으면
                기계적으로 사라진다. 사람이 볼 필요 없다.
  실질 이문     글자가 붙거나 빠지거나 순서가 바뀌었다. 조선 유통본과
                사고전서본이 실제로 다른 자리다. 사람이 판단해야 한다.

사용법:
    python scripts/review_kanripo_diff.py            # 요약만
    python scripts/review_kanripo_diff.py -o data/kanripo_review.md
"""

import argparse
import difflib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kanripo_variants import EQUIVALENT_PAIRS, GLYPH_VARIANTS, normalize  # noqa: E402

# 己/已/巳, 包/苞, 他/它 … 는 판각 혼동이라 대조에서 접기로 했었다. 그런데
# 원문에서는 그 접기가 실제 이문을 통째로 가렸다 — 革괘의 已日(날이 지난 뒤)과
# 巳日(간지의 巳日)은 뜻이 아예 다른데 대조표에 나오지도 않았다. 주석에서는
# 접어도 되지만 원문에서는 절대 접으면 안 된다.
FOLD = {b: a for a, b in EQUIVALENT_PAIRS}

NON_HANJA = re.compile(r"[^㐀-䶿一-鿿\U00020000-\U0002ffff]")

# 구 데이터의 교감 표기는 세 종류다. 한꺼번에 지우면 안 된다.
#
#   (A)[B]   저본의 A를 B로 바로잡음. B가 본문이다. 12건
#            예) 天道下(濟)[際]而光明 → 際
#   [一作X]  다른 판본은 X로 되어 있다는 주기. 본문이 아니다. 514건
#   (A)      단독 괄호. 이독 표시인데 사고전서본과의 관계가 일정하지 않다.
#            (何)天之衢는 신본에 何가 있고, 輿說(脫)輹은 신본에 脫이 없다.
#            9건뿐이라 지우지 않고 남긴 뒤 따로 뽑아 사람이 본다.
#
# 처음에 셋을 다 지웠더니 (A)[B]의 B가 사라져 없던 이문이 여럿 생겼다.
COLLATION_PAIR = re.compile(r"[(（]([^)）]{1,10})[)）]\s*\[([^\]]{1,12})\]")
COLLATION_NOTE = re.compile(r"\[[^\]]{1,20}\]")
COLLATION_SOLO = re.compile(r"[(（]([^)）]{1,20})[)）]")
# 구 데이터에 닫는 괄호를 ]가 아니라 [로 찍은 자리가 2군데 있다.
#   如車輿脫去[一有其字[輪輹   (26 大畜)
# 주기는 모두 一(一作·一无·一有·一更)로 시작하므로 좁게 잡아 함께 걷는다.
COLLATION_BROKEN = re.compile(r"\[一[^\[\]]{0,15}[\]\[]")

# 이체자 후보로 볼 최소 반복 횟수. 1회짜리는 실질 이문일 수 있어 사람에게 넘긴다.
VARIANT_MIN_HITS = 3


def norm(text: str, fold: bool = True) -> str:
    """교감 표기를 정리하고, 정규화한 뒤, 한자만 남긴다.

    fold=False면 EQUIVALENT_PAIRS를 접지 않는다. 원문 슬롯에 쓴다.

    순서가 다 중요하다. (A)[B]를 [一作X]보다 먼저 처리하지 않으면 B가 주기로
    오인돼 지워진다. 교감을 먼저 걷지 않으면 `卦下之[一无之字]辭`가
    `卦下之一无之字辭`로 남아 없던 이문이 생긴다. 정규화를 한자 필터보다
    먼저 해야 확장영역 글자(㢲·𧰼)가 살아남는다.
    """
    text = COLLATION_PAIR.sub(r"\2", text)
    text = COLLATION_BROKEN.sub("", text)
    text = COLLATION_NOTE.sub("", text)
    text = COLLATION_SOLO.sub(r"\1", text)
    text = normalize(text)
    if fold:
        text = "".join(FOLD.get(c, c) for c in text)
    return NON_HANJA.sub("", text)


def solo_parens(hexes: list) -> list[tuple[int, str, str, str]]:
    """단독 괄호 교감이 붙은 자리를 모은다. 사람이 직접 봐야 하는 9건."""
    found = []
    for h in hexes:
        for slot, text in list(slots(h)) + [("주석전량", all_commentary(h))]:
            for m in COLLATION_SOLO.finditer(text):
                if COLLATION_PAIR.search(text[m.start():m.end() + 14]):
                    continue                       # (A)[B] 쌍의 앞짝은 제외
                found.append((h["hexagram_id"], h["name_hanja"], slot,
                              text[max(0, m.start() - 14):m.end() + 14]))
    return found


def slots(hexa: dict):
    """원문 슬롯. 자리가 고정돼 1:1로 맞물린다."""
    for key, label in (("guasa", "괘사"), ("danjeon", "단전"),
                       ("daesang", "대상"), ("munon", "문언")):
        yield f"{label}·원문", hexa[key]["original"]
    for ln in hexa["lines"]:
        yield f"효{ln['position']}·원문", ln["original"]
        yield f"효{ln['position']}소상·원문", ln["sosang"]


def all_commentary(hexa: dict) -> str:
    """괘 하나의 주석 전량.

    주석은 슬롯 단위로 비교하면 안 된다. 기존 데이터가 블록을 다른 자리에
    넣어둔 곳이 많아서다 — 序卦 해설은 앞 괘 끝에 붙어 있고, 乾은 대상·소상
    주석이 전부 danjeon.commentary에 뭉쳐 있다. 슬롯끼리 맞대면 그 청킹
    차이가 전부 '이문'으로 잡혀 실제 차이가 묻힌다. 괘 단위로 묶으면
    남는 것은 글자 차이뿐이다.
    """
    out = list(hexa.get("intro") or [])        # 序卦 해설도 정전 주석이다
    out += [c for k in ("guasa", "danjeon", "daesang", "munon")
            for c in hexa[k]["commentary"]]
    out += [c for ln in hexa["lines"]
            for c in ln["commentary"] + ln["sosang_commentary"]]
    return "".join(out)


def internal_evidence(hexa_new: dict, hexa_old: dict,
                      left: str, seg_old: str, seg_new: str, right: str) -> str:
    """정전 주석이 어느 쪽 글자를 쓰는지 찾는다. 원문 판정의 결정적 증거다.

    통행본으로 판정하면 틀린다. 정이천은 저본을 고쳐 읽고 그 위에서 해석을
    전개한 자리가 여럿이다:

        15 謙 단전  주석에 "濟當爲際" — 濟를 際로 고쳐 읽으라 명시
        53 漸 상구  "安定胡公以陸爲逵" 뒤로 逵(구름길)를 전제로 풀이를 이어감
        27 頤 육사  주석이 "耽耽然如虎視"라 써서 저본이 耽耽임을 드러냄

    셋 다 통행본은 濟·陸·眈眈인데 정전 저본은 際·逵·耽耽이다.

    주석은 표제어를 통째로 옮기지 않고 짧게 집어 쓰므로, 차이 나는 조각에
    좌우 문맥을 조금씩 붙여가며 한쪽만 걸리는 가장 긴 조합을 찾는다.
    원문 슬롯에만 쓸 것 — 주석 자체를 비교하는 자리에서는 증거가 되지 않는다.
    """
    comm = NON_HANJA.sub("", normalize(all_commentary(hexa_new))
                         + normalize(all_commentary(hexa_old)))
    cands = []
    for lk in range(3, -1, -1):
        for rk in range(3, -1, -1):
            a = left[len(left) - lk:] + seg_old + right[:rk] if lk else seg_old + right[:rk]
            b = left[len(left) - lk:] + seg_new + right[:rk] if lk else seg_new + right[:rk]
            if len(a) >= 2 and len(b) >= 2 and a != b:
                cands.append((lk + rk, a, b))
    # 판정하지 않는다. 짧은 조각은 엉뚱한 문장에서도 걸린다 —
    # 34 大壯의 `壯君子`는 소상 인용이 아니라 `以行其壯君子之大壯者`에서 걸렸고
    # 62 小過의 `小者過`는 `小者過其常也`에서 걸렸다. 어느 쪽 표기가 주석에
    # 나타나는지와 그 주변 문장을 함께 보여주고, 인용인지 여부는 사람이 본다.
    for _, a, b in sorted(cands, key=lambda c: -c[0]):
        hit_o, hit_n = a in comm, b in comm
        if hit_o == hit_n:
            continue
        side, key = ("구본", a) if hit_o else ("신본", b)
        i = comm.find(key)
        mark = "" if len(key) >= 4 else " ※짧음"
        return f"{side}형 `{key}`{mark} … {comm[max(0, i - 16):i + len(key) + 16]}"
    if any(a in comm and b in comm for _, a, b in cands):
        return "양쪽 다 나타남 — 읽어봐야 함"
    return "주석에 근거 없음"


def classify(old_txt: str, new_txt: str, whole_old: str, whole_new: str) -> str:
    """검토가 필요없는 차이를 걸러낸다.

    序卦이동 — 기존 데이터는 각 괘의 서두 序卦 해설을 **앞 괘 끝에** 붙여놨다
        (60/63). 파서가 제자리로 옮기므로 앞 괘에서는 통째로 빠지고 해당
        괘에서는 통째로 들어온 것으로 잡힌다. 고친 결과다.
        괘명으로 판정하면 안 된다 — 본문은 恒·豊·無妄인데 이름표는 恆·豐·无妄
        이라 이체자에서 샌다. 머리 8자 안에 序卦가 있는지로 본다.

    재배치 — 같은 괘 안에서 자리만 바뀐 것. 기존 데이터는 소상 주석을 단전
        주석 뒤에 몰아놨고 파서는 각 효 옆에 붙인다. 한쪽에만 있는 조각이
        상대편 괘 전문에 그대로 있으면 글자는 하나도 안 잃은 것이다.
    """
    # 한쪽이 비었거나, 한쪽이 몇 글자뿐이고 반대쪽이 큰 덩어리인 경우를 같이 본다.
    # 블록 경계가 어긋나면 순수한 삽입/삭제가 `replace`로 보고되기 때문이다:
    #   [41 損] 구 '減' → 신 239자   [38 睽] 구 77자 → 신 '矣'
    small, large = sorted((old_txt, new_txt), key=len)
    one_sided = len(small) <= 3 and len(large) >= 8
    if not one_sided:
        return "이문"
    if "序卦" in large[:8]:
        return "序卦이동"
    counterpart = whole_new if large is old_txt else whole_old
    if large in counterpart:
        return "재배치"
    return "이문"


def compare(old: list, new: list):
    subs = Counter()                       # (구, 신) -> 횟수
    sub_where = defaultdict(list)
    findings = []                          # 실질 이문
    o_by = {h["hexagram_id"]: h for h in old}
    n_by = {h["hexagram_id"]: h for h in new}
    names = {h["hexagram_id"]: h["name_hanja"] for h in new}

    def walk(hid, name, slot, a, b, whole_o, whole_n):
        is_orig = slot.endswith("원문")

        def evidence(i1, i2, x, y):
            if not is_orig:
                return ""      # 주석끼리 비교하는 자리에서는 증거가 되지 않는다
            return internal_evidence(n_by[hid], o_by[hid],
                                     a[max(0, i1 - 6):i1], x, y, a[i2:i2 + 6])

        if a == b:
            return
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, a, b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            x, y = a[i1:i2], b[j1:j2]
            if tag == "replace" and len(x) == 1 == len(y):
                subs[(x, y)] += 1
                # 위치 라벨만으로는 판정할 수 없다. 뜻이 갈리는 쌍(君/若, 以/而)은
                # 앞뒤를 봐야 어느 쪽이 맞는지 알 수 있으므로 문맥을 함께 남긴다.
                sub_where[(x, y)].append({
                    "at": f"{hid}{name} {slot}",
                    "ctx": a[max(0, i1 - 20):i1] + f"⟦{x}→{y}⟧" + a[i2:i2 + 20],
                    "ev": evidence(i1, i2, x, y),
                })
            else:
                findings.append({
                    "hid": hid, "name": name, "slot": slot, "tag": tag,
                    "old": x, "new": y, "kind": classify(x, y, whole_o, whole_n),
                    "ctx": a[max(0, i1 - 12):i1] + "⟦" + x + "⟧" + a[i2:i2 + 12],
                    "ev": evidence(i1, i2, x, y),
                })

    for hid in sorted(o_by):
        name = n_by[hid]["name_hanja"]
        o_slots, n_slots = dict(slots(o_by[hid])), dict(slots(n_by[hid]))
        # 재배치 판정은 "괘 전문"을 기준으로 한다. 앞뒤 괘의 序卦 해설이
        # 오가므로 이웃 괘까지 넣어야 이동분을 놓치지 않는다.
        span = [h for h in (hid - 1, hid, hid + 1) if h in o_by]
        whole_o = norm("".join(all_commentary(o_by[h]) for h in span))
        whole_n = norm("".join(all_commentary(n_by[h]) for h in span))
        for slot in o_slots:   # 원문은 접지 않는다
            walk(hid, name, slot,
                 norm(o_slots[slot], fold=False), norm(n_slots.get(slot, ""), fold=False),
                 whole_o, whole_n)
        walk(hid, name, "주석전량",
             norm(all_commentary(o_by[hid])), norm(all_commentary(n_by[hid])),
             whole_o, whole_n)
    return subs, sub_where, findings


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="이관 손검토 대조표")
    ap.add_argument("--old", type=Path, default=root / "data" / "hexagrams.json")
    ap.add_argument("--new", type=Path, default=root / "data" / "hexagrams_kanripo.json")
    ap.add_argument("-o", "--out", type=Path, help="마크다운 대조표 저장 위치")
    args = ap.parse_args()

    old = json.loads(args.old.read_text(encoding="utf-8"))
    new = json.loads(args.new.read_text(encoding="utf-8"))
    subs, where, findings = compare(old, new)
    solos = solo_parens(old)

    # 이미 판정이 끝난 쌍은 후보에서 뺀다. GLYPH_VARIANTS는 정규화로 사라지고,
    # EQUIVALENT_PAIRS는 "건드리지 않기로" 결정한 쌍이다.
    known = set(GLYPH_VARIANTS.items()) | {(v, k) for k, v in GLYPH_VARIANTS.items()}
    known |= set(EQUIVALENT_PAIRS) | {(b, a) for a, b in EQUIVALENT_PAIRS}
    # 한쪽이 확장A(㐀-䶿)나 확장B 글자인 쌍은 횟수와 무관하게 이체자로 본다.
    # 사고전서본이 강희자전 이전 판각체를 쓴 탓이라 뜻이 갈리는 경우가 없다.
    def ext_glyph(pair) -> bool:
        return any(ch >= "㐀" and (ch <= "䶿" or ch > "鿿") for ch in pair)

    cand = [(p, n) for p, n in subs.most_common()
            if p not in known and (n >= VARIANT_MIN_HITS or ext_glyph(p))]
    onceoff = [(p, n) for p, n in subs.most_common()
               if p not in known and n < VARIANT_MIN_HITS and not ext_glyph(p)]

    print(f"슬롯 1:1 대조 — 1자 치환 {sum(subs.values())}회 / 실질 이문 {len(findings)}건")
    print(f"\n▶ 이체자 후보 ({VARIANT_MIN_HITS}회 이상 반복, 표에 없는 것) {len(cand)}종")
    for (x, y), n in cand[:40]:
        print(f"    {x} → {y}  ×{n}")
    print(f"\n▶ 1~2회짜리 1자 차이 {len(onceoff)}종 — 이문일 수 있어 사람 확인")
    moved = [f for f in findings if f["kind"] != "이문"]
    real = [f for f in findings if f["kind"] == "이문"]
    by_kind = Counter(f["kind"] for f in moved)
    print(f"\n▶ 자리 이동 {len(moved)}건 — 고친 결과다. 검토 불필요"
          f"  ({', '.join(f'{k} {v}' for k, v in by_kind.most_common())})")
    print(f"▶ 실질 이문 {len(real)}건")
    orig = [f for f in real if f["slot"].endswith("원문")]
    comm = [f for f in real if not f["slot"].endswith("원문")]
    for label, group in (("원문", orig), ("주석", comm)):
        size = Counter("1~3자" if max(len(f["old"]), len(f["new"])) <= 3
                       else "4~10자" if max(len(f["old"]), len(f["new"])) <= 10
                       else "11자 이상" for f in group)
        print(f"    {label} {len(group):>3}건 — " +
              " / ".join(f"{k} {v}" for k, v in size.most_common()))
    print(f"▶ 단독 괄호 교감 {len(solos)}건 — 구본이 괄호로 묶은 자리. 사람이 판단")
    findings = real

    if not args.out:
        return 0

    lines = ["# Kanripo 이관 — 손검토 대조표", "",
             f"슬롯 1:1 정렬. 구={args.old.name}, 신={args.new.name}", "",
             "## 1. 이체자 후보 — 정규화표에 넣으면 사라진다", "",
             "| 구 | 신 | 횟수 | 예시 위치 |", "|---|---|---|---|"]
    for (x, y), n in cand:
        at = ", ".join(w["at"] for w in where[(x, y)][:3])
        lines.append(f"| {x} | {y} | {n} | {at} |")

    lines += ["", "## 2. 1자 차이 — 문맥을 보고 판정", "",
              "발생 자리마다 한 행이다. `⟦구→신⟧` 표시 앞뒤가 실제 문장이다.",
              "글자만 보고는 판정할 수 없다 — 같은 쌍이라도 자리마다 답이 다르다.",
              "원문 자리는 **정전 주석이 어느 표기를 쓰는지**를 함께 뽑았다.",
              "통행본이 아니라 정전 저본이 기준이다 — 정이천이 저본을 고쳐 읽은",
              "자리가 있다(15 謙 `濟當爲際`, 27 頤 `耽耽然如虎視`).",
              "※짧음 표시는 2~3자로 걸린 것이라 우연일 수 있으니 문장을 볼 것.",
              "", "| 구 | 신 | 위치 | 문맥 | 정전 주석 근거 |", "|---|---|---|---|---|"]
    for (x, y), n in onceoff:
        for w in where[(x, y)]:
            lines.append(f"| {x} | {y} | {w['at']} | `{w['ctx']}` | {w.get('ev','')} |")

    lines += ["", "## 3. 단독 괄호 교감 — 구본이 괄호로 묶은 자리", "",
              "사고전서본과의 관계가 일정하지 않다. 신본에 있는 것도 없는 것도 있다.",
              "", "| 괘 | 자리 | 문맥 |", "|---|---|---|"]
    for hid, nm, slot, ctx in solos:
        lines.append(f"| {hid} {nm} | {slot} | `{ctx}` |")

    lines += ["", "## 4. 실질 이문 — 판단 필요", "",
              "| 괘 | 자리 | 종류 | 구 | 신 | 문맥 | 정전 주석 근거 |",
              "|---|---|---|---|---|---|---|"]
    for f in sorted(findings, key=lambda f: (-max(len(f["old"]), len(f["new"])), f["hid"])):
        o = f["old"][:40] or "—"
        n = f["new"][:40] or "—"
        lines.append(f"| {f['hid']} {f['name']} | {f['slot']} | {f['tag']} | "
                     f"`{o}` | `{n}` | `{f['ctx'][:50]}` | {f.get('ev','')} |")

    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
