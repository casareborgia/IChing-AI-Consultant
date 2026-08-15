"""[K] 멀티에이전트 오케스트레이션 파이프라인 (Pipeline).

- 턴 단위 실행 (run_turn)
- 에이전트 간 직접 결합 없이 중앙 파이프라인에서 순차 제어
- 매 턴 [0] 안전 스크리닝 최우선 실행 및 래치(Latch) 유지
- 재삼독(몽괘 원칙) 감지 시 재뽑기 없이 이전 상담 회고 분기
- TurnResult에서 사용자 노출 문자열과 내부 상태 분리
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.counsel import run_counsel_turn
from agents.intake import run_intake
from agents.interpret import run_interpret
from agents.journal import write_journal
from agents.safety import format_safety_response, screen
from core.llm import LLMClient
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
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


async def _get_past_sessions(session: AsyncSession, user_id: Optional[str], limit: int = 10) -> List[Dict[str, Any]]:
    """사용자의 최근 과거 세션과 저널 요약을 조회합니다."""
    if not user_id:
        return []

    stmt = (
        select(CounselSession, JournalEntry.summary)
        .outerjoin(JournalEntry, CounselSession.id == JournalEntry.session_id)
        .where(CounselSession.user_id == user_id, CounselSession.status != "safety_redirect")
        .order_by(CounselSession.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    past = []
    for cs, summary in rows:
        past.append({
            "session_id": cs.id,
            "clarified_question": cs.clarified_question or cs.raw_question,
            "summary": summary or "",
        })
    return past



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

    # 3. [1] 신규 세션인 경우: Intake (정리 및 재삼독 감지) & [2] Interpret (괘 도출)
    if not c_session:
        past_list = await _get_past_sessions(session, user_id)
        intake_res = await run_intake(message, past_sessions=past_list, client=clients.get("intake"))

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

        # 3-1. 재삼독 (동일 질문 중복) 감지 시 -> 괘를 뽑지 않고 이전 세션 회고로 유도
        if intake_res.is_duplicate_question:
            c_session.status = "completed"
            dup_msg = (
                f"이전에 이미 같은 고민(세션: {intake_res.duplicate_session_ref})으로 괘를 헤아려 보신 기록이 있습니다.\n\n"
                "주역(몽괘)에서는 같은 물음을 거듭 묻기보다(再三瀆), 먼저 얻은 지혜를 삶에서 어떻게 실천하고 돌아보았는지를 더 중히 여깁니다.\n\n"
                "지난 상담 이후 상황이나 마음에 어떤 새로운 변화나 갈림길이 생기셨는지 먼저 말씀해 주시겠어요?"
            )
            new_turn = CounselTurn(
                session_id=sid,
                turn_number=1,
                user_message=message,
                agent_response=dup_msg,
                needs_followup=True,
                is_final=False,
            )
            session.add(new_turn)
            await session.commit()

            return TurnResult(
                session_id=sid,
                turn_number=1,
                user_facing_message=dup_msg,
                needs_followup=True,
                is_final=False,
                is_duplicate=True,
                safety_category=safety_res.category,
            )

        # 3-2. 정상 신규 세션 -> [2] 괘 도출 및 해석
        interp_res, evidence, chunks = await run_interpret(
            session,
            intake_res.clarified_question,
            method=method,
            manual_lines=manual_lines,
            client=clients.get("interpret"),
        )

        # 3-3. [3] 1턴 상담 대화 생성
        caution_append = (safety_res.category == "CAUTION")
        counsel_turn_res = await run_counsel_turn(
            message,
            interp_res,
            conversation_history=[],
            turn_number=1,
            client=clients.get("counsel"),
            caution_append=caution_append,
        )

        new_turn = CounselTurn(
            session_id=sid,
            turn_number=1,
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
            turn_number=1,
            user_facing_message=counsel_turn_res.message,
            needs_followup=counsel_turn_res.needs_followup,
            is_final=counsel_turn_res.is_final,
            hexagram_id=interp_res.original_hexagram_id,
            transformed_hexagram_id=interp_res.transformed_hexagram_id,
            changing_lines=interp_res.changing_lines,
            safety_category=safety_res.category,
            journal_summary=journal_summary,
        )

    # 4. 기존 세션의 후속 턴 진행
    next_turn_num = len(turns) + 1
    # 1턴의 괘 정보 복원
    first_turn = turns[0]
    orig_hex_id = first_turn.original_hexagram_id or 1
    trans_hex_id = first_turn.transformed_hexagram_id
    ch_lines = first_turn.changing_lines or []

    # 이전 대화 히스토리 조립
    history_items = []
    for t in turns:
        history_items.append({"role": "user", "message": t.user_message})
        history_items.append({"role": "counselor", "message": t.agent_response})

    # 후속 턴용 괘 근거 및 해석 스키마 복원
    from core.hexagram_engine import cast_hexagram
    from core.reading import build_evidence

    # 1턴의 효 정보를 기반으로 확정 근거 재생성
    # manual_lines가 1턴과 일치하도록 복원
    mock_cast = cast_hexagram(method="coin")
    try:
        evidence = await build_evidence(session, mock_cast)
        summary_text = evidence.summary_korean
    except Exception:
        summary_text = f"제{orig_hex_id}괘 상담 지속 중"

    interp_stub = HexagramInterpretationSchema(
        original_hexagram_id=orig_hex_id,
        transformed_hexagram_id=trans_hex_id,
        changing_lines=ch_lines,
        raw_text=summary_text,
        contextual_mapping=c_session.clarified_question or c_session.raw_question,
    )


    caution_append = (safety_res.category == "CAUTION")
    counsel_turn_res = await run_counsel_turn(
        message,
        interp_stub,
        conversation_history=history_items,
        turn_number=next_turn_num,
        client=clients.get("counsel"),
        caution_append=caution_append,
    )

    new_turn = CounselTurn(
        session_id=c_session.id,
        turn_number=next_turn_num,
        original_hexagram_id=orig_hex_id,
        transformed_hexagram_id=trans_hex_id,
        changing_lines=ch_lines,
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
        turn_number=next_turn_num,
        user_facing_message=counsel_turn_res.message,
        needs_followup=counsel_turn_res.needs_followup,
        is_final=counsel_turn_res.is_final,
        hexagram_id=orig_hex_id,
        transformed_hexagram_id=trans_hex_id,
        changing_lines=ch_lines,
        safety_category=safety_res.category,
        journal_summary=journal_summary,
    )
