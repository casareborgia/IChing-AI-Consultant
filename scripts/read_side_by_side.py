#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""저장된 결과를 사람이 읽도록 나란히 놓는다.

    python scripts/read_side_by_side.py
    python scripts/read_side_by_side.py --turn 2 -o /tmp/2턴만.md

**왜 지표가 아니라 이걸 만드는가.** 여기까지 오면서 자를 네 번 만들고 세 번 고쳤다.
어휘 겹침으로 "답변이 괘를 반영하는가"를 재는 것은 대리 지표라, 상담 뼈대·안내문·근거
길이가 계속 끼어들고 그때마다 보정이 하나씩 붙었다. 그런데 **정작 실제 발견은 전부
사람이 목록을 읽어서 나왔다** — "주역에서는 지금의 상황을" 35회도, CAUTION 안내문
오염도 숫자가 아니라 눈으로 찾은 것이다. 지표는 어디를 볼지 좁혀줬을 뿐이다.

그래서 이 스크립트는 판정하지 않는다. **같은 사연에 괘만 다른 답변들을 나란히 놓고,
눈이 갈 자리를 표시해 줄 뿐이다.** 모델을 부르지 않는다.

**CAUTION 안내문은 걷어낸다.** CAUTION 판정이면 모든 괘의 답변 끝에 똑같은 안내문이
붙는다. 그건 괘와 무관한 고정 문구라 읽는 데 방해만 되고, 실제로 2턴 상용구 지표를
14.4%까지 부풀린 범인이었다. 문구는 `agents.safety`에서 직접 가져온다 — 복사해 두면
원본이 바뀔 때 갈라진다(진단어 목록에서 이미 겪은 일이다).

**공유 문구를 표시한다.** 그 묶음의 답변 둘 이상에 그대로 나오는 어절 뭉치를 아래에
모아 준다. 질문에 있던 말은 뺀다 — 상담사가 사연을 되짚는 것은 증상이 아니라 공감이다.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Sequence, Set, Tuple

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.safety import caution_append_message  # noqa: E402
from scripts.measure_boilerplate import ngrams, 어절들  # noqa: E402

기본_경로 = "/tmp/hexagram_effect_turns_{provider}_t{turn}.json"


def 안내문_걷어내기(답변: str) -> Tuple[str, bool]:
    """CAUTION 안내문을 떼어낸다. (본문, 붙어있었는지)"""
    안내문 = caution_append_message().strip()
    if 안내문 and 안내문 in 답변:
        return 답변.replace(안내문, "").strip(), True
    return 답변.strip(), False


def 근거_요약(근거: str) -> List[str]:
    """근거 덩어리에서 사람이 볼 머리 몇 줄만 뽑는다.

    `근거`는 확정 근거 요약과 주석이 한 덩어리로 붙어 있다. 여기서는 어느 괘의
    어느 효를 보고 있는지만 보이면 되므로 그 줄들만 추린다.
    """
    줄들 = []
    for line in (근거 or "").splitlines():
        line = line.strip()
        if line.startswith(("본괘:", "지괘:", "해석 초점:", "- [")):
            줄들.append(line)
    return 줄들


def 공유_문구(답변들: Sequence[str], 질문: str, 최소_괘수: int = 2) -> List[Tuple[str, int]]:
    """둘 이상의 답변에 그대로 나오는 어절 뭉치. 질문에 있던 말은 뺀다."""
    질문_ngram: Set[Tuple[str, ...]] = set(ngrams(어절들(질문)))
    등장: Dict[Tuple[str, ...], int] = defaultdict(int)
    for 답변 in 답변들:
        for g in set(ngrams(어절들(답변))):
            if g not in 질문_ngram:
                등장[g] += 1
    걸린 = [(" ".join(g), c) for g, c in 등장.items() if c >= 최소_괘수]
    return sorted(걸린, key=lambda kv: -kv[1])[:15]


def 읽기(provider: str, turns: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    out: Dict[int, List[Dict[str, Any]]] = {}
    for t in turns:
        경로 = 기본_경로.format(provider=provider, turn=t)
        if not os.path.exists(경로):
            print(f"⚠ 없음: {경로}", file=sys.stderr)
            continue
        with open(경로, encoding="utf-8") as f:
            out[t] = json.load(f)
    return out


def 쓴다(턴별: Dict[int, List[Dict[str, Any]]]) -> str:
    줄: List[str] = [
        "# 같은 사연, 다른 괘 — 나란히 읽기",
        "",
        "판정하지 않는다. 눈으로 견주기 위한 것이다.",
        "",
        "**읽을 때 물을 것** — 이 넷이 *다른 괘* 이야기로 읽히는가, 아니면 같은 말에",
        "괘 이름만 갈아끼운 것으로 읽히는가. 후자라면 **어디가** 같은지 지목할 것.",
        "그 지목이 다음 처방의 입력이다.",
        "",
        "CAUTION 안내문은 걷어냈다(붙어 있던 답변에는 표시해 둔다).",
        "",
    ]

    for turn_idx in sorted(턴별):
        rows = 턴별[turn_idx]
        줄 += [f"---", "", f"# {turn_idx}턴", ""]

        사연별: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            사연별[r["질문"]].append(r)

        for 질문, 묶음 in 사연별.items():
            첫_발화 = 질문.splitlines()[0]
            줄 += [f"## {첫_발화[:40]}…", ""]

            if turn_idx > 1:
                이번_발화 = 질문.splitlines()[-1]
                줄 += [f"> **이번 턴 발화:** {이번_발화}", ""]

            본문들 = []
            for r in sorted(묶음, key=lambda x: x["배치"]):
                본문, 안내 = 안내문_걷어내기(r["답변"])
                본문들.append(본문)
                줄 += [f"### {r['배치']}" + ("  · *(CAUTION 안내문 제거됨)*" if 안내 else ""), ""]
                근거줄 = 근거_요약(r["근거"])
                if 근거줄:
                    줄 += ["```"] + 근거줄 + ["```", ""]
                줄 += [본문, ""]

            공유 = 공유_문구(본문들, 질문)
            if 공유:
                줄 += ["**이 넷이 공유하는 문구** (몇 개 답변에 나오는가)", ""]
                줄 += [f"- {c}개 — `{문구}`" for 문구, c in 공유]
                줄 += [""]
            else:
                줄 += ["*공유하는 어절 뭉치 없음 — 넷이 서로 다른 말을 했다는 뜻이다.*", ""]

    return "\n".join(줄)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="저장된 다턴 결과를 같은 사연 × 다른 괘로 나란히 놓는다 (모델 호출 없음)")
    ap.add_argument("-p", "--provider", default="gemini")
    ap.add_argument("--turn", type=int, action="append",
                    help="특정 턴만. 여러 번 줄 수 있다. 안 주면 1·2·3턴 전부")
    ap.add_argument("-o", "--output", default="/tmp/hexagram_side_by_side.md")
    args = ap.parse_args()

    turns = args.turn or [1, 2, 3]
    턴별 = 읽기(args.provider, turns)
    if not 턴별:
        sys.exit("읽을 결과 파일이 없다. compare_hexagram_effect_turns.py를 먼저 돌릴 것.")

    본문 = 쓴다(턴별)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(본문)

    총 = sum(len(v) for v in 턴별.values())
    print(f"{총}판 → {args.output}")
    print(f"열어서 읽을 것: open {args.output}")


if __name__ == "__main__":
    main()
