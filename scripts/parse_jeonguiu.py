#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
주역전의(周易傳義) 파서
- 구글 문서에서 내보낸 텍스트를 괘/효 단위 구조화 JSON으로 변환한다.
- 원문(괘사/효사/단전/상전/문언)과 정전(程傳) 주석을 분리한다.

사용법:
    python parse_jeonguiu.py 입력.txt [입력2.txt ...] -o hexagrams.json

의존성: 표준 라이브러리만 사용 (설치 불필요)
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── 1. 효(爻) 위치 마커 정의 ────────────────────────────────────────────
# 초효(1)부터 상효(6)까지. 用九/用六은 건괘·곤괘 전용이라 position 7로 별도 처리.
LINE_MARKERS = {
    "初九": 1, "初六": 1,
    "九二": 2, "六二": 2,
    "九三": 3, "六三": 3,
    "九四": 4, "六四": 4,
    "九五": 5, "六五": 5,
    "上九": 6, "上六": 6,
    "用九": 7, "用六": 7,
}

# 괘 헤더: "1\. 乾 ䷀" 또는 "1. 乾 ䷀"
HEADER_RE = re.compile(r"^\s*(\d{1,2})\\?\.\s*([\u4e00-\u9fff]{1,4})\s*([\u4dc0-\u4dff])\s*$")

# 정전 주석 블록: "[傳] ..." (마크다운 이스케이프 형태도 허용)
TRAD_RE = re.compile(r"^\\?\[傳\\?\]\s*")

# 팔괘 기호(☰☱☲☳☴☵☶☷)로 시작하는 블록 = 괘 이미지, 본문 아님
TRIGRAM_CHARS = set("☰☱☲☳☴☵☶☷")


def unescape(text: str) -> str:
    """구글 문서 내보내기에서 붙는 마크다운 이스케이프(\\., \\[, \\])를 제거한다."""
    return (text.replace("\\.", ".")
                .replace("\\[", "[")
                .replace("\\]", "]")
                .replace("\\*", "*")
                .replace("\\_", "_")
                .replace("\\<", "<")
                .replace("\\>", ">"))


# ── 부록 경계 ──────────────────────────────────────────────────────────
# 상경은 괘30, 하경은 괘64에서 끝나고 그 뒤에 부록이 붙는다.
#   상경 뒤 — 하도낙서 도판(HTML <span> 덩어리)과 그 해설
#   하경 뒤 — 계사전·설괘전·서괘전·잡괘전
# 마지막 괘의 본문 끝을 알리는 표시가 없어서, 끊지 않으면 이 부록이 전부
# 마지막 괘로 빨려 들어간다. 실제로 그렇게 됐었다:
#   괘64 1효 original 9,688자(계사전 8장의 '初六은 藉用白茅'를 효사로 오인한 뒤 전부 누적)
#   괘64 6효 sosang  1,701자, 괘30 6효 sosang 10,649자
APPENDIX_HEADS = ("繫辭上傳", "繫辭下傳", "說卦傳", "序卦傳", "雜卦傳")

# 원문에 HTML이 있을 리 없다. 태그가 보이면 본문을 벗어난 것이다.
HTML_RE = re.compile(r"<\s*/?\s*(span|div|p|br|img|table|td|tr)\b", re.I)


def is_appendix(block: str) -> bool:
    """이 블록부터가 부록인가.

    부록 표제는 블록 첫머리에 온다. `startswith`로 좁게 보는 이유는
    정전 주석이 본문 안에서 '繫辭曰', '序卦에' 처럼 부록을 인용하기 때문이다.
    포함 검사로 하면 멀쩡한 주석에서 잘린다.
    """
    return block.startswith(APPENDIX_HEADS) or bool(HTML_RE.search(block))


def classify(block: str, seen_first_line: bool):
    """
    블록의 종류를 판별한다.
    반환: (종류, 효위치 or None)
      - 'guasa'      괘사
      - 'danjeon'    단전(彖曰)
      - 'daesang'    대상전(첫 효 이전의 象曰)
      - 'sosang'     소상전(효사 뒤의 象曰)
      - 'munon'      문언전(文言曰) — 건괘·곤괘 전용
      - 'hyosa'      효사
      - 'etc'        기타(○ 로 시작하는 부가 설명 등)
    """
    if block.startswith("彖曰"):
        return "danjeon", None
    if block.startswith("象曰"):
        return ("sosang" if seen_first_line else "daesang"), None
    if block.startswith("文言曰"):
        return "munon", None
    for marker, pos in LINE_MARKERS.items():
        if block.startswith(marker):
            return "hyosa", pos
    if block.startswith("○"):
        return "etc", None
    return "guasa", None


