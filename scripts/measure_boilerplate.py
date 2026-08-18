#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""괘가 달라도 같은 문구가 나오는가 — 신고된 증상을 그대로 세는 자.

    python scripts/measure_boilerplate.py /tmp/hexagram_effect_gemini.json
    python scripts/measure_boilerplate.py 수정전.json 수정후.json     # 나란히 대조

**왜 따로 만드는가.** `compare_hexagram_effect.py`의 세 지표는 "답변을 보고 어느 괘인지
알아볼 수 있는가"를 잰다. 그런데 실사용 신고는 그게 아니었다 — "괘가 다른데 **같은
문구**가 나온다"였다. 두 질문은 다르다. 확정 근거(괘사·효사 한글)의 어휘만 조금 섞여도
괘는 알아볼 수 있지만, 답변의 뼈대가 "잠시 멈춰 내면을 다지라"로 똑같으면 읽는 사람에게는
같은 답이다. 실제로 판별 적중률은 보정 기준 91.7%로 천장에 닿아 있는데도 신고는 들어왔다.

**세는 방법.** 사연을 고정해 놓고, 서로 다른 괘의 답변에 공통으로 나타나는 어절 뭉치를
찾는다. 그 뭉치가 답변을 얼마나 덮는지가 지표다. 100%면 어느 괘를 뽑아도 같은 말이고,
0%면 괘마다 다른 말을 한 것이다.

**사연 되풀이는 뺀다.** 상담사는 내담자의 말을 되짚어 준다("30년 쌓아오신 경험은…").
그 문구는 모든 괘의 답변에 나오지만 통념 후퇴가 아니라 공감이다. 질문에 있는 어절
뭉치는 상용구에서 제외한다 — 이걸 안 빼면 공감을 증상으로 오진한다.

**두 단계로 나눠 본다.**
  - 괘 간 상용구: 같은 사연 안에서 괘를 넘나드는 문구. 신고된 증상 그 자체다
  - 전역 상용구: 사연도 괘도 넘나드는 문구. 어떤 고민에나 나가는 상담 상투구다

**이 자는 놓치는 쪽으로 틀린다.** 어절 단위 정확 일치라 "멈춰 서서"와 "멈춰서"를 다른
것으로 본다. 한국어 형태 변화를 다 잡으려면 분석기를 물려야 하는데, 여기서 필요한 것은
절대값이 아니라 조건 간 대소이고 그 편향은 어느 조건에나 똑같이 걸린다.

모델을 부르지 않는다. 이미 저장된 결과 JSON만 읽는다.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Sequence, Set, Tuple

# 어절 n-gram 길이. 3어절이면 "잠시 멈춰 서서" 정도가 잡힌다. 2어절은 우연히 겹치는 것이
# 너무 많고, 4어절 이상은 조사 하나만 달라도 놓친다.
NGRAM = 3

# 상용구로 칠 최소 괘 수. 2로 두는 것은 느슨한 쪽이다 — 놓치느니 잡고, 목록에 괘 수를
# 찍어 사람이 판단하게 한다. 조건 간 비교에는 같은 잣대를 쓰므로 문제되지 않는다.
MIN_HEXAGRAMS = 2

_BUANG = re.compile(r"[^가-힣a-zA-Z0-9]+")


