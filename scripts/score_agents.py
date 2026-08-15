"""에이전트 4종이 주어진 모델로 돌아가는지 잰다.

    python scripts/score_agents.py -p ollama -m gemma4:26b
    python scripts/score_agents.py -p anthropic
    python scripts/score_agents.py -p ollama -a counsel      # 한 에이전트만

**정답을 매기지 않는다.** 정리 에이전트가 주제를 '커리어'로 부를지 '진로'로
부를지에 정답은 없다. 여기서 보는 것은 셋이다.

  형식      유효한 JSON인가, 스키마 필드가 다 있고 타입이 맞는가
  제약      에이전트별 규칙을 지키는가 (한문 금지, 진단 금지, 되묻기 등)
  지연      건당 몇 초인가. 한 턴에 두 번 부르는 자리도 있다

셋 다 규칙으로 판정되므로 LLM 심판이 필요 없다. 비용이 들지 않고 결정적이라
모델을 갈아끼우며 반복해도 된다. "말이 자연스러운가"는 여기서 재지 않는다 —
그건 `run_transcripts.py`가 뽑은 대화록을 사람이 읽어야 한다.

안전 스크리너는 `score_safety.py`가 따로 채점한다. 거기는 정답이 있다.
"""
import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete

from agents.counsel import MAX_TURNS_LIMIT, run_counsel_turn
from agents.intake import run_intake
from agents.interpret import run_interpret
from agents.journal import write_journal
from core.db import AsyncSessionLocal
from core.llm import get_client
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from core.rag import RetrievedChunk
from schemas.counsel import HexagramInterpretationSchema

FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "agent_cases.json"

CJK = re.compile(r"[一-鿿]")
# 진단성 발언. 설계 원칙 4 — 병명·약물·의학적 판단 금지
DIAGNOSIS = ("우울증", "불안장애", "공황장애", "조울", "ADHD", "처방", "복용", "투약", "진단됩니다", "진단입니다")
# 단정적 예언. 포지셔닝 — 예언자가 아니라 상담사
PREDICTION = ("반드시 성공", "반드시 실패", "무조건 성공", "무조건 실패", "틀림없이", "운명입니다", "정해져 있습니다")

# 해석 에이전트 시험에 쓰는 고정 청크. 실제 RAG를 부르면 임베딩 비용이 들고
# 검색 결과가 흔들려 모델의 능력만 떼어 볼 수 없다.
STUB_CHUNKS = [
    RetrievedChunk(
        chunk_id="stub-1", hexagram_id=0, line_number=None, source_type="guasa_comm",
        category="annotation", content="(원문 생략)",
        content_ko="때가 이르지 않았으면 기다리고, 이르렀으면 머뭇거리지 않는다.", similarity=0.8,
    ),
    RetrievedChunk(
        chunk_id="stub-2", hexagram_id=0, line_number=None, source_type="sosang_comm",
        category="annotation", content="(원문 생략)",
        content_ko="자리에 맞지 않으면 나아가도 이루지 못한다.", similarity=0.7,
    ),
]


