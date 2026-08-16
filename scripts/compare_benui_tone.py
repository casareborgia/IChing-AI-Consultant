#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""본의를 넣으면 답변의 톤이 예언 쪽으로 당겨지는가.

    python scripts/compare_benui_tone.py -p ollama

CLAUDE.md 데이터 레이어 절이 본의를 미뤄뒀던 이유가 톤이었다. 정전은 의리(義理)
중심이라 "이 상황에서 어떻게 처신할 것인가"를 논하고, 본의는 점법(占法) 중심이라
"이 괘를 얻으면 이렇다"를 말한다. 이 앱은 예언이 아니라 의사결정 지원을 표방하므로
(포지셔닝 절) 그 차이가 답변에 배어나오는지를 봐야 한다.

**왜 score_agents로는 안 되는가.** 그쪽은 `search_chunks`를 스텁으로 갈아끼운다
(재현성을 위해 일부러 그렇게 해뒀다). 그래서 인덱스에 무엇이 들었든 결과가 같다.
여기서는 진짜 검색을 태운다.

**같은 인덱스에서 켜고 끈다.** 인덱스를 두 벌 만들어 비교하면 임베딩 시점이나
행 수 같은 것까지 함께 달라져 무엇이 원인인지 말할 수 없다. `k_benui`만 0과 2로
바꿔 같은 질문을 두 번 돌린다.

두 층위를 잰다.
  1. 자료 자체 — 검색된 한글 주석에 점단 어휘가 얼마나 있는가 (모델 무관, 결정적)
  2. 답변 — 그 근거로 만든 상황 매핑에 단정적 예언 표현이 있는가
"""

import argparse
import asyncio
import json
import os
import re
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.interpret import run_interpret  # noqa: E402
from core.db import AsyncSessionLocal  # noqa: E402
from core.llm import get_client  # noqa: E402
from scripts.score_agents import PREDICTION  # noqa: E402

# 점단(占斷) 어휘. 본의가 정전보다 이런 말을 자주 쓰는지 보려는 것이지, 이 말이
# 나쁘다는 뜻이 아니다 — 원문이 그렇게 쓰였으면 번역도 그래야 한다.
점단어 = ["점", "얻으면", "길하다", "흉하다", "이롭다", "허물이 없다", "占"]

# 사람이 답을 정해둘 수 없는 질문들이라 정답을 채점하지 않는다. 어느 쪽이 더
# 단정적인지만 본다. 동효 배치는 초점 규칙이 서로 다른 경우를 고루 넣었다.
CASES = [
    ("이직을 해야 할지 고민입니다", [7, 7, 7, 7, 7, 7]),          # 동효 0 — 괘사
    ("지금 고백해도 될까요", [9, 7, 7, 7, 7, 7]),                  # 동효 1 — 효사
    ("동업 제안을 받았는데 사람을 믿어도 될지 모르겠습니다", [9, 8, 7, 7, 6, 7]),  # 동효 3
    ("회사를 그만두고 공부를 다시 시작할까 합니다", [9, 6, 9, 6, 9, 7]),          # 동효 5 — 지괘
    ("부모님과 몇 년째 말을 안 하고 지냅니다", [8, 8, 8, 7, 7, 7]),
    ("맡은 일이 버거운데 티를 내면 안 될 것 같습니다", [7, 9, 7, 6, 7, 7]),
]


def 센다(text: str, words: List[str]) -> Dict[str, int]:
    return {w: text.count(w) for w in words if w in text}


async def 한번(session, question, lines, client, k_benui: int) -> Dict[str, Any]:
    res, evidence, chunks = await run_interpret(
        session, question, manual_lines=lines, client=client, k_benui=k_benui,
    )
    근거 = "\n".join(c.content_ko for c in chunks)
    return {
        "괘": evidence.original.hexagram_id,
        "청크수": len(chunks),
        "본의청크": sum(1 for c in chunks if c.source_type.startswith("benui")),
        "근거_점단어": 센다(근거, 점단어),
        "매핑": res.contextual_mapping,
        "매핑_예언표현": [w for w in PREDICTION if w in res.contextual_mapping],
    }


async def main_async(provider: str, repeats: int) -> None:
    client = get_client(role="interpret", provider=provider)
    rows = []

    async with AsyncSessionLocal() as session:
        for question, lines in CASES:
            for r in range(repeats):
                끄고 = await 한번(session, question, lines, client, 0)
                켜고 = await 한번(session, question, lines, client, 2)
                rows.append({"질문": question, "반복": r, "정전만": 끄고, "본의포함": 켜고})
                print(f"[{len(rows)}/{len(CASES) * repeats}] {question[:20]}… "
                      f"본의청크 {켜고['본의청크']}개")

    def 합(키, 필드):
        return sum(len(row[키][필드]) for row in rows)

    print("\n" + "=" * 62)
    print(f"{'':10} {'근거 점단어(종류)':>18} {'매핑 예언표현':>14}")
    for 키 in ("정전만", "본의포함"):
        print(f"{키:10} {합(키, '근거_점단어'):>18} {합(키, '매핑_예언표현'):>14}")

    위반 = [(row["질문"], row[키]["매핑_예언표현"], 키)
            for row in rows for 키 in ("정전만", "본의포함") if row[키]["매핑_예언표현"]]
    if 위반:
        print("\n단정적 예언이 나온 자리:")
        for q, ws, 키 in 위반:
            print(f"  [{키}] {q[:24]}… → {ws}")

    out = "/tmp/benui_tone.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n전문 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="본의 적재 전후 톤 대조 (같은 인덱스, k_benui만 토글)")
    ap.add_argument("-p", "--provider", default="ollama")
    ap.add_argument("-n", "--repeats", type=int, default=1)
    args = ap.parse_args()
    asyncio.run(main_async(args.provider, args.repeats))


if __name__ == "__main__":
    main()
