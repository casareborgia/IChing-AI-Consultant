"""[+1] 저널 에이전트 (Journal Agent).

- 상담 세션 종료 후 대화 전체 요약 및 핵심 성찰 추출
- JournalEntry DB 레코드 생성 및 세션 상태 'completed' 변경
- 다음 방문 시 Intake 에이전트의 이전 맥락 데이터로 활용
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm import LLMClient, get_client
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from core.prompts import load_system_prompt
from schemas.counsel import JournalEntrySchema


async def write_journal(
    session: AsyncSession,
    counsel_session_id: str,
    *,
    client: Optional[LLMClient] = None,
) -> JournalEntry:
    """종료된 상담 세션의 대화 내용을 요약하여 저널 엔트리를 DB에 저장합니다.

    Args:
        session: SQLAlchemy 비동기 세션
        counsel_session_id: 상담 세션 ID
        client: 주입할 LLM 클라이언트

    Returns:
        저장된 JournalEntry ORM 객체
    """
    # 1. 세션 및 턴 조회
    c_session = (
        await session.execute(
            select(CounselSession).where(CounselSession.id == counsel_session_id)
        )
    ).scalar_one()

    turns = (
        await session.execute(
            select(CounselTurn)
            .where(CounselTurn.session_id == counsel_session_id)
            .order_by(CounselTurn.turn_number.asc())
        )
    ).scalars().all()

    # 2. 프롬프트 조립
    sys_prompt = load_system_prompt("journal")
    llm = client or get_client(role="journal")

    prompt_lines = [
        f"[상담 질문] {c_session.clarified_question or c_session.raw_question}",
        f"[주제 분류] {c_session.topic_category or '기타'}\n",
        "[전체 대화 이력]",
    ]

    for t in turns:
        prompt_lines.append(f"내담자 (턴 {t.turn_number}): {t.user_message}")
        prompt_lines.append(f"상담사: {t.agent_response}\n")

    user_msg = "\n".join(prompt_lines)

    try:
        data = llm.complete_json(user_msg, system=sys_prompt, temperature=0.2, max_tokens=1024)
        summary = data.get("summary", "주역 괘를 바탕으로 마음을 성찰한 상담 세션입니다.")
        key_insights = data.get("key_insights", "상황을 주체적으로 바라보는 지혜를 나눔.")
        action_items = data.get("action_items")
    except Exception:
        summary = f"질문: {c_session.clarified_question or c_session.raw_question}에 대한 주역 상담"
        key_insights = "괘상의 흐름을 바탕으로 대화를 나눔."
        action_items = None

    # 3. 기존 저널이 있는지 확인 후 갱신 또는 신규 생성
    existing_journal = (
        await session.execute(
            select(JournalEntry).where(JournalEntry.session_id == counsel_session_id)
        )
    ).scalar_one_or_none()

    if existing_journal:
        existing_journal.summary = summary
        existing_journal.key_insights = key_insights
        existing_journal.action_items = action_items
        journal_entry = existing_journal
    else:
        journal_entry = JournalEntry(
            session_id=counsel_session_id,
            summary=summary,
            key_insights=key_insights,
            action_items=action_items,
        )
        session.add(journal_entry)

    c_session.status = "completed"
    await session.commit()
    await session.refresh(journal_entry)

    return journal_entry
