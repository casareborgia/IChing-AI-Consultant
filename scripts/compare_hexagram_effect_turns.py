#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""괘 효과가 후속 턴에서도 유지되는가 — 실제 파이프라인으로 다턴 세션을 돌려 잰다.

    python scripts/compare_hexagram_effect_turns.py -p gemini -n 2

`compare_hexagram_effect.py`와 `measure_boilerplate.py`는 전부 **1턴만** 잰다.
`run_interpret`·`run_counsel_turn`을 직접 불러 그 자리에서 끝내기 때문이다. 그런데
이번 결함 수정의 절반 — 상황 매핑 저장(`counsel_turns.contextual_mapping`)과 근거
주석 저장(`counsel_turns.evidence_items`) — 은 **후속 턴에서만 작동한다.** 1턴만
재는 하네스로는 이 절반이 실제로 도착하는지 확인할 수 없다.

원래 신고 사례를 봐도 뉘앙스가 가장 겹쳤던 자리는 4·5번째 턴이었다(대화가 "만남"에서
"주점 운영"으로 옮겨간 자리). CLAUDE.md의 재검색 발동률 실측도 같은 구멍을 가리킨다 —
모델이 스스로 재검색을 트리거하는 일은 0회였고, 지금 도는 재검색은 `asks_for_grounds`가
"왜 그렇게 보시나요" 류의 명시적 질문을 코드로 잡을 때뿐이다. 화제가 조용히 옮겨가는
경우(관계 얘기인 줄 알았는데 시기 문제였던 경우)는 아무도 잡지 않는다.

**그래서 진짜 파이프라인을 태운다.** `agents.pipeline.run_turn`을 그대로 불러 DB에
쓰고 읽는다 — 저장·복원 경로가 실제로 작동하는지까지 함께 재는 것이 목적이다.
`compare_hexagram_effect.py`처럼 스텁 검색을 쓰지 않는다.

**시나리오는 3턴이고, 2·3턴에 의도적으로 화제 드리프트를 넣었다** — 처음 화두(가게
전환·이별 고민·부모 갈등)에서 옆 국면(대출금 부담·후련함이라는 감정의 낯섦·부모의
동기에 대한 의심)으로 옮겨간다. 드리프트가 없으면 이 하네스도 "1턴 다리가 세션
내내 버틴다"는 것만 확인하고 끝나, 정작 걱정하는 상황(화제가 옮겨갔을 때)을
비켜 간다.

**측정은 턴 번호별로 따로 낸다.** 1턴·2턴·3턴 각각에 대해
`compare_hexagram_effect.보고()`(판별 적중률·답변 쌍 유사도·근거 도달도·상용구)를
그대로 돌린다 — 같은 6배치·같은 자를 쓰므로 1턴 결과는 기존 실측과 바로 비교된다.
턴이 깊어질수록 지표가 무너지면 매핑·근거가 후속 턴에서 실제로 안 쓰이고 있다는
뜻이고, 유지되면 저장·복원 경로가 제 몫을 하고 있다는 뜻이다.