def parse_section(num: int, name: str, symbol: str, body: str) -> dict:
    """괘 하나의 본문을 파싱한다."""
    hexagram = {
        "hexagram_id": num,
        "name_hanja": name,
        "symbol": symbol,
        "guasa": {"original": "", "commentary": []},
        "danjeon": {"original": "", "commentary": []},
        "daesang": {"original": "", "commentary": []},
        "munon": {"original": "", "commentary": []},
        "lines": {},   # 효위치 -> {"original","commentary","sosang","sosang_commentary"}
        "notes": [],   # 분류 실패/기타 블록 (검수용)
    }

    blocks = [b.strip() for b in body.split("\n\n") if b.strip()]

    current_key = None      # 지금 원문을 누적 중인 대상 ('guasa','danjeon','daesang','munon')
    current_line = None     # 지금 다루는 효 위치
    current_kind = None     # 'hyosa' | 'sosang' | 그 외
    seen_first_line = False
    guasa_done = False

    def target_commentary():
        """현재 문맥에 맞는 주석 리스트를 반환한다."""
        if current_line is not None:
            slot = hexagram["lines"].setdefault(
                current_line,
                {"original": "", "commentary": [], "sosang": "", "sosang_commentary": []},
            )
            return slot["sosang_commentary"] if current_kind == "sosang" else slot["commentary"]
        if current_key:
            return hexagram[current_key]["commentary"]
        return hexagram["notes"]

    for i, block in enumerate(blocks):
        # 부록에 닿으면 이 괘의 본문은 끝이다. 이후 블록은 전부 버린다.
        if is_appendix(block):
            hexagram["_cut"] = (len(blocks) - i, block[:20])
            break

        # 팔괘 기호 블록·단독 '傳' 표시는 건너뛴다
        if block and block[0] in TRIGRAM_CHARS:
            continue
        if block == "傳":
            continue

        # 정전 주석
        if TRAD_RE.match(block):
            target_commentary().append(TRAD_RE.sub("", block).strip())
            continue

        kind, pos = classify(block, seen_first_line)

        if kind == "hyosa":
            seen_first_line = True
            current_line, current_kind, current_key = pos, "hyosa", None
            slot = hexagram["lines"].setdefault(
                pos, {"original": "", "commentary": [], "sosang": "", "sosang_commentary": []}
            )
            slot["original"] = (slot["original"] + " " + block).strip()

        elif kind == "sosang":
            current_kind = "sosang"
            if current_line is None:      # 방어: 효 없이 소상전이 오면 노트로
                hexagram["notes"].append(block)
            else:
                slot = hexagram["lines"][current_line]
                slot["sosang"] = (slot["sosang"] + " " + block).strip()

        elif kind in ("danjeon", "daesang", "munon"):
            guasa_done = True
            current_key, current_line, current_kind = kind, None, kind
            hexagram[kind]["original"] = (hexagram[kind]["original"] + " " + block).strip()

        elif kind == "guasa":
            if not guasa_done and not seen_first_line:
                # 괘사 본문 (여러 줄로 쪼개져 있을 수 있어 누적)
                current_key, current_line, current_kind = "guasa", None, "guasa"
                hexagram["guasa"]["original"] = (
                    hexagram["guasa"]["original"] + " " + block
                ).strip()
            elif current_kind in ("danjeon", "daesang", "munon") and current_key:
                # 彖曰/象曰이 여러 줄로 끊긴 경우의 이어지는 줄
                hexagram[current_key]["original"] = (
                    hexagram[current_key]["original"] + " " + block
                ).strip()
            elif current_kind == "hyosa" and current_line:
                hexagram["lines"][current_line]["original"] += " " + block
            elif current_kind == "sosang" and current_line:
                hexagram["lines"][current_line]["sosang"] += " " + block
            else:
                hexagram["notes"].append(block)

        else:  # 'etc'
            hexagram["notes"].append(block)

    # 효 딕셔너리를 정렬된 리스트로 변환
    hexagram["lines"] = [
        {"position": p, **hexagram["lines"][p]} for p in sorted(hexagram["lines"])
    ]
    return hexagram


# 건괘 문언전 안에서 각 효를 다시 논하는 부분의 시작 마커 ("初九曰", "九二曰" ...)
QIAN_MUNON_RE = re.compile(r"(初九|九二|九三|九四|九五|上九|用九)曰")


