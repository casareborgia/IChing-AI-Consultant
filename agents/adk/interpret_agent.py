"""[2] ADK 괘 도출 및 해석 에이전트 (Interpretation Agent)."""

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from agents.adk.base import Agent
from agents.tools import cast_hexagram_tool, lookup_hexagram_text_tool, search_iching_commentaries_tool
from agents.interpret import run_interpret
from core.config import settings
from core.llm import LLMClient
from core.prompts import load_system_prompt
from core.rag import RetrievedChunk
from core.reading import ReadingEvidence
from schemas.counsel import HexagramInterpretationSchema


def create_interpret_agent() -> Agent:
    """ADK 괘 해석 에이전트 인스턴스 생성."""
    return Agent(
        name="interpret",
        role="interpret",
        model=settings.INTERPRET_MODEL,
        instruction=load_system_prompt("interpret"),
        description="규칙 엔진으로 괘를 도출하고 확정 원문과 RAG 주석을 바탕으로 상황 매핑을 생성합니다.",
        tools=[cast_hexagram_tool, lookup_hexagram_text_tool, search_iching_commentaries_tool],
        output_schema=HexagramInterpretationSchema,
        temperature=0.0,
    )


async def execute_interpret_agent(
    agent: Agent,
    session: AsyncSession,
    clarified_question: str,
    *,
    method: str = "coin",
    manual_lines: Optional[List[int]] = None,
    client: Optional[LLMClient] = None,
    k_benui: int = 2,
) -> Tuple[HexagramInterpretationSchema, ReadingEvidence, List[RetrievedChunk]]:
    """ADK 해석 에이전트 실행 함수."""
    llm = agent.get_client(client)
    return await run_interpret(
        session=session,
        clarified_question=clarified_question,
        method=method,
        manual_lines=manual_lines,
        client=llm,
        k_benui=k_benui,
    )
