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

**비용과 시간.** 3턴 세션 하나가 캐스팅 턴(안전+정리+해석+상담 4호출) + 후속 턴
2개(각 안전+상담 2호출) = 8호출이고, 실측 지연으로 세션당 1~1.5분이 든다. 배치를
넷으로 줄여 `-n 1`이면 12판(약 15~20분), `-n 2`면 24판(약 30~40분)이다.

**중간에 끊겨도 다시 처음부터 돌리지 않는다.** 조합 하나가 끝날 때마다 진행
파일(`/tmp/hexagram_effect_turns_{provider}_진행중.json`)에 남기므로,
`--resume`을 붙이면 거기서부터 잇는다. 그리고 진행 줄은 즉시 흘려보낸다 —
버퍼에 갇히면 "멈춤"과 "정상 진행"을 구분할 수 없다.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.pipeline import run_turn  # noqa: E402
from core.db import AsyncSessionLocal  # noqa: E402
from core.llm import get_client  # noqa: E402
from scripts import compare_hexagram_effect as CHE  # noqa: E402

def 말한다(*args: Any) -> None:
    """진행 상황을 즉시 흘려보낸다.

    `print`를 그냥 쓰면 안 된다. 출력이 파이프로 들어가는 환경(IDE 에이전트 등)에서는
    파이썬이 stdout을 버퍼에 쌓아두므로, 한 판이 1분 넘게 걸리고 조합이 열여덟 개인
    이 하네스는 몇십 분 동안 화면이 비어 있게 된다. 그러면 "멈춤"과 "정상 진행"을
    구분할 방법이 없다 — 실제로 그렇게 한 시간을 날렸다.
    """
    print(*args, flush=True)

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