def fix_qian(h: dict) -> dict:
    """
    건괘(1번)는 편집 순서가 다르다.
      - 효사 6개 + 用九가 먼저 나오고, 그 뒤에 彖曰 / 象曰(대상전) / 소상전 6줄이 온다.
      - 소상전 6줄에는 '象曰' 접두어가 없다.
      - 효사 블록 뒤에 문언전의 '初九曰 …' 문답이 붙어 들어온다.
    이 함수가 그 셋을 제자리로 돌려놓는다.
    """
    if h["hexagram_id"] != 1:
        return h

    # (1) 효사에 섞여 들어온 문언전 문답을 잘라내 munon으로 옮긴다
    munon_extra = []
    for line in h["lines"]:
        m = QIAN_MUNON_RE.search(line["original"])
        if m:
            munon_extra.append(line["original"][m.start():].strip())
            line["original"] = line["original"][:m.start()].strip()
    if munon_extra:
        h["munon"]["original"] = (" ".join(munon_extra) + " " + h["munon"]["original"]).strip()

    # (2) notes 앞부분에 밀려난 대상전 / 소상전 6줄을 복원한다
    leftovers = h["notes"]
    if leftovers and leftovers[0].startswith("象曰") and not h["daesang"]["original"]:
        h["daesang"]["original"] = leftovers.pop(0)

    by_pos = {l["position"]: l for l in h["lines"]}
    for pos in range(1, 7):
        if not leftovers:
            break
        slot = by_pos.get(pos)
        if slot is not None and not slot["sosang"]:
            slot["sosang"] = leftovers.pop(0)

    # (3) 用九(7효)만은 소상전이 notes로 밀리지 않고 효사 뒤에 그대로 붙어 들어온다.
    #     "用九 <효사> 用九 <소상전>" 형태이므로 두 번째 '用九'에서 잘라 떼어낸다.
    yonggu = by_pos.get(7)
    if yonggu is not None and not yonggu["sosang"]:
        second = yonggu["original"].find("用九", len("用九"))
        if second != -1:
            yonggu["sosang"] = yonggu["original"][second:].strip()
            yonggu["original"] = yonggu["original"][:second].strip()

    h["notes"] = leftovers
    return h


# 원문 사이트에서 넘어온 글자 중 손봐야 하는 것들.
# 확장한자(4바이트)가 latin-1로 잘못 해석돼 깨진 경우와, 이체자를 표준 자형으로 통일하는 경우.
GLYPH_FIXES = {
    "\u00f0\u00a4\u00a8\u008f": "瑣",  # 𤨏(U+24A0F)가 깨진 형태 — 괘56 旅瑣瑣 / 鄙猥瑣細
    "\U00024a0f": "瑣",                # 정상 디코딩된 이체자도 같은 표준자로 통일
}


def normalize_glyphs(text: str) -> str:
    """알려진 깨진 글자·이체자를 표준 자형으로 되돌린다."""
    for broken, standard in GLYPH_FIXES.items():
        text = text.replace(broken, standard)
    return text


def parse_text(text: str) -> list:
    """전체 텍스트에서 괘 섹션들을 찾아 파싱한다."""
    text = normalize_glyphs(unescape(text))

    # 구글 문서 마크다운 내보내기는 문단 경계를 빈 줄이 아니라 하드브레이크
    # (줄 끝 공백 2칸)로 내보낸다. 블록 분리가 빈 줄 기준이라 이대로 두면
    # 괘 하나가 통째로 한 블록이 되어 효사가 하나도 안 잡힌다.
    text = re.sub(r"[ \t]+\n", "\n\n", text)

    lines = text.split("\n")

    starts = []  # (라인번호, 괘번호, 괘명, 기호)
    for idx, line in enumerate(lines):
        m = HEADER_RE.match(line)
        if m:
            starts.append((idx, int(m.group(1)), m.group(2), m.group(3)))

    results = []
    for i, (idx, num, name, sym) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(lines)
        body = "\n".join(lines[idx + 1:end])
        h = fix_qian(parse_section(num, name, sym, body))
        cut = h.pop("_cut", None)   # 출력 스키마에는 남기지 않는다
        if cut:
            dropped, head = cut
            print(f"  괘{num} {name}: 부록 이후 {dropped}블록 제외 (시작: {head}…)")
        results.append(h)
    return results


MAX_LINE_LEN = 150   # 효사·소상전 길이 상한 (실측 최대 55자)


def _all_texts(h: dict):
    """검사 대상 문자열을 (이름, 내용)으로 모두 훑는다."""
    for k in ("guasa", "danjeon", "daesang", "munon"):
        yield k, h[k]["original"]
        for c in h[k]["commentary"]:
            yield f"{k}.주석", c
    for l in h["lines"]:
        yield f"효{l['position']}", l["original"]
        yield f"효{l['position']}.소상전", l["sosang"]
        for c in l["commentary"]:
            yield f"효{l['position']}.주석", c
        for c in l["sosang_commentary"]:
            yield f"효{l['position']}.소상주석", c
    for n in h["notes"]:
        yield "notes", n


