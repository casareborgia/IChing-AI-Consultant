#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kanripo 주역 원전 파서 — 경문(KR1a0001) + 정전(KR1a0016) → hexagrams.json 구조.

`parse_jeonguiu.py`(현토본 파서)를 대체한다. 산출 스키마는 같으므로 하위
파이프라인(build_rag_chunks / translate / seed_hexagrams)은 그대로 쓴다.

사용법:
    python scripts/fetch_kanripo.py
    python scripts/parse_kanripo.py -o data/hexagrams_kanripo.json

--------------------------------------------------------------------------
현토본 파서와 달라진 점

1. 괘 분할을 **파일 순서와 괘체(卦體)로** 한다. 괘 기호(䷀…)는 못 믿는다.
   현재 hexagrams.json에 3건(14 大有·15 謙·30 離), Kanripo 정전에 3건
   (31 咸·48 井·63 旣濟) 오류가 있다. 서로 다른 자리라 한쪽만 믿을 수 없다.
   대신 경문 파일은 001~064가 서괘 순서대로고, 각 파일과 정전 헤더가
   똑같은 괘체 문자열을 갖는다. 그 둘을 맞대어 검증한다.

2. 경문과 주석을 **들여쓰기로** 가른다. 정전 사고전서본은 경문을 왼쪽에
   붙이고 주석을 전각 공백으로 들여쓴다. 현토본에서 레이아웃으로 추론하던
   것을 여기서는 그냥 읽으면 된다.

3. 괘 서두의 序卦 해설을 제자리에 넣는다. 현토본 파서는 이걸 **앞 괘의
   마지막 블록에** 붙였다 — 63괘 중 60괘가 그렇고, 자기 序卦 해설을 제대로
   가진 괘는 0개였다. RAG에서 屯의 도입 해설이 坤으로 검색되던 원인이다.
--------------------------------------------------------------------------
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kanripo_variants import normalize  # noqa: E402

# ── 효(爻) 위치 마커 ───────────────────────────────────────────────────
LINE_MARKERS = {
    "初九": 1, "初六": 1, "九二": 2, "六二": 2, "九三": 3, "六三": 3,
    "九四": 4, "六四": 4, "九五": 5, "六五": 5, "上九": 6, "上六": 6,
    "用九": 7, "用六": 7,
}
MARKER_ALT = "|".join(LINE_MARKERS)

# 경문(tls본)은 효 머리에 ：또는 、를 찍는다. 문언의 "初九曰、"과 구분된다.
GYEONG_SPLIT = re.compile(
    rf"(《彖》曰：|《象》曰：|《文言》曰：|(?:{MARKER_ALT})[：、])"
)

# 정전 괘 머리: "䷂(震下/坎上)" — 기호는 못 믿고 괘체만 쓴다.
JEON_HEADER = re.compile(r"([䷀-䷿])\(([^/]+)下/([^)]+)上\)")

# 팔괘 이체 표기
TRIGRAM_ALIAS = {"兊": "兌", "兑": "兌", "㢲": "巽"}

HANJA_ONLY = re.compile(r"[^一-鿿]")

PB_TAG = re.compile(r"<pb[^>]*>")
GYEONG_TITLE = re.compile(r"^\*\*\s*《(.+?)第")
GYEONG_BODY_HEAD = re.compile(r"^([䷀-䷿])(.+?)下(.+?)上$")

# 정전 본문이 아닌 판심(版心)·간기 줄
JEON_BOILERPLATE = ("欽定四庫全書", "伊川易傳卷", "周易上經", "周易下經", "宋　程子")


def clean_trigram(name: str) -> str:
    return TRIGRAM_ALIAS.get(name.strip(), name.strip())


# ══ 1. 경문 (KR1a0001) ═══════════════════════════════════════════════

def load_gyeongmun(src: Path) -> list[dict]:
    """001~064 파일을 서괘 순서대로 읽어 괘별 원문 구조를 만든다."""
    out = []
    for n in range(1, 65):
        path = src / f"KR1a0001_{n:03d}.txt"
        if not path.exists():
            raise FileNotFoundError(f"경문 파일 없음: {path}")
        out.append(_parse_gyeongmun_file(path.read_text(encoding="utf-8"), n))
    return out


def _strip_name_marker(guasa: str, name: str) -> str:
    """괘사 머리의 《괘명》 표기를 정리한다.

    tls본은 괘사 앞에 괘명을 《》로 표시한다 — 《屯》元亨，利貞。
    괘사 자체가 괘명으로 시작하는 세 괘(履·否·同人)에서는 이게 겹쳐
    《履》履虎尾… 처럼 두 번 나온다. 겹치면 표기를 떼고, 아니면 괄호만
    벗겨 기존 데이터 관례(`屯 元亨…`)에 맞춘다.
    """
    if not name or not guasa.startswith(f"《{name}》"):
        return guasa.strip()
    rest = guasa[len(name) + 2:].lstrip("：、 ")
    return (rest if rest.startswith(name) else f"{name} {rest}").strip()


