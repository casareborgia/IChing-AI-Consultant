"""두 모델의 번역을 대조해 사람이 볼 검수 목록을 만든다.

    python scripts/compare_translations.py data/translations/gemini.json \
                                           data/translations/claude.json \
                                           -o data/translations/diff.md

왜 필요한가. 파일럿에서 두 모델 모두 `flag`를 한 번도 달지 않았다(정직성 0/12).
모델의 자기 신고로는 검수 대상을 고를 수 없다는 뜻이다. 그래서 남은 자동 신호는
**두 모델의 불일치**와 **용어표 위반**뿐이다.

전부 다르게 쓰이므로 문장이 다르다는 사실 자체는 신호가 아니다. 아래 순서로 좁힌다.
  1. 판정어 뒤집힘   — 한쪽만 '길함'/'흉함' 따위를 말한다. 뜻이 반대일 수 있다
  2. 고정 용어표 위반 — 확정한 우리말을 안 쓴 자리
  3. 문장 유사도 하위 — 표현이 크게 갈린 자리
"""
import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any, Dict, List

# 판정어 — 한쪽에만 있으면 뜻이 갈렸을 수 있다
VERDICT_WORDS = ["길함", "길하", "흉함", "흉하", "허물이 없", "허물", "뉘우침",
                 "부끄러", "위태로", "이롭", "형통"]

LOW_SIMILARITY_TOP = 40   # 유사도 하위 몇 건을 실을지