def validate(hexagrams: list) -> list:
    """구조 검증 — 누락된 항목을 경고 목록으로 반환한다."""
    warnings = []
    seen = {}
    for h in hexagrams:
        hid = h["hexagram_id"]
        if hid in seen:
            warnings.append(f"[중복] 괘 {hid} ({h['name_hanja']})")
        seen[hid] = True

        if not h["guasa"]["original"]:
            warnings.append(f"[누락] 괘 {hid} {h['name_hanja']}: 괘사 없음")
        if not h["danjeon"]["original"]:
            warnings.append(f"[누락] 괘 {hid} {h['name_hanja']}: 단전 없음")

        positions = [l["position"] for l in h["lines"] if l["position"] <= 6]
        if len(positions) != 6:
            warnings.append(
                f"[불일치] 괘 {hid} {h['name_hanja']}: 효 {len(positions)}개 (기대 6개) -> {positions}"
            )
        for l in h["lines"]:
            if not l["original"]:
                warnings.append(f"[누락] 괘 {hid} 효{l['position']}: 효사 없음")

        # 길이 이상 — 부록이 빨려 들어가면 여기서 걸린다.
        # 실측 최대는 효사 54자(괘51 6효), 소상전 55자(괘10 3효)다. 상한은 넉넉히 잡았다.
        for l in h["lines"]:
            if len(l["original"]) > MAX_LINE_LEN:
                warnings.append(
                    f"[길이] 괘 {hid} 효{l['position']}: 효사 {len(l['original'])}자 "
                    f"(상한 {MAX_LINE_LEN}) — 뒤에 딴 것이 붙었는지 확인"
                )
            if len(l["sosang"]) > MAX_LINE_LEN:
                warnings.append(
                    f"[길이] 괘 {hid} 효{l['position']}: 소상전 {len(l['sosang'])}자 "
                    f"(상한 {MAX_LINE_LEN}) — 뒤에 딴 것이 붙었는지 확인"
                )

        # 마크업·부록 잔여 — 원문에는 있을 수 없다
        for label, text in _all_texts(h):
            if HTML_RE.search(text):
                warnings.append(f"[마크업] 괘 {hid} {label}: HTML 태그가 남아 있음")
            if text.startswith(APPENDIX_HEADS):
                warnings.append(f"[부록] 괘 {hid} {label}: 부록 표제로 시작함")

    missing = sorted(set(range(1, 65)) - set(seen))
    if missing:
        warnings.append(f"[미수록 괘] {missing}")
    return warnings


def load_input(path: Path) -> str:
    """텍스트 또는 {'fileContent': ...} 형태의 JSON 둘 다 받는다."""
    raw = path.read_text(encoding="utf-8")
    stripped = raw.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                data = data[0]
            if isinstance(data, dict):
                for key in ("fileContent", "text", "content"):
                    if key in data:
                        inner = data[key]
                        if isinstance(inner, str) and inner.lstrip().startswith("{"):
                            try:
                                inner = json.loads(inner).get("fileContent", inner)
                            except json.JSONDecodeError:
                                pass
                        return inner
        except json.JSONDecodeError:
            pass  # 일반 텍스트로 처리
    return raw


def main():
    ap = argparse.ArgumentParser(description="주역전의 텍스트 -> 구조화 JSON")
    ap.add_argument("inputs", nargs="+", help="입력 파일 (상/하 여러 개 지정 가능)")
    ap.add_argument("-o", "--output", default="hexagrams.json", help="출력 JSON 경로")
    ap.add_argument("--quiet", action="store_true", help="경고 출력 생략")
    args = ap.parse_args()

    all_hex = []
    for p in args.inputs:
        path = Path(p)
        if not path.exists():
            print(f"오류: 파일을 찾을 수 없습니다 -> {p}", file=sys.stderr)
            sys.exit(1)
        try:
            parsed = parse_text(load_input(path))
        except Exception as e:
            print(f"오류: {p} 파싱 실패 -> {e}", file=sys.stderr)
            sys.exit(1)
        print(f"{path.name}: 괘 {len(parsed)}개 추출")
        all_hex.extend(parsed)

    all_hex.sort(key=lambda h: h["hexagram_id"])

    warnings = validate(all_hex)
    if warnings and not args.quiet:
        print("\n── 검증 경고 ──")
        for w in warnings:
            print(" ", w)
        print(f"총 {len(warnings)}건\n")

    out = Path(args.output)
    out.write_text(json.dumps(all_hex, ensure_ascii=False, indent=2), encoding="utf-8")

    total_lines = sum(len([l for l in h["lines"] if l["position"] <= 6]) for h in all_hex)
    print(f"완료: {out} (괘 {len(all_hex)}개 / 효 {total_lines}개)")


if __name__ == "__main__":
    main()