def _parse_gyeongmun_file(raw: str, hexagram_id: int) -> dict:
    name = lower = upper = None
    body_lines = []
    for line in raw.split("\n"):
        line = PB_TAG.sub("", line).replace("¶", "").strip()
        if not line or line.startswith("#"):
            continue
        m = GYEONG_TITLE.match(line)
        if m:
            name = m.group(1)
            continue
        m = GYEONG_BODY_HEAD.match(line)
        if m and lower is None:
            lower, upper = clean_trigram(m.group(2)), clean_trigram(m.group(3))
            continue
        body_lines.append(line)

    body = "".join(body_lines)
    parts = GYEONG_SPLIT.split(body)
    parts[0] = _strip_name_marker(parts[0], name)

    hexa = {
        "hexagram_id": hexagram_id,
        "name_hanja": name,
        # 기호는 원본 대신 서괘 번호로 다시 만든다. 원본 오류를 물려받지 않는다.
        "symbol": chr(0x4DC0 + hexagram_id - 1),
        "trigrams": {"lower": lower, "upper": upper},
        "notes": [],                 # 기존 스키마와 맞춘다 (현재 전 괘 비어 있음)
        # 괘 서두의 序卦 해설. 괘사를 푸는 글이 아니라 "이 괘가 왜 앞 괘 다음에
        # 오는가"와 괘 전체 개관이라 괘사 주석과 성격이 다르다. 섞어두면 나중에
        # 가려낼 수 없고, 번역 배치가 괘사 주석 대신 이걸 문맥으로 집어간다.
        "intro": [],
        "guasa": {"original": parts[0].strip(), "commentary": []},
        "danjeon": {"original": "", "commentary": []},
        "daesang": {"original": "", "commentary": []},
        "munon": {"original": "", "commentary": []},
        "lines": [],
    }

    lines: dict[int, dict] = {}
    cur_pos = None
    last_pos = 0
    section = "guasa"
    tail = None      # 인용 안에서 잘못 끊긴 조각을 되붙일 자리

    def append_tail(text: str) -> None:
        """효 마커가 인용문 안에 있었을 때 본문으로 되돌린다."""
        if tail is None:
            return
        holder, key = tail
        holder[key] = (holder[key] + text).strip()

    for marker, chunk in zip(parts[1::2], parts[2::2]):
        chunk = chunk.strip()
        if marker == "《彖》曰：":
            hexa["danjeon"]["original"] = "彖曰：" + chunk
            section, tail = "danjeon", (hexa["danjeon"], "original")
        elif marker == "《文言》曰：":
            hexa["munon"]["original"] = "文言曰：" + chunk
            section, tail = "munon", (hexa["munon"], "original")
        elif marker == "《象》曰：":
            if not hexa["daesang"]["original"]:
                hexa["daesang"]["original"] = "象曰：" + chunk
                section, tail = "daesang", (hexa["daesang"], "original")
            else:                                   # 효 뒤에 붙는 象曰 = 소상
                lines[cur_pos]["sosang"] = "象曰：" + chunk
                section, tail = "sosang", (lines[cur_pos], "sosang")
        else:
            # 효 마커. 단, 소상·문언이 효사를 되인용할 때도 같은 글자가 나온다:
            #   比 초효 소상  《象》曰：《比》之初六、「有它吉」也。
            #   中孚 초효 소상 《象》曰：「初九、虞吉」、志未變也。
            # 효 순서는 반드시 증가하므로, 이미 지난 자리면 인용으로 보고
            # 본문에 되붙인다.
            pos = LINE_MARKERS[marker[:2]]
            if pos <= last_pos:
                append_tail(marker + chunk)
                continue
            cur_pos = last_pos = pos
            lines[pos] = {"position": pos, "original": marker[:2] + " " + chunk,
                          "commentary": [], "sosang": "",
                          "sosang_commentary": []}
            section, tail = "line", (lines[pos], "original")

    # 乾·坤은 소상이 대상과 한 덩어리로 들어간다. 「효사」 인용 단위로 가른다.
    # 문장 끝(。) 뒤의 「에서만 끊는다. 소상 안에 인용이 또 나오기 때문이다:
    #   「飛龍在天」、「大人」造也。   「或躍在淵」、進「无咎」也。
    # 모든 「에서 끊으면 조각이 효 수보다 많아져 한 칸씩 밀린다.
    if hexa["daesang"]["original"] and "「" in hexa["daesang"]["original"]:
        head, *quoted = re.split(r"(?<=。)(?=「)", hexa["daesang"]["original"])
        if len(quoted) == len(lines):
            hexa["daesang"]["original"] = head.strip()
            for pos, text in zip(sorted(lines), quoted):
                lines[pos]["sosang"] = text.strip()

    hexa["lines"] = [lines[p] for p in sorted(lines)]
    return hexa


