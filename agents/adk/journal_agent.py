"""[+1] ADK 저널 에이전트 (Journal Agent)."""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from agents.adk.base import Agent
from agents.journal import write_journal
from core.config import settings
from core.llm import LLMClient
from core.models.counsel import JournalEntry
from core.prompts import load_system_prompt
from schemas.counsel import JournalEntrySchema


def create_journal_agent() -> Agent:
    """ADK 저널 에이전트 인스턴스 생성."""
    return Agent(
        name="journal",
        role="journal",
        model=settings.JOURNAL_MODEL,
        instruction=load_system_prompt("journal"),
        description="종료된 상담 세션의 대화 내용을 요약하고 성찰 포인트를 추출하여 DB에 저장합니다.",
        output_schema=JournalEntrySchema,
        temperature=0.2,
    )


async def execute_journal_agent(
    agent: Agent,
    session: AsyncSession,
    counsel_session_id: str,
    *,
    client: Optional[LLMClient] = None,
) -> JournalEntry:
    """ADK 저널 에이전트 실행 함수."""
    llm = agent.get_client(client)
    return await write_journal(
        session=session,
        counsel_session_id=counsel_session_id,
        client=llm,
    )
