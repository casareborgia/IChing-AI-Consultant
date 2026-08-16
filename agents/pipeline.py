"""[K] 멀티에이전트 오케스트레이션 파이프라인 (Pipeline).

- 턴 단위 실행 (run_turn)
- 에이전트 간 직접 결합 없이 중앙 파이프라인에서 순차 제어
- 매 턴 [0] 안전 스크리닝 최우선 실행 및 래치(Latch) 유지
- 재삼독(몽괘 원칙) 감지 시 재뽑기 없이 이전 상담 회고 분기
- TurnResult에서 사용자 노출 문자열과 내부 상태 분리
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.counsel import run_counsel_turn
from core.config import settings
from agents.intake import run_intake
from agents.interpret import run_interpret
from agents.journal import write_journal
from agents.safety import format_safety_response, screen
from core.hexagram_engine import rebuild_cast
from core.llm import LLMClient
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from core.models.hexagram import Hexagram
from core.prompts import load_prompt_block
from core.rag import make_retriever
from core.reading import build_evidence
from schemas.counsel import HexagramInterpretationSchema, SafetyVerdict


@dataclass
class TurnResult:
    """한 턴의 실행 결과 (사용자 노출 데이터와 내부 메타데이터 분리)."""

    session_id: str
    turn_number: int
    user_facing_message: str          # 사용자 화면에 직접 나가는 순수 텍스트
    needs_followup: bool = False
    is_final: bool = False
    hexagram_id: Optional[int] = None
    transformed_hexagram_id: Optional[int] = None
    changing_lines: Optional[List[int]] = None
    safety_category: str = "NORMAL"   # 내부 로깅/DB용 (사용자 미노출)
    is_duplicate: bool = False
    journal_summary: Optional[str] = None


async def _get_past_sessions(
    session: AsyncSession,
    user_id: Optional[str],
    limit: int = 10,
    exclude_session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """사용자의 최근 과거 세션과 저널 요약을 조회합니다.

    `exclude_session_id`는 지금 진행 중인 세션을 뺀다. 되묻기(ASK)를 거친 세션은
    이미 DB에 있어서, 빼지 않으면 정리 에이전트가 자기 자신을 보고 "같은 질문을
    또 한다"고 판정한다.
    """
    if not user_id:
        return []

    stmt = (
        select(CounselSession, JournalEntry.summary)
        .outerjoin(JournalEntry, CounselSession.id == JournalEntry.session_id)
        .where(CounselSession.user_id == user_id, CounselSession.status != "safety_redirect")
        .order_by(CounselSession.created_at.desc())
        .limit(limit)
    )
    if exclude_session_id:
        stmt = stmt.where(CounselSession.id != exclude_session_id)
    rows = (await session.execute(stmt)).all()
    past = []
    for cs, summary in rows:
        past.append({
            "session_id": cs.id,
            "clarified_question": cs.clarified_question or cs.raw_question,
            "summary": summary or "",
        })
    return past


async def _has_recent_crisis(session: AsyncSession, user_id: Optional[str],
                             exclude_session_id: Optional[str] = None) -> bool:
    """이 사용자에게 최근 위기 판정이 있었는지 본다.

    래치가 세션 안에만 있으면 아무것도 막지 못한다. 위기 판정은 세션을 닫으므로
    (`is_final`), 다음 발화는 새 세션으로 들어오고 거기엔 아무 흔적이 없다.
    위기를 겪은 사람이 몇 분 뒤 다시 말을 걸면 평범한 괘가 나가던 상태였다.

    창(窓)을 둔 것은 타협이다. 프롬프트는 "해제는 사람이 판단한다"고 하지만
    이 앱에는 판단할 사람이 없다. 무기한 차단은 앱을 못 쓰게 만들고, 즉시 해제는
    지금처럼 아무것도 막지 못한다. 사람이 검토하는 경로가 생기면 이 창은 걷어낸다.

    `user_id`가 없으면(익명) 세션 단위 래치만 남는다. 이건 한계이지 설계가 아니다.
    """
    hours = settings.CRISIS_LATCH_HOURS
    if not user_id or hours <= 0:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(CounselSession.id)
        .where(
            CounselSession.user_id == user_id,
            CounselSession.status == "safety_redirect",
            CounselSession.updated_at >= cutoff,
        )
        .limit(1)
    )
    if exclude_session_id:
        stmt = stmt.where(CounselSession.id != exclude_session_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def _get_previous_reading(session: AsyncSession, ref_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """재삼독으로 지목된 이전 세션에서 그때 얻은 괘를 꺼낸다.

    되묻기만 하고 끝내면 대화가 막힌다. 지난번 괘를 물려받아야 이어서 상담할 수
    있고, 그것이 "이전 상담을 다시 보여준다"는 원칙이기도 하다.
    """
    if not ref_id:
        return None

    turn = (
        await session.execute(
            select(CounselTurn)
            .where(CounselTurn.session_id == ref_id, CounselTurn.original_hexagram_id.isnot(None))
            .order_by(CounselTurn.turn_number.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if turn is None:
        return None

    hexagram = (
        await session.execute(select(Hexagram).where(Hexagram.id == turn.original_hexagram_id))
    ).scalar_one_or_none()
    summary = (
        await session.execute(select(JournalEntry.summary).where(JournalEntry.session_id == ref_id))
    ).scalar_one_or_none()

    return {
        "hexagram_id": turn.original_hexagram_id,
        "transformed_hexagram_id": turn.transformed_hexagram_id,
        "changing_lines": list(turn.changing_lines or []),
        "name_full": (hexagram.name_full if hexagram else None) or f"제{turn.original_hexagram_id}괘",
        "summary": summary or "",
    }


def _format_duplicate_message(prev: Dict[str, Any]) -> str:
    """재삼독 안내 문구를 조립한다. 내부 식별자는 넣지 않는다."""
    reading = f"제{prev['hexagram_id']}괘 {prev['name_full']}"
    if prev.get("transformed_hexagram_id"):
        reading += f"(지괘 제{prev['transformed_hexagram_id']}괘)"
    recall = f"\n\n그때 나눈 이야기는 이러했습니다 — {prev['summary']}" if prev.get("summary") else ""
    return (
        load_prompt_block("duplicate_response", "## 재삼독 안내")
        .replace("{reading}", reading)
        .replace("{recall}", recall)
    )



async def run_turn(
    session: AsyncSession,
    *,
    counsel_session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    message: str,
    method: str = "coin",
    manual_lines: Optional[List[int]] = None,
    clients: Optional[Dict[str, LLMClient]] = None,
) -> TurnResult:
    """상담 파이프라인의 1개 턴을 실행합니다.

    Args:
        session: SQLAlchemy 비동기 세션
        counsel_session_id: 세션 ID (None이면 신규 세션 시작)
        user_id: 사용자 고유 식별자 (선택 사항)
        message: 사용자의 이번 턴 발화
        method: 괘 도출 방식 ("coin" | "yarrow")
        manual_lines: 테스트용 수동 효 리스트
        clients: 주입할 역할별 LLM 클라이언트 딕셔너리 (Mock 테스팅용)

    Returns:
        TurnResult 객체
    """
    clients = clients or {}

    # 1. 세션 존재 여부 및 이전 턴 로드
    c_session: Optional[CounselSession] = None
    turns: List[CounselTurn] = []
    latched_crisis = False

    if counsel_session_id:
        c_session = (
            await session.execute(
                select(CounselSession).where(CounselSession.id == counsel_session_id)
            )
        ).scalar_one_or_none()

        if c_session:
            turns = (
                await session.execute(
                    select(CounselTurn)
                    .where(CounselTurn.session_id == counsel_session_id)
                    .order_by(CounselTurn.turn_number.asc())
                )
            ).scalars().all()

            if c_session.status == "safety_redirect":
                latched_crisis = True

    # 세션이 닫혀도 사람은 그대로다. 최근에 위기 판정이 있었다면 새 세션으로 와도
    # 괘를 뽑지 않는다.
    if not latched_crisis:
        latched_crisis = await _has_recent_crisis(
            session, user_id, exclude_session_id=c_session.id if c_session else None
        )

    # 2. [0] 안전 스크리닝 (항상 최우선 매 턴 실행)
    history_summary = None
    if turns:
        history_summary = f"이전 {len(turns)}개 턴 진행 중. 최근 발화: {turns[-1].user_message}"

    safety_res: SafetyVerdict = await screen(
        message,
        history=history_summary,
        client=clients.get("safety"),
        latched_crisis=latched_crisis,
    )

    # 2-0. 스크리닝 실패 -> 괘도 상담도 없이 중립 안내. 세션 상태는 건드리지 않는다.
    #      통신 장애 한 번에 세션이 닫히거나 위기/범위밖 문구가 나가면 안 된다.
    if safety_res.category == "ERROR":
        return TurnResult(
            session_id=c_session.id if c_session else "",
            turn_number=len(turns) + 1,
            user_facing_message=format_safety_response(safety_res) or "",
            needs_followup=True,
            is_final=False,
            safety_category="ERROR",
        )

    # 2-1. 위기 발화 (BLOCK_CRISIS) -> 즉시 핫라인 안내 분기 및 세션 래치
    if safety_res.category == "BLOCK_CRISIS":
        sid = c_session.id if c_session else str(uuid.uuid4())
        if not c_session:
            c_session = CounselSession(
                id=sid,
                user_id=user_id,
                raw_question=message,
                status="safety_redirect",
            )
            session.add(c_session)
        else:
            c_session.status = "safety_redirect"

        next_turn_num = len(turns) + 1
        resp_msg = format_safety_response(safety_res) or ""
        new_turn = CounselTurn(
            session_id=sid,
            turn_number=next_turn_num,
            user_message=message,
            agent_response=resp_msg,
            needs_followup=False,
            is_final=True,
        )
        session.add(new_turn)
        await session.commit()

        return TurnResult(
            session_id=sid,
            turn_number=next_turn_num,
            user_facing_message=resp_msg,
            needs_followup=False,
            is_final=True,
            safety_category="BLOCK_CRISIS",
        )

    # 2-2. 범위 밖 (BLOCK_SCOPE) 또는 되묻기 (ASK) -> 괘를 뽑지 않고 해당 안내 출력
    if safety_res.category in ("BLOCK_SCOPE", "ASK"):
        sid = c_session.id if c_session else str(uuid.uuid4())
        if not c_session:
            c_session = CounselSession(
                id=sid,
                user_id=user_id,
                raw_question=message,
                status="active" if safety_res.category == "ASK" else "completed",
            )
            session.add(c_session)

        next_turn_num = len(turns) + 1
        resp_msg = format_safety_response(safety_res) or ""
        new_turn = CounselTurn(
            session_id=sid,
            turn_number=next_turn_num,
            user_message=message,
            agent_response=resp_msg,
            needs_followup=(safety_res.category == "ASK"),
            is_final=(safety_res.category != "ASK"),
        )
        session.add(new_turn)
        await session.commit()

        return TurnResult(
            session_id=sid,
            turn_number=next_turn_num,
            user_facing_message=resp_msg,
            needs_followup=(safety_res.category == "ASK"),
            is_final=(safety_res.category != "ASK"),
            safety_category=safety_res.category,
        )

    # 이전 대화 이력 (되묻기만 오간 세션에서도 상담사가 맥락을 잃지 않도록 먼저 조립한다)
    history_items: List[Dict[str, str]] = []
    for t in turns:
        history_items.append({"role": "user", "message": t.user_message})
        history_items.append({"role": "counselor", "message": t.agent_response})

    turn_no = len(turns) + 1

    # 3. 아직 괘가 없는 세션 -> [1] Intake (정리·재삼독) + [2] Interpret (괘 도출)
    #
    #    갈림의 기준은 "세션이 새것인가"가 아니라 "이 세션에 괘가 있는가"다.
    #    되묻기(ASK)는 세션을 먼저 만들어 두므로, 세션 유무로 가르면 사용자가
    #    되물음에 답한 턴이 이 블록을 건너뛴다. 그러면 뽑은 적 없는 괘로
    #    상담이 나간다 — 실제로 1번 괘가 그렇게 나가고 있었다.
    has_reading = any(t.original_hexagram_id for t in turns)

    if not has_reading:
        past_list = await _get_past_sessions(
            session, user_id, exclude_session_id=c_session.id if c_session else None
        )

        # 되묻기를 거쳤다면 앞선 발화까지 함께 넘긴다. 이번 발화만 보면
        # "네, 이직 얘기예요" 같은 답변만 남아 고민을 정리할 수 없다.
        intake_source = "\n".join([t.user_message for t in turns] + [message])
        intake_res = await run_intake(
            intake_source,
            past_sessions=past_list,
            client=clients.get("intake"),
        )

        if c_session is None:
            sid = str(uuid.uuid4())
            c_session = CounselSession(
                id=sid,
                user_id=user_id,
                raw_question=message,
                clarified_question=intake_res.clarified_question,
                topic_category=intake_res.topic_category,
                is_duplicate=intake_res.is_duplicate_question,
                duplicate_session_ref=intake_res.duplicate_session_ref,
                status="active",
            )
            session.add(c_session)
        else:
            sid = c_session.id
            c_session.clarified_question = intake_res.clarified_question
            c_session.topic_category = intake_res.topic_category
            c_session.is_duplicate = intake_res.is_duplicate_question
            c_session.duplicate_session_ref = intake_res.duplicate_session_ref
            c_session.status = "active"

        # 3-1. 재삼독 (동일 질문 중복) -> 새로 뽑지 않고 지난번 괘를 물려받는다.
        #
        # 되묻기만 하고 끝내면 안 된다. 예전에는 이 분기가 괘 없는 턴을 남겨서,
        # 사용자가 "무엇이 달라졌나" 물음에 답해도 다음 턴이 다시 이 분기로 들어와
        # 똑같은 문구를 글자 하나 안 틀리고 반복했다. 빠져나갈 길이 없었다.
        #
        # 지난번 괘를 이 턴에 기록해 두면 다음 턴은 후속 상담 경로로 간다 —
        # 새 괘를 뽑지 않으면서 대화는 이어진다. 몽괘 원칙이 막으려던 것은
        # 재뽑기지 대화가 아니다.
        #
        # 지목된 세션에서 괘를 찾지 못하면(그 세션도 되묻기만 하다 끝난 경우 등)
        # 보여줄 것이 없으므로 중복으로 치지 않고 정상적으로 뽑는다.
        prev_reading = await _get_previous_reading(session, intake_res.duplicate_session_ref)

        if intake_res.is_duplicate_question and prev_reading:
            dup_msg = _format_duplicate_message(prev_reading)
            new_turn = CounselTurn(
                session_id=sid,
                turn_number=turn_no,
                original_hexagram_id=prev_reading["hexagram_id"],
                transformed_hexagram_id=prev_reading["transformed_hexagram_id"],
                changing_lines=prev_reading["changing_lines"],
                user_message=message,
                agent_response=dup_msg,
                needs_followup=True,
                is_final=False,
            )
            session.add(new_turn)
            await session.commit()

            return TurnResult(
                session_id=sid,
                turn_number=turn_no,
                user_facing_message=dup_msg,
                needs_followup=True,
                is_final=False,
                is_duplicate=True,
                hexagram_id=prev_reading["hexagram_id"],
                transformed_hexagram_id=prev_reading["transformed_hexagram_id"],
                changing_lines=prev_reading["changing_lines"],
                safety_category=safety_res.category,
            )

        if intake_res.is_duplicate_question:
            # 중복이라 했으나 보여줄 괘가 없다. 기록만 남기고 평소대로 진행한다.
            c_session.is_duplicate = False
            c_session.duplicate_session_ref = None

        # 3-2. 주역 자체를 묻는 질문이면 괘를 뽑지 않는다.
        #
        # 묻는 사람은 괘를 뽑은 적이 없다. 그런데도 뽑아서 답하면 "지금 보신 괘는…"
        # 같은, 사실이 아닌 전제를 사용자에게 돌려주게 된다. 실제로 그렇게 나가고 있었다.
        if intake_res.request_type == "question":
            counsel_turn_res = await run_counsel_turn(
                message, None,
                conversation_history=history_items,
                turn_number=turn_no,
                client=clients.get("counsel"),
                caution_append=(safety_res.category == "CAUTION"),
            )
            new_turn = CounselTurn(
                session_id=sid,
                turn_number=turn_no,
                user_message=message,
                agent_response=counsel_turn_res.message,
                needs_followup=counsel_turn_res.needs_followup,
                is_final=counsel_turn_res.is_final,
            )
            session.add(new_turn)
            await session.commit()

            return TurnResult(
                session_id=sid,
                turn_number=turn_no,
                user_facing_message=counsel_turn_res.message,
                needs_followup=counsel_turn_res.needs_followup,
                is_final=counsel_turn_res.is_final,
                safety_category=safety_res.category,
            )

        # 3-3. 괘 도출 및 해석
        interp_res, evidence, chunks = await run_interpret(
            session,
            intake_res.clarified_question,
            method=method,
            manual_lines=manual_lines,
            client=clients.get("interpret"),
        )

        # 3-3. [3] 상담 대화 생성
        #
        # 재검색은 초점이 가리키는 괘로 묶어 넘긴다. 동효가 4~5개면 초점은 지괘에
        # 있고, 그때 본괘로 묶으면 상담사가 이야기하는 괘와 다시 찾아오는 해설이
        # 서로 다른 괘가 된다. `evidence.target_hexagram_id`가 그 자리를 가리킨다.
        counsel_turn_res = await run_counsel_turn(
            message,
            interp_res,
            conversation_history=history_items,
            turn_number=turn_no,
            client=clients.get("counsel"),
            caution_append=(safety_res.category == "CAUTION"),
            retrieve=make_retriever(session, hexagram_id=evidence.target_hexagram_id),
        )

        new_turn = CounselTurn(
            session_id=sid,
            turn_number=turn_no,
            original_hexagram_id=interp_res.original_hexagram_id,
            transformed_hexagram_id=interp_res.transformed_hexagram_id,
            changing_lines=interp_res.changing_lines,
            user_message=message,
            agent_response=counsel_turn_res.message,
            needs_followup=counsel_turn_res.needs_followup,
            is_final=counsel_turn_res.is_final,
        )
        session.add(new_turn)
        await session.commit()

        journal_summary = None
        if counsel_turn_res.is_final:
            j = await write_journal(session, sid, client=clients.get("journal"))
            journal_summary = j.summary

        return TurnResult(
            session_id=sid,
            turn_number=turn_no,
            user_facing_message=counsel_turn_res.message,
            needs_followup=counsel_turn_res.needs_followup,
            is_final=counsel_turn_res.is_final,
            hexagram_id=interp_res.original_hexagram_id,
            transformed_hexagram_id=interp_res.transformed_hexagram_id,
            changing_lines=interp_res.changing_lines,
            safety_category=safety_res.category,
            journal_summary=journal_summary,
        )

    # 4. 이미 괘가 있는 세션 -> 그 괘를 되살려 상담을 잇는다
    #
    #    다시 뽑지 않는다. 본괘 ID와 동효 위치만으로 그때의 6효가 하나로
    #    결정되므로, 저장된 값에서 같은 괘를 그대로 복원할 수 있다.
    #    예전에는 여기서 cast_hexagram()을 새로 불러 매 턴 다른 괘가 나왔고,
    #    상담사는 A괘의 괘사를 들고 B괘 이야기를 했다.
    reading_turn = next(t for t in turns if t.original_hexagram_id)
    cast = rebuild_cast(reading_turn.original_hexagram_id, reading_turn.changing_lines or [])
    evidence = await build_evidence(session, cast)

    interp_stub = HexagramInterpretationSchema(
        original_hexagram_id=cast.original_hexagram_id,
        transformed_hexagram_id=cast.transformed_hexagram_id,
        changing_lines=cast.changing_lines,
        raw_text=evidence.summary_korean,
        contextual_mapping=c_session.clarified_question or c_session.raw_question,
    )

    # 후속 턴이야말로 재검색이 필요한 자리다. 첫 검색은 정리된 첫 질문으로 돌았고,
    # 여기서는 대화가 이미 그 질문에서 멀어져 있다. 이 경로에 검색이 없으면
    # 상담사는 세션 내내 첫 턴에 찾아둔 해설만 들고 이야기하게 된다.
    counsel_turn_res = await run_counsel_turn(
        message,
        interp_stub,
        conversation_history=history_items,
        turn_number=turn_no,
        client=clients.get("counsel"),
        caution_append=(safety_res.category == "CAUTION"),
        retrieve=make_retriever(session, hexagram_id=evidence.target_hexagram_id),
    )

    new_turn = CounselTurn(
        session_id=c_session.id,
        turn_number=turn_no,
        original_hexagram_id=cast.original_hexagram_id,
        transformed_hexagram_id=cast.transformed_hexagram_id,
        changing_lines=cast.changing_lines,
        user_message=message,
        agent_response=counsel_turn_res.message,
        needs_followup=counsel_turn_res.needs_followup,
        is_final=counsel_turn_res.is_final,
    )
    session.add(new_turn)
    await session.commit()

    journal_summary = None
    if counsel_turn_res.is_final:
        j = await write_journal(session, c_session.id, client=clients.get("journal"))
        journal_summary = j.summary

    return TurnResult(
        session_id=c_session.id,
        turn_number=turn_no,
        user_facing_message=counsel_turn_res.message,
        needs_followup=counsel_turn_res.needs_followup,
        is_final=counsel_turn_res.is_final,
        hexagram_id=cast.original_hexagram_id,
        transformed_hexagram_id=cast.transformed_hexagram_id,
        changing_lines=cast.changing_lines,
        safety_category=safety_res.category,
        journal_summary=journal_summary,
    )