# ══ 2. 정전 (KR1a0016) ═══════════════════════════════════════════════

def load_jeongjeon(src: Path) -> list[list[tuple[str, str, str]]]:
    """괘별 (표제어, 주석, 괘체) 목록. 표제어가 빈 것은 괘 서두 해설."""
    raw = "".join((src / f"KR1a0016_{v:03d}.txt").read_text(encoding="utf-8")
                  for v in range(1, 5))
    raw = PB_TAG.sub("", raw)

    heads = list(JEON_HEADER.finditer(raw))
    if len(heads) != 64:
        raise ValueError(f"정전 괘 머리 {len(heads)}개 (64 기대). 원본 확인 필요")

    segments = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
        trig = (clean_trigram(h.group(2)), clean_trigram(h.group(3)))
        segments.append(_parse_jeon_segment(raw[h.end():end], trig))
    return segments


def _parse_jeon_segment(seg: str, trig: tuple[str, str]) -> dict:
    """들여쓰기로 표제어/주석을 가르고 (표제어, 주석) 쌍으로 묶는다."""
    pairs: list[tuple[str, list[str]]] = []
    lemma_buf, comm_buf, mode = [], [], None

    def flush():
        nonlocal lemma_buf, comm_buf
        if lemma_buf or comm_buf:
            pairs.append(("".join(lemma_buf), "".join(comm_buf)))
        lemma_buf, comm_buf = [], []

    for line in seg.split("\n"):
        line = line.replace("¶", "")
        if not line.strip():
            continue
        indented = line.startswith("　")
        text = line.strip("　").strip()
        if any(b in text for b in JEON_BOILERPLATE):
            continue
        if indented:
            comm_buf.append(text)
            mode = "c"
        else:
            if mode == "c":          # 주석이 끝나고 새 표제어 → 앞 쌍을 닫는다
                flush()
            lemma_buf.append(text)
            mode = "o"
    flush()
    return {"trigrams": {"lower": trig[0], "upper": trig[1]}, "pairs": pairs}


def attach_commentary(hexa: dict, seg: dict) -> list[str]:
    """정전 주석을 경문 구조의 제자리에 붙인다. 경고 목록을 돌려준다."""
    warn = []
    by_pos = {ln["position"]: ln for ln in hexa["lines"]}
    section, cur_pos = "guasa", None
    daesang_done = False
    special = hexa["hexagram_id"] in (1, 2)     # 乾·坤은 소상 표제어에 象曰이 없다
    bare_sosang = 0

    # 대상을 글자 그대로 알아두고 표제어와 맞댄다. 사고전서본은 彖曰을 象曰로
    # 잘못 새긴 데가 있다 — 蠱는 "象曰蠱剛上而柔下", 中孚는 "象曰中孚柔在內".
    # 글자만 보면 둘 다 대상이 되어 진짜 대상이 소상으로 밀린다.
    daesang_key = HANJA_ONLY.sub("", normalize(hexa["daesang"]["original"]))
    daesang_key = daesang_key[2:12] if daesang_key.startswith("象曰") else daesang_key[:10]

    for lemma, comm in seg["pairs"]:
        lemma_n = normalize(lemma)
        comm = normalize(comm).strip()

        if not lemma:                            # 괘 서두 序卦 해설
            if comm:
                hexa["intro"].append(comm)
            continue

        if lemma_n.startswith("文言曰"):
            section = "munon"
        elif lemma_n.startswith("彖曰") or lemma_n.startswith("象曰"):
            key = HANJA_ONLY.sub("", lemma_n)[2:12]
            is_daesang = bool(daesang_key) and key.startswith(daesang_key[:8])
            if not daesang_done and is_daesang:
                section, daesang_done = "daesang", True
            elif not daesang_done and section in ("guasa", "danjeon"):
                section = "danjeon"
            else:
                section = "sosang"
        elif lemma_n[:2] in LINE_MARKERS:
            cur_pos = LINE_MARKERS[lemma_n[:2]]
            section = "line"
            if cur_pos not in by_pos:
                warn.append(f"효 {cur_pos} 자리가 경문에 없다: {lemma_n[:12]}")
                continue
        elif special and daesang_done and section in ("daesang", "sosang"):
            # 乾·坤: 대상 뒤로 이어지는 맨 표제어는 순서대로 소상이다
            bare_sosang += 1
            cur_pos, section = bare_sosang, "sosang"
            if cur_pos not in by_pos:
                warn.append(f"소상 {cur_pos} 자리 없음")
                continue
        # else: 표제어가 앞 절의 연장(彖의 '動乎險中' 같은 것) → section 유지

        if not comm:
            continue
        if section in ("guasa", "danjeon", "daesang", "munon"):
            hexa[section]["commentary"].append(comm)
        elif section == "line" and cur_pos in by_pos:
            by_pos[cur_pos]["commentary"].append(comm)
        elif section == "sosang" and cur_pos in by_pos:
            by_pos[cur_pos]["sosang_commentary"].append(comm)
        else:
            warn.append(f"버린 주석({section}/{cur_pos}): {comm[:24]}")
    return warn


