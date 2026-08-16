"""[1] ADK 정리 에이전트 (Intake Agent)."""

from typing import Any, Dict, List, Optional
from agents.adk.base import Agent
from agents.tools import lookup_past_sessions_tool
from agents.intake import run_intake
from core.config import settings
from core.llm import LLMClient
from core.prompts import load_system_prompt
from schemas.counsel import IntakeOutput


def create_intake_agent() -> Agent:
    """ADK 정리 에이전트 인스턴스 생성."""
    return Agent(
        name="intake",
        role="intake",
        model=settings.INTAKE_MODEL,
        instruction=load_system_prompt("intake"),
        description="사용자 고민을 명확화하고 과거 상담 이력을 통해 중복 질문(재삼독)을 감지합니다.",
        tools=[lookup_past_sessions_tool],
        output_schema=IntakeOutput,
        temperature=0.0,
    )


async def execute_intake_agent(
    agent: Agent,
    message: str,
    *,
    past_sessions: Optional[List[Dict[str, Any]]] = None,
    client: Optional[LLMClient] = None,
) -> IntakeOutput:
    """ADK 정리 에이전트 실행 함수."""
    llm = agent.get_client(client)
    return await run_intake(
        message=message,
        past_sessions=past_sessions,
        client=llm,
    )