def _폭(s: str) -> int:
    """한글은 두 칸을 차지한다. 이걸 모르면 표가 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _채움(s: str, n: int, 오른쪽: bool = False) -> str:
    공백 = " " * max(0, n - _폭(s))
    return 공백 + s if 오른쪽 else s + 공백


def 어절들(text: str) -> List[str]:
    """구두점·강조 기호를 털어낸 어절 목록. 빈 어절은 버린다."""
    out = []
    for w in (text or "").split():
        w = _BUANG.sub("", w)
        if w:
            out.append(w)
    return out


def ngrams(tokens: Sequence[str], n: int = NGRAM) -> List[Tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def 덮임(tokens: Sequence[str], 상용구: Set[Tuple[str, ...]], n: int = NGRAM) -> int:
    """상용구에 덮인 어절 자리의 개수.

    등장 횟수가 아니라 **덮인 자리**를 센다. 겹치는 n-gram이 같은 어절을 두 번 세면
    비율이 1을 넘는다.
    """
    covered: Set[int] = set()
    for i, g in enumerate(ngrams(tokens, n)):
        if g in 상용구:
            covered.update(range(i, i + n))
    return len(covered)


def 공유_덮임(a_tokens: Sequence[str], b_tokens: Sequence[str],
             제외: Set[Tuple[str, ...]]) -> float:
    """답변 A의 어절 중, 답변 B에도 그대로 나오는 문구에 덮인 몫.

    쌍으로 재는 이유는 대조군 때문이다. 열두 답변을 한 풀에 모아 "둘 이상이 공유하는
    문구"를 뽑으면, 비교 대상이 많을수록 공유가 늘어 조건 간 비교가 깨진다. 쌍으로
    재면 어느 조건이든 답변 두 개씩만 견주므로 잣대가 같아진다.
    """
    b = set(ngrams(b_tokens))
    b -= 제외
    return 덮임(a_tokens, b) / len(a_tokens) if a_tokens else 0.0


def 분석(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """상용구 지표를 낸다. rows는 compare_hexagram_effect.py가 남긴 결과다.

    **대조군이 핵심이다.** 상담 답변에는 괘와 무관한 뼈대가 원래 있다 — 사연을 되짚는
    공감 도입, 되묻기 마무리. 그건 증상이 아니다. 그래서 절대값이 아니라 두 값을 견준다.

      · 괘가 다른 쌍이 공유하는 몫
      · 같은 괘를 두 번 돌린 쌍이 공유하는 몫  ← 대조군

    같은 괘끼리는 당연히 많이 겹친다. 괘를 바꿨는데도 그만큼 겹치면, 괘를 바꾼 것이
    답변에 아무 일도 하지 않은 것이다. 차이가 클수록 괘가 말을 갈랐다는 뜻이다.
    """
    사연들 = sorted({r["질문"] for r in rows})

    # 질문에 들어 있는 어절 뭉치. 상담사가 사연을 그대로 되뇌는 것은 증상이 아니다.
    질문_ngram: Set[Tuple[str, ...]] = set()
    for q in 사연들:
        질문_ngram.update(ngrams(어절들(q)))

    토큰 = {id(r): 어절들(r["답변"]) for r in rows}

    다른괘, 같은괘 = [], []
    for 질문 in 사연들:
        같은사연 = [r for r in rows if r["질문"] == 질문]
        for i, a in enumerate(같은사연):
            for b in 같은사연[i + 1:]:
                # 양방향을 다 재어 평균한다. 길이가 다르면 A→B와 B→A가 다르다.
                몫 = (공유_덮임(토큰[id(a)], 토큰[id(b)], 질문_ngram)
                      + 공유_덮임(토큰[id(b)], 토큰[id(a)], 질문_ngram)) / 2
                (다른괘 if a["배치"] != b["배치"] else 같은괘).append(몫)

    # 전역 상투구 — 사연도 괘도 넘나드는 문구. 이건 풀 전체에서 본다.
    전체_사연: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    전체_배치: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    등장수: Dict[Tuple[str, ...], int] = defaultdict(int)
    for r in rows:
        toks = 토큰[id(r)]
        for g in set(ngrams(toks)):
            if g in 질문_ngram:
                continue
            전체_사연[g].add(r["질문"])
            전체_배치[g].add(r["배치"])
        for g in ngrams(toks):
            if g not in 질문_ngram:
                등장수[g] += 1

    전역 = {g for g in 전체_배치
            if len(전체_배치[g]) >= MIN_HEXAGRAMS and len(전체_사연[g]) >= 2}

    전역_덮임, 전체_어절 = 0, 0
    for r in rows:
        toks = 토큰[id(r)]
        전체_어절 += len(toks)
        전역_덮임 += 덮임(toks, 전역)

    넓은 = sorted(전체_배치.items(),
                  key=lambda kv: (len(kv[1]), len(전체_사연[kv[0]]), 등장수[kv[0]]),
                  reverse=True)
    넓은_문구 = [(" ".join(g), len(배치들), len(전체_사연[g]), 등장수[g])
                 for g, 배치들 in 넓은 if len(배치들) >= MIN_HEXAGRAMS][:12]

    def 평균(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    return {
        "다른괘_공유": 평균(다른괘),
        "같은괘_공유": 평균(같은괘),
        "다른괘_쌍수": len(다른괘),
        "같은괘_쌍수": len(같은괘),
        "전역_덮임": 전역_덮임 / 전체_어절 if 전체_어절 else 0.0,
        "총_어절": 전체_어절,
        "넓은_문구": 넓은_문구,
    }


def 출력(이름: str, 결과: Dict[str, Any]) -> None:
    차 = 결과["같은괘_공유"] - 결과["다른괘_공유"]
    print(f"\n[상용구 지표] {이름}")
    print(f"  괘가 다른 쌍      {결과['다른괘_공유']:6.1%}  (n={결과['다른괘_쌍수']})")
    if 결과["같은괘_쌍수"]:
        print(f"  같은 괘 반복 쌍   {결과['같은괘_공유']:6.1%}  (n={결과['같은괘_쌍수']}) ← 대조군")
        print(f"  차이              {차:+6.1%}   "
              f"← 0에 가까우면 괘를 바꿔도 같은 말을 한 것이다")
    else:
        print("  대조군 없음 — 원 측정을 `-n 2` 이상으로 돌려야 같은 괘 반복 쌍이 생긴다.")
    print(f"  전역 상투구 덮임  {결과['전역_덮임']:6.1%}   "
          f"← 사연도 괘도 넘나드는 문구가 답변을 덮은 몫 (답변 총 {결과['총_어절']:,}어절)")

    if 결과["넓은_문구"]:
        print("\n  가장 넓게 퍼진 문구 (괘 수 / 사연 수 / 등장):")
        for 문구, 괘수, 사연수, 횟수 in 결과["넓은_문구"]:
            print(f"    {괘수}괘 / {사연수}사연 / {횟수:2d}회   \"{문구}\"")


def 대조(왼_이름: str, 왼: Dict[str, Any], 오_이름: str, 오: Dict[str, Any]) -> None:
    print("\n" + "=" * 76)
    print("  " + _채움("", 24) + _채움(왼_이름[:18], 20, True)
          + _채움(오_이름[:18], 20, True) + _채움("차이", 10, True))
    행 = (("다른괘_공유", "괘가 다른 쌍 공유"),
          ("같은괘_공유", "같은 괘 쌍 공유(대조)"),
          ("전역_덮임", "전역 상투구 덮임"))
    for 키, 라벨 in 행:
        a, b = 왼[키], 오[키]
        print("  " + _채움(라벨, 24) + _채움(f"{a:.1%}", 20, True)
              + _채움(f"{b:.1%}", 20, True) + _채움(f"{b - a:+.1%}", 10, True))

    왼_차 = 왼["같은괘_공유"] - 왼["다른괘_공유"]
    오_차 = 오["같은괘_공유"] - 오["다른괘_공유"]
    print("  " + _채움("대조군과의 차이", 24) + _채움(f"{왼_차:.1%}", 20, True)
          + _채움(f"{오_차:.1%}", 20, True) + _채움(f"{오_차 - 왼_차:+.1%}", 10, True))
    print("\n  → 마지막 줄이 커졌으면 괘마다 다른 말을 하기 시작한 것이다.")
    print("    '괘가 다른 쌍 공유'가 내려가고 대조군은 그대로인 것이 가장 좋은 모양이다.")


def 읽기(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    빠진 = [k for k in ("질문", "배치", "답변") if rows and k not in rows[0]]
    if 빠진:
        sys.exit(f"결과 형식이 아닙니다 ({path}): {빠진} 항목이 없습니다. "
                 "compare_hexagram_effect.py가 남긴 JSON을 주십시오.")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description="괘가 달라도 같은 문구가 나오는지 센다 (모델 호출 없음)")
    ap.add_argument("files", nargs="+", metavar="JSON",
                    help="compare_hexagram_effect.py가 남긴 결과 파일. 두 개를 주면 대조표를 낸다")
    args = ap.parse_args()

    결과들 = [(p, 분석(읽기(p))) for p in args.files]
    for 이름, 결과 in 결과들:
        출력(이름, 결과)

    if len(결과들) == 2:
        (왼_이름, 왼), (오_이름, 오) = 결과들
        대조(왼_이름.split("/")[-1], 왼, 오_이름.split("/")[-1], 오)


if __name__ == "__main__":
    main()