# 배치는 `compare_hexagram_effect.HEXAGRAMS` 여섯 중 넷만 쓴다.
#
# 이 하네스는 한 조합이 3턴 8호출이라 여섯을 다 돌리면 `-n 1`에도 스무 판이 넘고
# 실측으로 한 시간을 넘겼다. 여기서 답할 질문은 "1턴 대비 2·3턴이 무너지는가"
# 하나뿐이고 그건 넷으로도 답이 나온다 — 우연선이 1/6에서 1/4로 올라가지만
# (판별 적중률을 그만큼 엄격하게 읽어야 한다), 정작 중요한 상용구·답변 쌍 지표는
# 쌍의 수로 결정되므로 배치가 줄어도 충분히 안정적이다.
#
# 초점 규칙이 서로 다른 자리를 남긴다 — 효사 둘(수산건) · 효사 하나(천산둔) ·
# 괘사(중천건) · 초점이 지괘로 넘어가는 자리(화풍정). 규칙이 같은 것만 남기면
# "괘가 다르다"가 아니라 "효사냐 괘사냐"만 재게 된다.
사용할_배치 = {"수산건 1·2효", "천산둔 2효", "중천건 무변", "화풍정 5변"}
HEXAGRAMS = [(이름, lines) for 이름, lines in CHE.HEXAGRAMS if 이름 in 사용할_배치]

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

    for turn_idx, message in enumerate(turns, start=1):
        # DB 세션은 **턴마다 새로 연다.** 한 세션으로 3턴을 묶으면 느린 외부 호출
        # 사이(턴당 20~30초)에 커넥션이 유휴로 끊긴다 — `compare_benui_tone.py`가
        # 실제로 그렇게 죽었고(asyncpg ConnectionDoesNotExistError) CLAUDE.md에
        # 적혀 있는 자리다. 대화 연속성은 `session_id`로 이어지므로 커넥션을
        # 붙들고 있을 이유가 없다. 매 턴 커밋되어 있다.
        async with AsyncSessionLocal() as session:
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
            말한다(f"  ⚠ {이름} {turn_idx}턴에서 정상 범위를 벗어남"
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


def 진행_경로(provider: str) -> str:
    return f"/tmp/hexagram_effect_turns_{provider}_진행중.json"


async def main_async(provider: str, repeats: int, 이어서: bool) -> None:
    clients = {
        role: get_client(role=role, provider=provider)
        for role in ("safety", "intake", "interpret", "counsel", "journal")
    }

    # 턴 번호별로 행을 따로 모은다. compare_hexagram_effect.보고()를 턴마다
    # 독립적으로 돌리기 위해서다.
    턴별_행: Dict[int, List[Dict[str, Any]]] = {1: [], 2: [], 3: []}
    끝난_조합: set = set()

    # 이어서 돌리기. 한 판이 1분 넘게 걸리고 조합이 여럿이라, 중간에 끊기면
    # 처음부터 다시 하는 것이 곧 요금이다. 진행 파일이 있으면 거기서부터 잇는다.
    경로 = 진행_경로(provider)
    if 이어서 and os.path.exists(경로):
        with open(경로, encoding="utf-8") as f:
            저장 = json.load(f)
        for k, rows in 저장.get("턴별_행", {}).items():
            턴별_행[int(k)] = rows
        끝난_조합 = {tuple(x) for x in 저장.get("끝난_조합", [])}
        말한다(f"이어서 돌린다 — 이미 끝난 조합 {len(끝난_조합)}개는 건너뛴다 ({경로})")

    def 저장한다() -> None:
        with open(경로, "w", encoding="utf-8") as f:
            json.dump(
                {"턴별_행": 턴별_행, "끝난_조합": [list(x) for x in 끝난_조합]},
                f, ensure_ascii=False,
            )

    총 = len(STORY_TURNS) * len(HEXAGRAMS) * repeats
    완료 = 0
    for q_idx in range(len(STORY_TURNS)):
        for 이름, lines in HEXAGRAMS:
            for r in range(repeats):
                완료 += 1
                조합 = (q_idx, 이름, r)
                if 조합 in 끝난_조합:
                    말한다(f"[{완료}/{총}] {이름} (r{r}) → 이미 끝남, 건너뜀")
                    continue

                결과 = await 세션_한판(q_idx, 이름, lines, clients)
                if 결과 is None:
                    말한다(f"[{완료}/{총}] {STORY_TURNS[q_idx][0][:16]}… × {이름} → 1턴부터 실패")
                    continue
                for turn_idx, row in 결과.items():
                    row["회차"] = r
                    턴별_행[turn_idx].append(row)
                끝난_조합.add(조합)
                # 조합 하나가 끝날 때마다 디스크에 남긴다. 중간에 죽어도 여기까지는
                # 건진다 — 맨 끝에만 쓰면 한 시간을 돌리고도 아무것도 안 남는다.
                저장한다()
                말한다(f"[{완료}/{총}] {STORY_TURNS[q_idx][0][:16]}… × {이름} "
                      f"→ {len(결과)}턴 확보 (누적 1턴 {len(턴별_행[1])}건)")

    말한다("\n" + "#" * 76)
    말한다(f"# 턴 번호별 결과 ({provider}, 반복 {repeats}회)")
    말한다("#" * 76)

    for turn_idx in sorted(턴별_행):
        rows = 턴별_행[turn_idx]
        if not rows:
            말한다(f"\n[{turn_idx}턴] 데이터 없음 — 전 조합이 이 턴 전에 안전 판정으로 끊겼다")
            continue
        말한다(f"\n[{turn_idx}턴] n={len(rows)}")
        out = f"/tmp/hexagram_effect_turns_{provider}_t{turn_idx}.json"
        # `보고()`는 우연선을 `CHE.HEXAGRAMS` 길이로 계산한다. 여기서는 배치를
        # 넷으로 줄여 쓰므로 그 값을 잠시 바꿔 끼운다 — 안 바꾸면 우연선이 1/6로
        # 찍혀 적중률을 실제보다 후하게 읽는다.
        원래_배치 = CHE.HEXAGRAMS
        CHE.HEXAGRAMS = HEXAGRAMS
        try:
            CHE.보고(rows, repeats, provider=provider, out_path=out)
        finally:
            CHE.HEXAGRAMS = 원래_배치

    말한다("\n" + "=" * 76)
    말한다("읽는 법: 1턴 수치는 compare_hexagram_effect.py의 기존 실측과 같은 잣대다 —")
    말한다("여기서 크게 벗어나면 이 하네스 자체를 의심할 것. 2·3턴이 1턴 대비 무너지면")
    말한다("(판별 적중률 하락, 다른괘 공유 상승) 매핑·근거가 후속 턴에서 실제로")
    말한다("안 쓰이고 있다는 뜻이다 — CLAUDE.md 「배포 전에 남은 것」의 재검색 발동률")
    말한다("실측과 같은 자리를 가리킨다.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="다턴 세션에서도 괘가 답변을 실제로 바꾸는지 잰다 (실제 파이프라인)")
    ap.add_argument("-p", "--provider", default="ollama")
    ap.add_argument("-n", "--repeats", type=int, default=1,
                    help="같은 조합 반복 횟수. 2 이상이어야 대조군이 생긴다")
    ap.add_argument("--resume", action="store_true",
                    help="중간에 끊긴 실행을 이어서 돌린다 (진행 파일에서 복구)")
    args = ap.parse_args()
    asyncio.run(main_async(args.provider, args.repeats, args.resume))


if __name__ == "__main__":
    main()