def load(path: str) -> Dict[str, Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {str(r["id"]): r for r in data}


def text(rec: Dict[str, Any]) -> str:
    return (rec.get("translation_ko") or "").strip() if rec else ""


def is_checkable(korean: str) -> bool:
    """이 용어로 준수 여부를 볼 수 있는가.

    용언과 파생 명사는 걸러낸다. 활용형이 갈리는 데다('이로움' vs '이롭다')
    불규칙 활용까지 있어 문자열 비교로는 오탐만 쌓인다. 위치 표시처럼
    번역문에 그대로 나올 이유가 없는 말도 여기서 빠진다('初'→'처음'은
    실제로는 '초구'로 옮겨진다).

    남는 것은 뜻이 하나로 고정된 명사뿐이다 — 질곡, 볼기, 고종, 귀방, 동몽,
    가시덤불 같은 것들. 놓치는 위반이 생기더라도, 사람이 볼 목록은
    이쪽이 쓸모 있다.
    """
    if " " in korean or len(korean) < 2:
        return False
    return not korean.endswith(("다", "함", "음", "기", "움", "침", "짐", "옴", "됨"))


def load_glossary(path: str) -> Dict[str, str]:
    """'한자 우리말' 쌍이 공백으로 이어진 블록을 읽는다."""
    table = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        for pair in re.split(r"\s{2,}|\t", line.strip()):
            parts = pair.split(None, 1)
            if len(parts) == 2 and re.fullmatch(r"[一-鿿]+", parts[0]):
                table[parts[0]] = parts[1].strip()
    return table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("left"); ap.add_argument("right")
    ap.add_argument("-o", "--output", default="data/translations/diff.md")
    ap.add_argument("--items", default="data/translation_items.json")
    ap.add_argument("--glossary", default="pilot/glossary_block.txt")
    args = ap.parse_args()

    lname, rname = Path(args.left).stem, Path(args.right).stem
    L, R = load(args.left), load(args.right)
    items = json.loads(Path(args.items).read_text(encoding="utf-8"))
    glossary = load_glossary(args.glossary)

    verdict, violation, sims, missing = [], [], [], []

    for it in items:
        iid = str(it["id"])
        a, b = text(L.get(iid)), text(R.get(iid))
        if not a or not b:
            missing.append((iid, bool(a), bool(b)))
            continue

        # 1. 판정어 뒤집힘
        diffs = [w for w in VERDICT_WORDS if (w in a) != (w in b)]
        if diffs:
            verdict.append((iid, it, a, b, diffs))

        # 2. 용어표 위반 — 원문에 한자가 있는데 정한 우리말이 없는 쪽.
        #    통째로 비교하면 활용형에서 전부 걸린다('형통함' vs '형통하고').
        #    어간만 보아 활용 차이는 넘기고 낱말 자체가 다른 자리만 잡는다.
        for hanja, korean in glossary.items():
            if not is_checkable(korean):
                continue
            # 복합어가 원문에 있으면 그 구성 글자는 건너뛴다.
            # 群龍을 '뭇 용'으로 옮겼는데 群을 '무리'로 안 썼다고 걸리면 헛일이다.
            if any(k != hanja and hanja in k and k in it["source"] for k in glossary):
                continue
            if hanja in it["source"]:
                bad = [n for n, t in ((lname, a), (rname, b)) if korean not in t]
                if bad:
                    violation.append((iid, hanja, korean, bad))

        # 3. 유사도
        sims.append((difflib.SequenceMatcher(None, a, b).ratio(), iid, it, a, b))

    sims.sort()
    out: List[str] = [
        "# 번역 검수 목록", "",
        f"`{lname}` vs `{rname}` 대조. 전체 {len(items)}건.", "",
        "파일럿에서 두 모델 모두 `flag`를 한 번도 달지 않았다. 모델의 자기 신고로는",
        "검수 대상을 고를 수 없어, 불일치와 용어표 위반으로 목록을 만들었다.", "",
        f"- 판정어 뒤집힘 **{len(verdict)}건** ← 최우선",
        f"- 용어표 위반 **{len(violation)}건**",
        f"- 유사도 하위 {min(LOW_SIMILARITY_TOP, len(sims))}건",
        f"- 한쪽이 비어 있음 {len(missing)}건", "", "---", "",
        "## 1. 판정어가 한쪽에만 있는 항목", "",
        "길흉·허물 같은 판정어가 한쪽에만 나온다. 뜻이 반대로 갈렸을 수 있어 먼저 본다.", "",
    ]
    for iid, it, a, b, diffs in verdict:
        out += [f"### {iid} — {it['hexagram']} {it['target']}  (갈린 말: {', '.join(diffs)})", "",
                f"> {it['source']}", "",
                f"- **{lname}**: {a}", f"- **{rname}**: {b}", ""]
    if not verdict:
        out += ["(없음)", ""]

    out += ["---", "", "## 2. 고정 용어표를 안 쓴 항목", "",
            "| id | 한자 | 정한 우리말 | 안 쓴 쪽 |", "|---|---|---|---|"]
    for iid, hanja, korean, bad in violation[:120]:
        out.append(f"| {iid} | {hanja} | {korean} | {', '.join(bad)} |")
    if len(violation) > 120:
        out.append(f"| … | 외 {len(violation) - 120}건 | | |")
    if not violation:
        out.append("| (없음) | | | |")

    out += ["", "---", "", f"## 3. 표현이 가장 크게 갈린 {LOW_SIMILARITY_TOP}건", ""]
    for ratio, iid, it, a, b in sims[:LOW_SIMILARITY_TOP]:
        out += [f"### {iid} — {it['hexagram']} {it['target']}  (유사도 {ratio:.2f})", "",
                f"> {it['source']}", "",
                f"- **{lname}**: {a}", f"- **{rname}**: {b}", ""]

    if missing:
        out += ["---", "", "## 4. 한쪽이 비어 있는 항목", "",
                "| id | " + lname + " | " + rname + " |", "|---|---|---|"]
        for iid, has_l, has_r in missing:
            out.append(f"| {iid} | {'있음' if has_l else '없음'} | {'있음' if has_r else '없음'} |")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"검수 목록 → {args.output}")
    print(f"  판정어 뒤집힘 {len(verdict)}건 / 용어표 위반 {len(violation)}건 / "
          f"한쪽 비어 있음 {len(missing)}건")
    if sims:
        print(f"  유사도 중앙값 {sims[len(sims)//2][0]:.2f}, 최저 {sims[0][0]:.2f}")


if __name__ == "__main__":
    main()