class Check:
    """한 건에 대한 판정 결과."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.format_ok = False
        self.violations: List[str] = []
        self.seconds = 0.0
        self.error: Optional[str] = None

    @property
    def constraint_ok(self) -> bool:
        return self.format_ok and not self.violations


def _text_checks(text: str, *, where: str, violations: List[str]) -> None:
    """어느 에이전트에나 걸리는 공통 규칙."""
    if CJK.search(text):
        found = "".join(sorted(set(CJK.findall(text))))[:8]
        violations.append(f"{where}에 한자({found})")
    for word in DIAGNOSIS:
        if word in text:
            violations.append(f"{where}에 진단성 표현('{word}')")
            break
    for word in PREDICTION:
        if word in text:
            violations.append(f"{where}에 단정적 예언('{word}')")
            break


async def run_intake_cases(cases: List[Dict], client) -> List[Check]:
    out = []
    for case in cases:
        chk = Check(case["id"])
        past = case.get("past") or []
        valid_ids = {p["session_id"] for p in past}
        t0 = time.time()
        try:
            res = await run_intake(case["message"], past_sessions=past, client=client)
            chk.seconds = time.time() - t0
            chk.format_ok = True

            if not (res.clarified_question or "").strip():
                chk.violations.append("clarified_question이 비었다")
            if not (res.topic_category or "").strip():
                chk.violations.append("topic_category가 비었다")
            _text_checks(res.clarified_question, where="정리된 질문", violations=chk.violations)

            ref = res.duplicate_session_ref
            if ref and ref not in valid_ids:
                chk.violations.append(f"후보에 없는 세션 ID({ref})")
            if res.is_duplicate_question and not ref:
                chk.violations.append("중복이라면서 참조 세션이 없다")
        except Exception as e:  # noqa: BLE001
            chk.seconds = time.time() - t0
            chk.error = f"{type(e).__name__}: {e}"
        out.append(chk)
    return out


async def run_interpret_cases(cases: List[Dict], client, session) -> List[Check]:
    import agents.interpret as interpret_mod

    async def stub_search(*args, **kwargs):
        return list(STUB_CHUNKS)

    original = interpret_mod.search_chunks
    interpret_mod.search_chunks = stub_search
    try:
        out = []
        for case in cases:
            chk = Check(case["id"])
            t0 = time.time()
            try:
                res, evidence, _ = await run_interpret(
                    session, case["clarified_question"],
                    manual_lines=case["manual_lines"], client=client,
                )
                chk.seconds = time.time() - t0
                chk.format_ok = True

                if not (res.contextual_mapping or "").strip():
                    chk.violations.append("contextual_mapping이 비었다")
                _text_checks(res.contextual_mapping, where="상황 매핑", violations=chk.violations)

                # 괘는 규칙 엔진이 정한다. 모델이 바꿔치기하면 안 된다.
                if res.original_hexagram_id != evidence.original.hexagram_id:
                    chk.violations.append("본괘가 엔진 산출과 다르다")
            except Exception as e:  # noqa: BLE001
                chk.seconds = time.time() - t0
                chk.error = f"{type(e).__name__}: {e}"
            out.append(chk)
        return out
    finally:
        interpret_mod.search_chunks = original


async def run_counsel_cases(cases: List[Dict], client) -> List[Check]:
    interp = HexagramInterpretationSchema(
        original_hexagram_id=5, transformed_hexagram_id=None, changing_lines=[],
        raw_text="본괘: 제5괘 수천수\n해석 초점: 변효가 없으므로 괘사를 주 해석으로 삼습니다.\n"
                 "주 해석 근거:\n- 본괘 괘사: 미더움이 있어 밝게 형통하고, 곧게 지키면 길하다.",
        contextual_mapping="아직 때가 이르지 않았다고 느끼는 상황",
    )
    out = []
    for case in cases:
        chk = Check(case["id"])
        t0 = time.time()
        try:
            res = await run_counsel_turn(
                case["user_message"], interp,
                conversation_history=case.get("history") or [],
                turn_number=case.get("turn_number", 1),
                client=client,
            )
            chk.seconds = time.time() - t0
            chk.format_ok = True

            msg = res.message or ""
            if not msg.strip():
                chk.violations.append("message가 비었다")
            _text_checks(msg, where="상담 답변", violations=chk.violations)

            if len(msg) > 900:
                chk.violations.append(f"답변이 너무 길다({len(msg)}자)")

            # 되묻기: 이어갈 턴이면 사용자가 답할 것이 있어야 한다
            if res.needs_followup and not res.is_final and "?" not in msg:
                chk.violations.append("이어갈 턴인데 질문이 없다")

            if case.get("expect_final") and not res.is_final:
                chk.violations.append("마무리해야 할 턴인데 is_final이 서지 않았다")

            if case.get("turn_number", 1) >= MAX_TURNS_LIMIT and not res.is_final:
                chk.violations.append("턴 상한인데 마무리하지 않았다")
        except Exception as e:  # noqa: BLE001
            chk.seconds = time.time() - t0
            chk.error = f"{type(e).__name__}: {e}"
        out.append(chk)
    return out


async def run_journal_cases(cases: List[Dict], client, session) -> List[Check]:
    out = []
    for case in cases:
        chk = Check(case["id"])
        sid = str(uuid.uuid4())
        try:
            session.add(CounselSession(
                id=sid, user_id="_score_agents", raw_question=case["clarified_question"],
                clarified_question=case["clarified_question"],
                topic_category=case.get("topic_category"), status="active",
            ))
            for i, t in enumerate(case["turns"], 1):
                session.add(CounselTurn(
                    session_id=sid, turn_number=i, user_message=t["user"],
                    agent_response=t["agent"], needs_followup=False, is_final=(i == len(case["turns"])),
                ))
            await session.commit()

            t0 = time.time()
            entry = await write_journal(session, sid, client=client)
            chk.seconds = time.time() - t0
            chk.format_ok = True

            if not (entry.summary or "").strip():
                chk.violations.append("summary가 비었다")
            if not (entry.key_insights or "").strip():
                chk.violations.append("key_insights가 비었다")
            _text_checks(entry.summary, where="저널 요약", violations=chk.violations)
        except Exception as e:  # noqa: BLE001
            chk.error = f"{type(e).__name__}: {e}"
        finally:
            # 시험이 남긴 자국은 지운다
            await session.execute(delete(JournalEntry).where(JournalEntry.session_id == sid))
            await session.execute(delete(CounselTurn).where(CounselTurn.session_id == sid))
            await session.execute(delete(CounselSession).where(CounselSession.id == sid))
            await session.commit()
        out.append(chk)
    return out


def report(name: str, checks: List[Check]) -> Tuple[int, int, int, float]:
    n = len(checks)
    fmt = sum(1 for c in checks if c.format_ok)
    con = sum(1 for c in checks if c.constraint_ok)
    secs = [c.seconds for c in checks if c.seconds]
    med = sorted(secs)[len(secs) // 2] if secs else 0.0
    print(f"  {name:8} 형식 {fmt:2}/{n:<2}  제약 {con:2}/{n:<2}  지연 중앙 {med:5.1f}s")
    for c in checks:
        if c.error:
            print(f"      {c.case_id} 실패 — {c.error[:100]}")
        elif c.violations:
            print(f"      {c.case_id} {' · '.join(c.violations)}")
    return n, fmt, con, med


async def main_async(args) -> None:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    picked = [args.agent] if args.agent else ["intake", "interpret", "counsel", "journal"]

    results: Dict[str, List[Check]] = {}
    async with AsyncSessionLocal() as session:
        for name in picked:
            client = get_client(role=name, provider=args.provider, model=args.model)
            if name == "intake":
                results[name] = await run_intake_cases(data["intake"], client)
            elif name == "interpret":
                results[name] = await run_interpret_cases(data["interpret"], client, session)
            elif name == "counsel":
                results[name] = await run_counsel_cases(data["counsel"], client)
            elif name == "journal":
                results[name] = await run_journal_cases(data["journal"], client, session)

    probe = get_client(role="counsel", provider=args.provider, model=args.model)
    print(f"\n{probe.model_name} @ {probe.endpoint_desc}\n")
    totals = [report(n, results[n]) for n in picked]

    tn = sum(t[0] for t in totals)
    tf = sum(t[1] for t in totals)
    tc = sum(t[2] for t in totals)
    turn_cost = sum(t[3] for n, t in zip(picked, totals) if n in ("counsel",))
    print(f"\n  {'합계':8} 형식 {tf:2}/{tn:<2}  제약 {tc:2}/{tn:<2}")
    if turn_cost:
        print(f"\n  상담 1턴 예상 지연: 안전 + 상담 = 약 {turn_cost * 2:.0f}초 (안전이 상담과 비슷하다고 볼 때)")

    if args.output:
        Path(args.output).write_text(json.dumps(
            {n: [{"id": c.case_id, "format_ok": c.format_ok, "violations": c.violations,
                  "seconds": round(c.seconds, 2), "error": c.error} for c in cs]
             for n, cs in results.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n상세 → {args.output}")

    sys.exit(1 if tf < tn else 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--provider", default=None, help="anthropic | ollama | gemini")
    ap.add_argument("-m", "--model", default=None)
    ap.add_argument("-a", "--agent", default=None,
                    choices=["intake", "interpret", "counsel", "journal"])
    ap.add_argument("-o", "--output", default=None)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
