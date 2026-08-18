#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""괘가 답변을 실제로 바꾸는가 — 사연을 고정하고 괘만 바꿔 잰다.

    python scripts/compare_hexagram_effect.py -p gemini
    python scripts/compare_hexagram_effect.py -p ollama -n 2   # 대조군까지 받으려면 n≥2

실사용에서 "괘가 다른데 답변 뉘앙스가 같다"는 신고가 있었다(CLAUDE.md 설계 원칙 절).
수산건과 천산둔이 둘 다 "잠시 멈춰 내면을 다지라"로 나갔다. 그때 이걸 잴 도구가
없어서 사람이 두 대화록을 눈으로 견줬다.

**무엇을 반증하려는가.** "괘가 일을 하고 있다"는 주장이다. 사연이 같은데 괘를 바꿔도
답이 같다면, 답을 만든 것은 괘가 아니라 사연이다. 그때 이 앱은 주역을 인용하는
공감 챗봇이지 괘를 읽는 상담이 아니다.

**왜 절대 수치로는 안 되는가.** 두 답변의 유사도가 0.42라는 것만으로는 아무 말도
할 수 없다. 같은 모델에 같은 것을 두 번 물어도 답은 조금씩 다르기 때문이다. 그래서
대조군을 함께 잰다 — **같은 괘를 두 번 돌린 쌍**이다. 괘를 바꾼 쌍의 유사도가
이 대조군과 비슷하면, 괘를 바꾼 것이 아무 일도 하지 않은 것이다.

**세 가지를 잰다.**
  1. 괘 판별 적중률 — 답변이 자기 괘의 근거와 가장 닮았는가. 우연은 1/K다
  2. 답변 쌍 유사도 — 괘가 다른 쌍 vs 같은 괘 반복 쌍(대조군). n≥2에서만 나온다
  3. 근거 도달도 — 자기 괘 근거의 어휘가 답변에 얼마나 나타나는가

**왜 score_agents로는 안 되는가.** 그쪽은 검색을 스텁으로 갈아끼운다(재현성을 위해
일부러 그렇게 해뒀다). 인덱스에 무엇이 들었든 결과가 같으므로 이 질문에는 답하지
못한다. 여기서는 진짜 검색과 진짜 DB 근거를 태운다.

유사도는 한글 문자 2-gram으로 잰다. 형태소 분석기를 새로 물리지 않으려는 것이고,
여기서 필요한 것은 절대값이 아니라 조건들 사이의 대소뿐이다.

**자를 먼저 재봤다.** 합성 답변으로 두 극단을 넣어 지표가 갈라지는지 확인했다
(`tests/test_hexagram_effect_metrics.py`가 그 확인을 붙들고 있다).

| | 괘 판별 적중률 | 근거 도달도 | 답변 쌍 유사도 |
|---|---|---|---|
| 근거를 그대로 옮긴 답변 | 100% | 1.000 | 0.42 |
| 어느 괘든 같은 말을 한 답변 | 33% (= 우연) | 0.03 | 1.00 |