# ══ 3. 검증 ═══════════════════════════════════════════════════════════

def validate(hexes: list[dict], segs: list[dict]) -> list[str]:
    problems = []
    for hexa, seg in zip(hexes, segs):
        hid, nm = hexa["hexagram_id"], hexa["name_hanja"]
        g, j = hexa["trigrams"], seg["trigrams"]
        if g != j:
            problems.append(f"[{hid} {nm}] 괘체 불일치 경문{g} vs 정전{j}")
        if not hexa["guasa"]["original"]:
            problems.append(f"[{hid} {nm}] 괘사 원문 없음")
        if not hexa["danjeon"]["original"]:
            problems.append(f"[{hid} {nm}] 단전 원문 없음")
        if not hexa["daesang"]["original"]:
            problems.append(f"[{hid} {nm}] 대상 원문 없음")
        want = 7 if hid in (1, 2) else 6
        if len(hexa["lines"]) != want:
            problems.append(f"[{hid} {nm}] 효 {len(hexa['lines'])}개 ({want} 기대)")
        for ln in hexa["lines"]:
            if not ln["sosang"]:
                problems.append(f"[{hid} {nm}] 효{ln['position']} 소상 없음")
        if not hexa["guasa"]["commentary"]:
            problems.append(f"[{hid} {nm}] 괘사 주석 없음")
    return problems


def stats(hexes: list[dict]) -> dict:
    n_comm = n_orig = 0
    for h in hexes:
        for k in ("guasa", "danjeon", "daesang", "munon"):
            n_orig += 1 if h[k]["original"] else 0
            n_comm += len(h[k]["commentary"])
        for ln in h["lines"]:
            n_orig += (1 if ln["original"] else 0) + (1 if ln["sosang"] else 0)
            n_comm += len(ln["commentary"]) + len(ln["sosang_commentary"])
    return {"원문 블록": n_orig, "주석 블록": n_comm,
            "효": sum(len(h["lines"]) for h in hexes)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Kanripo 주역 파서")
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("-s", "--src", type=Path, default=root / "data" / "kanripo")
    ap.add_argument("-o", "--out", type=Path,
                    default=root / "data" / "hexagrams_kanripo.json")
    ap.add_argument("--strict", action="store_true",
                    help="검증에 걸리면 저장하지 않고 종료한다")
    args = ap.parse_args()

    hexes = load_gyeongmun(args.src)
    segs = load_jeongjeon(args.src)

    warns = []
    for hexa, seg in zip(hexes, segs):
        for w in attach_commentary(hexa, seg):
            warns.append(f"[{hexa['hexagram_id']} {hexa['name_hanja']}] {w}")

    # 원문도 자형을 맞춰 둔다 (경문 tls본과 정전 WYG본의 자형이 다르다)
    for h in hexes:
        for k in ("guasa", "danjeon", "daesang", "munon"):
            h[k]["original"] = normalize(h[k]["original"])
        for ln in h["lines"]:
            ln["original"] = normalize(ln["original"])
            ln["sosang"] = normalize(ln["sosang"])

    problems = validate(hexes, segs)

    print("── 집계 ──")
    for k, v in stats(hexes).items():
        print(f"  {k}: {v:,}")
    print(f"\n── 검증: 문제 {len(problems)}건, 경고 {len(warns)}건 ──")
    for p in problems[:30]:
        print("  ✗", p)
    if len(problems) > 30:
        print(f"  … 외 {len(problems)-30}건")
    for w in warns[:15]:
        print("  !", w)
    if len(warns) > 15:
        print(f"  … 외 {len(warns)-15}건")

    if problems and args.strict:
        print("\n--strict: 저장하지 않고 종료한다.")
        return 1

    args.out.write_text(
        json.dumps(hexes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