**비용.** 3턴 세션 하나가 캐스팅 턴(안전+정리+해석+상담 4호출) + 후속 턴 2개(각
안전+상담 2호출) = 8호출이다. `-n 2`면 3사연 × 6배치 × 2회 × 8호출 = 288회 —
어제 한 회차와 비슷한 규모다. `-n 1`이면 대조군 없이 방향만 본다.
"""

import argparse
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.pipeline import run_turn  # noqa: E402
from core.db import AsyncSessionLocal  # noqa: E402
from core.llm import get_client  # noqa: E402
from scripts import compare_hexagram_effect as CHE  # noqa: E402

# 각 사연의 1턴은 `compare_hexagram_effect.CASES`와 글자 그대로 같다 — 1턴 결과가
# 기존 단일 턴 실측과 어긋나면 안 되므로 표현을 새로 쓰지 않는다.
#
# 2·3턴은 처음 화두에서 옆 국면으로 드리프트한다. GROUNDS_PATTERNS(agents/counsel.py)
# 어느 문구와도 겹치지 않게 골랐다 — 겹치면 재검색이 돌아 이 하네스가 "화제 드리프트"가
# 아니라 "근거를 물어온 턴"을 재게 된다.
STORY_TURNS: List[List[str]] = [
    [
        "30년 하던 가게를 접고 업종을 바꿀지 고민입니다. 이것밖에 해본 게 없어 막막합니다.",
        "사실 가게를 접는 것보다 남은 대출금을 어떻게 갚을지가 더 걱정입니다.",
        "이 상황을 자식들한테는 어떻게 설명해야 할지도 모르겠어요.",
    ],
    [
        "7년 만난 사람과 헤어질지 계속 갈지 모르겠습니다. 미워서가 아니라 아무 느낌이 없어서요.",
        "헤어진다는 상상을 하면 무섭기보다 후련한 느낌이 들어서 그게 더 혼란스러워요.",
        "주변에서는 다들 좋은 사람이라며 놓치지 말라고 하는데, 저만 이상한 건가 싶어요.",
    ],
    [
        "부모님이 제 진로를 계속 반대하셔서 대화가 막혔습니다.",
        "반대하시는 이유를 들어보면 저를 위해서라기보다 체면 때문인 것 같아서 더 화가 납니다.",
        "이제는 대화를 포기하고 그냥 제 뜻대로 밀고 나가야 하나 고민입니다.",
    ],
]

# 안전 판정이 정상(NORMAL·CAUTION) 범위를 벗어나면 그 턴은 괘 상담이 아니라
# 안내문이 나간다 — 근거 도달도를 잴 대상이 아니다. 이 밖으로 튄 조합은
# 경고를 찍고 그 이후 턴을 건너뛴다.
정상_안전_판정 = {"NORMAL", "CAUTION"}


def 근거_텍스트(res: Any) -> str:
    """상담사가 그 턴에 손에 쥔 근거 전부 — 확정 근거 + 프롬프트에 실린 주석.

    `compare_hexagram_effect.근거_텍스트`와 정의를 맞춘다. 1턴 결과를 그쪽 실측과
    바로 견줄 수 있어야 하기 때문이다.
    """
    주석 = " ".join(e.get("content", "") for e in (res.evidences or []))
    return f"{res.raw_text or ''} {주석}".strip()


async def 세션_한판(
    question_idx: int, 이름: str, lines: List[int], clients: Dict[str, Any],
) -> Optional[Dict[int, Dict[str, Any]]]:
    """사연 하나를 3턴 끝까지 돌리고, 턴 번호별 측정용 행을 돌려준다.

    익명(user_id=None)으로 돈다. 사용자를 지정하면 정리 에이전트가 과거 세션과
    대조해 재삼독(중복 질의) 판정을 시도하는데, 같은 사연 문구를 배치·회차마다
    반복해서 넣으므로 실제로는 다른 실험인데 "같은 질문"으로 잡힐 수 있다.
    익명이면 대조할 과거가 없어 이 위험이 구조적으로 없다.
    """
    turns = STORY_TURNS[question_idx]
    session_id = None
    결과: Dict[int, Dict[str, Any]] = {}
    누적_질문 = ""

    async with AsyncSessionLocal() as session:
        for turn_idx, message in enumerate(turns, start=1):
            res = await run_turn(
                session,
                counsel_session_id=session_id,
                user_id=None,
                message=message,
                manual_lines=lines if turn_idx == 1 else None,
                clients=clients,
            )
            session_id = res.session_id
            누적_질문 = (누적_질문 + "\n" + message).strip()

            if res.safety_category not in 정상_안전_판정 or not res.raw_text:
                # 안전 스크리닝이 튀었거나(ASK 등) 아직 괘가 없다. 이 조합은
                # 화제 드리프트를 재려던 것이지 안전 경계를 재려던 게 아니므로
                # 여기서 접고, 앞선 턴까지의 결과만 돌려준다.
                print(f"  ⚠ {이름} {turn_idx}턴에서 정상 범위를 벗어남"
                      f"({res.safety_category}) — 이후 턴 건너뜀")
                break

            결과[turn_idx] = {
                # 턴 N의 "질문"은 1턴부터 N턴까지의 누적 발화다. measure_boilerplate가
                # 이 문자열에서 어절을 뽑아 상용구 후보에서 제외하므로, 지금까지 나온
                # 사연 전체를 담아야 상담사가 사연을 되짚는 말을 오진하지 않는다.
                "질문": 누적_질문,
                "배치": 이름,
                "회차": None,  # main_async에서 채운다
                "근거": 근거_텍스트(res),
                "답변": res.user_facing_message,
            }

    return 결과 or None


async def main_async(provider: str, repeats: int) -> None:
    clients = {
        role: get_client(role=role, provider=provider)
        for role in ("safety", "intake", "interpret", "counsel", "journal")
    }

    # 턴 번호별로 행을 따로 모은다. compare_hexagram_effect.보고()를 턴마다
    # 독립적으로 돌리기 위해서다.
    턴별_행: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: []}

    총 = len(STORY_TURNS) * len(CHE.HEXAGRAMS) * repeats
    완료 = 0
    for q_idx in range(len(STORY_TURNS)):
        for 이름, lines in CHE.HEXAGRAMS:
            for r in range(repeats):
                결과 = await 세션_한판(q_idx, 이름, lines, clients)
                완료 += 1
                if 결과 is None:
                    print(f"[{완료}/{총}] {STORY_TURNS[q_idx][0][:16]}… × {이름} → 1턴부터 실패")
                    continue
                for turn_idx, row in 결과.items():
                    row["회차"] = r
                    턴별_행[turn_idx].append(row)
                print(f"[{완료}/{총}] {STORY_TURNS[q_idx][0][:16]}… × {이름} "
                      f"→ {len(결과)}턴 확보")

    print("\n" + "#" * 76)
    print(f"# 턴 번호별 결과 ({provider}, 반복 {repeats}회)")
    print("#" * 76)

    for turn_idx in sorted(턴별_행):
        rows = 턴별_행[turn_idx]
        if not rows:
            print(f"\n[{turn_idx}턴] 데이터 없음 — 전 조합이 이 턴 전에 안전 판정으로 끊겼다")
            continue
        print(f"\n[{turn_idx}턴] n={len(rows)}")
        out = f"/tmp/hexagram_effect_turns_{provider}_t{turn_idx}.json"
        CHE.보고(rows, repeats, provider=provider, out_path=out)

    print("\n" + "=" * 76)
    print("읽는 법: 1턴 수치는 compare_hexagram_effect.py의 기존 실측과 같은 잣대다 —")
    print("여기서 크게 벗어나면 이 하네스 자체를 의심할 것. 2·3턴이 1턴 대비 무너지면")
    print("(판별 적중률 하락, 다른괘 공유 상승) 매핑·근거가 후속 턴에서 실제로")
    print("안 쓰이고 있다는 뜻이다 — CLAUDE.md 「배포 전에 남은 것」의 재검색 발동률")
    print("실측과 같은 자리를 가리킨다.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="다턴 세션에서도 괘가 답변을 실제로 바꾸는지 잰다 (실제 파이프라인)")
    ap.add_argument("-p", "--provider", default="ollama")
    ap.add_argument("-n", "--repeats", type=int, default=1,
                    help="같은 조합 반복 횟수. 2 이상이어야 대조군이 생긴다")
    args = ap.parse_args()
    asyncio.run(main_async(args.provider, args.repeats))


if __name__ == "__main__":
    main()
