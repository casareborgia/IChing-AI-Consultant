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

from agents.counsel import DIAGNOSIS_TERMS, MAX_TURNS_LIMIT, run_counsel_turn
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
# 진단성 발언. 설계 원칙 4 — 병명·약물·의학적 판단 금지.
# 목록은 agents/counsel.py가 갖는다. 여기에 복사본을 두면 둘이 갈라진다.
DIAGNOSIS = DIAGNOSIS_TERMS
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


class RecordingClient:
    """호출 실패를 기록하는 껍데기.

    에이전트들은 LLM 실패를 안에서 삼키고 미리 준비한 문장을 돌려준다(설계상
    그게 맞다 — 사용자에게 예외를 보여줄 수는 없다). 그래서 에이전트의 반환값만
    보면 모델이 아무것도 못 냈을 때도 '형식 통과'로 세게 된다. 실제로 26B 측정에서
    0토큰짜리 호출이 통과로 집계됐다. 클라이언트 층에서 직접 세야 한다.
    """

    def __init__(self, inner):
        self.inner = inner
        self.failures = 0
        self.last_error: Optional[str] = None

    @property
    def model_name(self):
        return self.inner.model_name

    @property
    def endpoint_desc(self):
        return self.inner.endpoint_desc

    @property
    def last_timing(self):
        return getattr(self.inner, "last_timing", None)

    def complete_json(self, user: str, **kwargs) -> Dict[str, Any]:
        try:
            return self.inner.complete_json(user, **kwargs)
        except Exception as e:  # noqa: BLE001
            self.failures += 1
            self.last_error = f"{type(e).__name__}: {e}"
            raise


class Check:
    """한 건에 대한 판정 결과."""

    def __init__(self, case_id: str):
        self.case_id = case_id
        self.format_ok = False
        self.violations: List[str] = []
        self.seconds = 0.0
        self.error: Optional[str] = None
        self.timing: Optional[Dict[str, float]] = None   # Ollama가 준 시간 분해
        # 위반이 잡혔을 때 무엇이 나왔는지 봐야 진짜인지 안다. 세 번 막혔던 자리다.
        self.output: Optional[str] = None

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
            _f0 = getattr(client, 'failures', 0)
            res = await run_intake(case["message"], past_sessions=past, client=client)
            chk.seconds = time.time() - t0
            chk.timing = getattr(client, "last_timing", None)
            chk.format_ok = getattr(client, "failures", 0) == _f0
            if not chk.format_ok:
                chk.error = f"모델 호출 실패 — {getattr(client, 'last_error', '')[:80]}"
                out.append(chk)
                continue

            if not (res.clarified_question or "").strip():
                chk.violations.append("clarified_question이 비었다")
            if not (res.topic_category or "").strip():
                chk.violations.append("topic_category가 비었다")
            chk.output = res.clarified_question
            _text_checks(res.clarified_question, where="정리된 질문", violations=chk.violations)

            want = case.get("expect_request_type")
            if want and res.request_type != want:
                chk.violations.append(f"request_type이 {want}여야 하는데 {res.request_type}")

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

    # 검색을 대역으로 갈아끼운다. 인덱스 내용이 점수에 섞이면 모델 비교가 안 되고,
    # 임베딩 호출도 나가지 않는다. 이름은 `core.rag`를 따라간다 —
    # `search_chunks`에서 `search_balanced`로 바뀌었을 때 여기가 같이 안 바뀌어
    # 하네스가 통째로 죽은 적이 있다(테스트 밖이라 pytest가 못 잡는다).
    original = interpret_mod.search_balanced
    interpret_mod.search_balanced = stub_search
    try:
        out = []
        for case in cases:
            chk = Check(case["id"])
            t0 = time.time()
            try:
                _f0 = getattr(client, 'failures', 0)
                res, evidence, _ = await run_interpret(
                    session, case["clarified_question"],
                    manual_lines=case["manual_lines"], client=client,
                )
                chk.seconds = time.time() - t0
                chk.timing = getattr(client, "last_timing", None)
                chk.format_ok = getattr(client, "failures", 0) == _f0
                if not chk.format_ok:
                    chk.error = f"모델 호출 실패 — {getattr(client, 'last_error', '')[:80]}"
                    out.append(chk)
                    continue

                if not (res.contextual_mapping or "").strip():
                    chk.violations.append("contextual_mapping이 비었다")
                chk.output = res.contextual_mapping
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
        interpret_mod.search_balanced = original


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
            _f0 = getattr(client, 'failures', 0)
            res = await run_counsel_turn(
                case["user_message"], interp,
                conversation_history=case.get("history") or [],
                turn_number=case.get("turn_number", 1),
                client=client,
            )
            chk.seconds = time.time() - t0
            chk.timing = getattr(client, "last_timing", None)
            chk.format_ok = getattr(client, "failures", 0) == _f0
            if not chk.format_ok:
                chk.error = f"모델 호출 실패 — {getattr(client, 'last_error', '')[:80]}"
                out.append(chk)
                continue

            msg = res.message or ""
            chk.output = msg
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
            _f0 = getattr(client, 'failures', 0)
            entry = await write_journal(session, sid, client=client)
            chk.seconds = time.time() - t0
            chk.timing = getattr(client, "last_timing", None)
            chk.format_ok = getattr(client, "failures", 0) == _f0
            if not chk.format_ok:
                chk.error = f"모델 호출 실패 — {getattr(client, 'last_error', '')[:80]}"
            else:
                chk.output = entry.summary
            if chk.format_ok and not (entry.summary or "").strip():
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


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def report(name: str, checks: List[Check]) -> Dict[str, Any]:
    n = len(checks)
    fmt = sum(1 for c in checks if c.format_ok)
    con = sum(1 for c in checks if c.constraint_ok)
    secs = [c.seconds for c in checks if c.seconds]
    med, worst = _median(secs), (max(secs) if secs else 0.0)

    line = f"  {name:10} 형식 {fmt:3}/{n:<3} 제약 {con:3}/{n:<3} 지연 중앙 {med:6.1f}s 최장 {worst:6.1f}s"

    # Ollama가 시간 분해를 줬다면 어디에 쓰였는지 갈라 본다
    tms = [c.timing for c in checks if c.timing]
    if tms:
        load = _median([t["load"] for t in tms])
        pin = _median([t["prompt_seconds"] for t in tms])
        gen = _median([t["gen_seconds"] for t in tms])
        ptok = _median([t["prompt_tokens"] for t in tms])
        gtok = _median([t["gen_tokens"] for t in tms])
        gtps = _median([t["gen_tps"] for t in tms])
        line += (f"\n             ├ 로드 {load:5.1f}s  입력 {pin:5.1f}s ({ptok:.0f}토큰)"
                 f"  생성 {gen:5.1f}s ({gtok:.0f}토큰, {gtps:.0f} tok/s)")
        reloads = sum(1 for t in tms if t["load"] > 1.0)
        if reloads:
            line += f"\n             └ 모델 재로드 {reloads}/{len(tms)}건 — 메모리에서 밀려났다는 뜻"
    print(line)

    for c in checks:
        if c.error:
            print(f"      {c.case_id} 실패 — {c.error[:100]}")
        elif c.violations:
            print(f"      {c.case_id} {' · '.join(c.violations)}")
    return {"n": n, "format": fmt, "constraint": con, "median": med, "worst": worst}