실제 답변은 근거를 그대로 옮기지 않고 내담자의 말로 바꾸므로 두 극단 사이에 앉는다.
**절대값이 아니라 우연선(1/K)과 대조군에 견주어 읽을 것.**
"""

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
from typing import Any, Dict, List, Set

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.counsel import run_counsel_turn  # noqa: E402
from agents.interpret import run_interpret  # noqa: E402
from core.db import AsyncSessionLocal  # noqa: E402
from core.llm import get_client  # noqa: E402

# 사연은 고정하고 괘만 바꾼다. 사연이 서로 다르면 답변이 달라진 이유가 괘인지
# 사연인지 갈라낼 수 없다 — 그것이 이 하네스의 전부다.
CASES: List[str] = [
    "30년 하던 가게를 접고 업종을 바꿀지 고민입니다. 이것밖에 해본 게 없어 막막합니다.",
    "7년 만난 사람과 헤어질지 계속 갈지 모르겠습니다. 미워서가 아니라 아무 느낌이 없어서요.",
    "부모님이 제 진로를 계속 반대하셔서 대화가 막혔습니다.",
]

# 초점 규칙이 서로 다른 자리를 고루 넣었다. 규칙이 같은 괘만 모으면 "괘가 다르다"가
# 아니라 "효사냐 괘사냐"만 재게 된다.
#
# (이름, 여섯 효). 6=노음(변) 7=소양 8=소음 9=노양(변)
# 여섯 효는 엔진으로 검산해 넣었다. 손으로 적으면 뜻한 괘가 안 나온다 —
# 처음 적은 여섯 중 셋이 다른 괘였다.
HEXAGRAMS = [
    ("수산건 1·2효",   [6, 6, 7, 8, 7, 8]),   # 39 → 5.  동효 2 — 두 효사, 상위(2효) 우선
    ("천산둔 2효",     [8, 6, 7, 7, 7, 7]),   # 33 → 44. 동효 1 — 효사 하나
    ("중천건 무변",    [7, 7, 7, 7, 7, 7]),   # 1.       동효 0 — 괘사
    ("지뢰복 1효",     [9, 8, 8, 8, 8, 8]),   # 24 → 2.  동효 1 — 효사 하나
    ("택수곤 4·5효",   [8, 7, 8, 9, 9, 8]),   # 47 → 7.  동효 2 — 상위(5효) 우선
    ("화풍정 5변",     [6, 9, 9, 9, 6, 7]),   # 50 → 42. 동효 5 — 초점이 지괘 6효로 넘어간다
]

한글2gram = re.compile(r"[^가-힣]")


def bigrams(text: str) -> Set[str]:
    """한글만 남긴 문자 2-gram. 조사·어미까지 섞이지만 조건 비교에는 충분하다."""
    t = 한글2gram.sub("", text or "")
    return {t[i:i + 2] for i in range(len(t) - 1)}


def 포함도(답변: str, 근거: str) -> float:
    """근거의 어휘가 답변에 얼마나 나타나는가. |답변∩근거| / |근거|.

    자카드가 아니라 포함도를 쓰는 이유는 길이 차이 때문이다. 상담 답변은 길고
    근거는 짧아서, 자카드로 재면 근거 쪽 분모가 답변 길이에 눌려 조건 간 차이가
    묻힌다. 여기서 묻고 싶은 것은 "근거가 답변에 닿았는가" 한 방향이다.
    """
    a, b = bigrams(답변), bigrams(근거)
    if not b:
        return 0.0
    return len(a & b) / len(b)


def 유사도(x: str, y: str) -> float:
    """두 답변이 얼마나 닮았는가 (자카드). 길이가 비슷한 것끼리라 자카드로 충분하다."""
    a, b = bigrams(x), bigrams(y)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def 근거_텍스트(res: Any) -> str:
    """그 괘로 상담사가 손에 쥔 근거 전부 — 확정 근거 + 프롬프트에 실린 주석."""
    주석 = " ".join(e.content for e in res.evidences)
    return f"{res.raw_text} {주석}"


async def 한판(session, question: str, lines: List[int], clients) -> Dict[str, Any]:
    interp, evidence, _ = await run_interpret(
        session, question, manual_lines=lines, client=clients["interpret"],
    )
    turn = await run_counsel_turn(
        question, interp, turn_number=1, client=clients["counsel"],
    )
    return {
        "괘": evidence.original.hexagram_id,
        "괘이름": evidence.original.name_full,
        "초점": evidence.focus_rule.description_ko,
        "근거": 근거_텍스트(interp),
        "답변": turn.message,
    }


async def main_async(provider: str, repeats: int) -> None:
    clients = {
        "interpret": get_client(role="interpret", provider=provider),
        "counsel": get_client(role="counsel", provider=provider),
    }

    rows: List[Dict[str, Any]] = []
    총 = len(CASES) * len(HEXAGRAMS) * repeats
    for question in CASES:
        for 이름, lines in HEXAGRAMS:
            for r in range(repeats):
                # 케이스마다 세션을 새로 연다. 한 세션으로 전부 돌리면 느린 외부 호출
                # 사이에 커넥션이 유휴로 끊긴다 (compare_benui_tone.py가 겪은 자리).
                async with AsyncSessionLocal() as session:
                    판 = await 한판(session, question, lines, clients)
                판.update({"질문": question, "배치": 이름, "회차": r})
                rows.append(판)
                print(f"[{len(rows)}/{총}] {question[:16]}… × {이름} → 제{판['괘']}괘")

    보고(rows, repeats)


def 보고(rows: List[Dict[str, Any]], repeats: int) -> None:
    print("\n" + "=" * 72)

    # ── 1. 괘 판별 적중률 ───────────────────────────────────────────────
    # 답변이 자기 괘의 근거와 가장 닮았는가. 사연이 같으므로 답변에 섞인 사연
    # 어휘는 어느 비교에나 똑같이 들어가고, 갈라지는 것은 근거 쪽 어휘뿐이다.
    적중, 전체 = 0, 0
    표: List[str] = []
    for question in {r["질문"] for r in rows}:
        같은사연 = [r for r in rows if r["질문"] == question]
        근거들 = {(r["배치"], r["회차"]): r["근거"] for r in 같은사연}
        for r in 같은사연:
            점수 = {키: 포함도(r["답변"], 근거) for 키, 근거 in 근거들.items()}
            최고 = max(점수, key=점수.get)
            맞음 = 최고[0] == r["배치"]
            적중 += int(맞음)
            전체 += 1
            표.append(
                f"  {'○' if 맞음 else '✗'} {r['질문'][:14]}… × {r['배치']:<12} "
                f"자기근거 {점수[(r['배치'], r['회차'])]:.3f} / 최고 {점수[최고]:.3f} ({최고[0]})"
            )

    # 반복 회차가 여럿이면 같은 배치의 다른 회차도 정답으로 친다. 후보는 K×R이고
    # 그중 R개가 정답이므로 우연은 R/(K×R) = 1/K다 — 반복을 늘려도 변하지 않는다.
    우연 = 1.0 / len(HEXAGRAMS)
    print(f"[1] 괘 판별 적중률: {적중}/{전체} = {적중 / max(전체, 1):.1%}  (우연 {우연:.1%})")
    print("\n".join(표))

    # ── 2. 답변 쌍 유사도 (대조군 대비) ────────────────────────────────
    다른괘, 같은괘 = [], []
    for question in {r["질문"] for r in rows}:
        같은사연 = [r for r in rows if r["질문"] == question]
        for a, b in itertools.combinations(같은사연, 2):
            (다른괘 if a["배치"] != b["배치"] else 같은괘).append(유사도(a["답변"], b["답변"]))

    def 평균(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    print(f"\n[2] 답변 쌍 유사도")
    print(f"  괘가 다른 쌍      {평균(다른괘):.3f}  (n={len(다른괘)})")
    if 같은괘:
        print(f"  같은 괘 반복 쌍   {평균(같은괘):.3f}  (n={len(같은괘)}) ← 대조군")
        차 = 평균(같은괘) - 평균(다른괘)
        print(f"  차이              {차:+.3f}")
        print("  → 차이가 0에 가까우면 괘를 바꾼 것이 아무 일도 하지 않은 것이다.")
    else:
        print("  대조군 없음 — `-n 2` 이상으로 돌려야 같은 괘 반복 쌍이 생긴다.")

    # ── 3. 근거 도달도 ─────────────────────────────────────────────────
    도달 = [포함도(r["답변"], r["근거"]) for r in rows]
    print(f"\n[3] 근거 도달도(자기 괘): 평균 {평균(도달):.3f} · "
          f"최저 {min(도달):.3f} · 최고 {max(도달):.3f}")
    바닥 = sorted(rows, key=lambda r: 포함도(r["답변"], r["근거"]))[:3]
    print("  가장 낮은 셋 (근거가 답변에 닿지 않은 자리):")
    for r in 바닥:
        print(f"    {포함도(r['답변'], r['근거']):.3f}  {r['질문'][:14]}… × {r['배치']}")

    out = "/tmp/hexagram_effect.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n전문 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="사연을 고정하고 괘만 바꿔, 괘가 답변을 실제로 바꾸는지 잰다")
    ap.add_argument("-p", "--provider", default="ollama")
    ap.add_argument("-n", "--repeats", type=int, default=1,
                    help="같은 조합 반복 횟수. 2 이상이어야 대조군이 생긴다")
    args = ap.parse_args()
    asyncio.run(main_async(args.provider, args.repeats))


if __name__ == "__main__":
    main()
