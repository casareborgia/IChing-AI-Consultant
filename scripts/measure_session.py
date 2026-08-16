#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""세션 하나가 무엇을 얼마나 쓰는지 잰다 — 리팩터 전 기준선.

    python scripts/measure_session.py -p ollama -n 3

배포 리팩터는 토큰과 지연을 줄이겠다고 말한다. 줄었는지 판정하려면 **줄이기 전
숫자**가 있어야 한다. 리팩터 후에 재면 좋아졌는지 나빠졌는지 비교할 대상이 없다.

역할별로 호출 수 · 프롬프트 크기 · 생성 토큰 · 시간을 따로 낸다. 합계만 보면
어디를 줄여야 할지 알 수 없기 때문이다 — 안전 스크리너는 매 턴 도는 유일한
에이전트라 호출 수가 많고, 상담은 근거가 실려 프롬프트가 크다. 성격이 다르다.

지연은 provider에 따라 크게 다르므로 절대값보다 **구성 비율**을 본다.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.pipeline import run_turn  # noqa: E402
from core.db import AsyncSessionLocal  # noqa: E402
from core.llm import get_client  # noqa: E402

# 한 세션의 전형적인 흐름. 근거를 묻는 턴을 일부러 넣는다 — 검색 결과가 프롬프트에
# 실려 가장 커지는 자리이고, 리팩터가 줄이겠다고 말하는 바로 그 지점이다.
대화 = [
    "직장을 옮길지 몇 달째 결정을 못 하고 있습니다",
    "안정적이긴 한데 성장이 멈춘 느낌이라 답답합니다",
    "왜 그렇게 보시나요? 무슨 근거로 그렇게 말씀하시는 건가요?",
    "덕분에 도움이 많이 됐어요. 고맙습니다",
]


class 계측:
    def __init__(self, role: str, provider: str):
        self.role = role
        self.client = get_client(role=role, provider=provider)
        self.기록: List[Dict[str, Any]] = []

    def complete_json(self, user: str, *, system: str = "", **kw):
        t0 = time.time()
        try:
            out = self.client.complete_json(user, system=system, **kw)
        finally:
            초 = time.time() - t0
            timing = getattr(self.client, "last_timing", None) or {}
            self.기록.append({
                "역할": self.role,
                "프롬프트_자": len(system) + len(user),
                "프롬프트_토큰": timing.get("prompt_tokens"),
                "생성_토큰": timing.get("gen_tokens"),
                "초": round(초, 2),
            })
        return out


async def main_async(provider: str, repeats: int) -> None:
    계측기 = {r: 계측(r, provider) for r in
              ("safety", "intake", "interpret", "counsel", "journal")}

    턴시간: List[float] = []
    async with AsyncSessionLocal() as session:
        for run in range(repeats):
            sid = None
            for msg in 대화:
                t0 = time.time()
                res = await run_turn(session, counsel_session_id=sid,
                                     user_id=f"measure_{run}_{int(time.time())}"[:20],
                                     message=msg, clients=계측기)
                턴시간.append(time.time() - t0)
                sid = res.session_id or sid
                if res.is_final:
                    break
            print(f"  세션 {run + 1}/{repeats} 완료")

    전체 = [r for m in 계측기.values() for r in m.기록]
    세션당 = lambda v: v / repeats  # noqa: E731

    print("\n" + "=" * 72)
    print(f"{'역할':10} {'호출':>6} {'프롬프트(자)':>14} {'프롬프트(토큰)':>14} "
          f"{'생성(토큰)':>12} {'중앙 지연':>10}")
    for role, m in 계측기.items():
        if not m.기록:
            continue
        자 = sum(r["프롬프트_자"] for r in m.기록)
        pt = sum(r["프롬프트_토큰"] or 0 for r in m.기록)
        gt = sum(r["생성_토큰"] or 0 for r in m.기록)
        중앙 = statistics.median(r["초"] for r in m.기록)
        print(f"{role:10} {세션당(len(m.기록)):6.1f} {세션당(자):14,.0f} "
              f"{세션당(pt):14,.0f} {세션당(gt):12,.0f} {중앙:9.1f}초")

    자합 = sum(r["프롬프트_자"] for r in 전체)
    pt합 = sum(r["프롬프트_토큰"] or 0 for r in 전체)
    gt합 = sum(r["생성_토큰"] or 0 for r in 전체)
    print("-" * 72)
    print(f"{'세션당':10} {세션당(len(전체)):6.1f} {세션당(자합):14,.0f} "
          f"{세션당(pt합):14,.0f} {세션당(gt합):12,.0f} "
          f"{statistics.median(턴시간):9.1f}초/턴")

    최대 = max(전체, key=lambda r: r["프롬프트_자"])
    print(f"\n가장 큰 프롬프트: {최대['역할']} {최대['프롬프트_자']:,}자 "
          f"({최대['프롬프트_토큰']} 토큰) — 리팩터가 줄이겠다고 하는 자리")

    out = "/tmp/session_baseline.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"provider": provider, "repeats": repeats, "records": 전체},
                  f, ensure_ascii=False, indent=2)
    print(f"전문 → {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description="세션당 토큰·지연 기준선")
    ap.add_argument("-p", "--provider", default="ollama")
    ap.add_argument("-n", "--repeats", type=int, default=3)
    args = ap.parse_args()
    asyncio.run(main_async(args.provider, args.repeats))


if __name__ == "__main__":
    main()
