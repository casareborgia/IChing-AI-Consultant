"""[3] ADK 상담 에이전트 (Counsel Agent)."""

from typing import Any, Dict, List, Optional
from agents.adk.base import Agent
from agents.tools import search_iching_commentaries_tool
from agents.counsel import run_counsel_turn
from core.config import settings
from core.llm import LLMClient
from core.prompts import load_system_prompt
from core.rag import RetrievedChunk, Retriever
from schemas.counsel import CounselTurnSchema, HexagramInterpretationSchema


def create_counsel_agent() -> Agent:
    """ADK 상담 에이전트 인스턴스 생성."""
    return Agent(
        name="counsel",
        role="counsel",
        model=settings.COUNSEL_MODEL,
        instruction=load_system_prompt("counsel"),
        description="내담자와 다중 턴으로 대화하며 1턴 1질문 되묻기와 성찰적 상담을 수행합니다.",
        tools=[search_iching_commentaries_tool],
        output_schema=CounselTurnSchema,
        temperature=0.3,
    )


async def execute_counsel_agent(
    agent: Agent,
    user_message: str,
    turn_number: int,
    clarified_question: str,
    interpretation: HexagramInterpretationSchema,
    *,
    evidence_summary: str,
    chunks: Optional[List[RetrievedChunk]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    client: Optional[LLMClient] = None,
    retriever: Optional[Retriever] = None,
    max_rag_searches: int = 3,
) -> CounselTurnSchema:
    """ADK 상담 에이전트 턴 실행 함수."""
    llm = agent.get_client(client)
    return await run_counsel_turn(
        user_message=user_message,
        turn_number=turn_number,
        clarified_question=clarified_question,
        interpretation=interpretation,
        evidence_summary=evidence_summary,
        chunks=chunks,
        history=history,
        client=llm,
        retriever=retriever,
        max_rag_searches=max_rag_searches,
    )