async def warmup(client) -> None:
    """첫 호출은 모델 로드가 섞여 대표성이 없다. 재고 버린다."""
    try:
        client.complete_json('{"ping":1}만 출력하십시오.', system="JSON만 출력합니다.")
    except Exception:
        pass


async def run_all(data: Dict, client, session, picked: List[str]) -> Dict[str, List[Check]]:
    out = {}
    for name in picked:
        if name == "intake":
            out[name] = await run_intake_cases(data["intake"], client)
        elif name == "interpret":
            out[name] = await run_interpret_cases(data["interpret"], client, session)
        elif name == "counsel":
            out[name] = await run_counsel_cases(data["counsel"], client)
        elif name == "journal":
            out[name] = await run_journal_cases(data["journal"], client, session)
    return out


async def main_async(args) -> None:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    picked = [args.agent] if args.agent else ["intake", "interpret", "counsel", "journal"]
    models = [m.strip() for m in args.model.split(",")] if args.model else [None]

    async with AsyncSessionLocal() as session:
        for model in models:
            client = get_client(role="counsel", provider=args.provider, model=model)
            print(f"\n{'=' * 66}\n{client.model_name} @ {client.endpoint_desc}  ({args.repeat}회 반복)\n{'=' * 66}")

            # 예열은 한 모델당 한 번. 이후 반복은 메모리에 올라온 상태를 잰다.
            await warmup(client)

            merged: Dict[str, List[Check]] = {n: [] for n in picked}
            for r in range(args.repeat):
                run_client = RecordingClient(
                    get_client(role="counsel", provider=args.provider, model=model))
                got = await run_all(data, run_client, session, picked)
                for n, cs in got.items():
                    merged[n].extend(cs)

            summaries = {n: report(n, merged[n]) for n in picked}
            tn = sum(v["n"] for v in summaries.values())
            tf = sum(v["format"] for v in summaries.values())
            tc = sum(v["constraint"] for v in summaries.values())
            print(f"\n  {'합계':10} 형식 {tf:3}/{tn:<3} 제약 {tc:3}/{tn:<3}")
            if "counsel" in summaries:
                print(f"  상담 1턴(안전+상담) 추정: 약 {summaries['counsel']['median'] * 2:.0f}초")

            if args.output:
                tag = (client.model_name or "model").replace(":", "-").replace("/", "-")
                path = Path(args.output).with_name(Path(args.output).stem + f"_{tag}.json")
                path.write_text(json.dumps(
                    {n: [{"id": c.case_id, "format_ok": c.format_ok, "violations": c.violations,
                          "seconds": round(c.seconds, 2), "timing": c.timing,
                          "output": c.output, "error": c.error}
                         for c in cs] for n, cs in merged.items()},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  상세 → {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--provider", default=None, help="anthropic | ollama | gemini")
    ap.add_argument("-m", "--model", default=None, help="쉼표로 여러 개 지정 가능")
    ap.add_argument("-r", "--repeat", type=int, default=1, help="모델당 반복 횟수")
    ap.add_argument("-a", "--agent", default=None,
                    choices=["intake", "interpret", "counsel", "journal"])
    ap.add_argument("-o", "--output", default=None)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
