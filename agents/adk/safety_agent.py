"""[0] ADK 안전 스크리닝 에이전트 (Safety Screener Agent)."""

from typing import Optional
from agents.adk.base import Agent
from agents.safety import format_safety_response, screen
from core.config import settings
from core.llm import LLMClient
from core.prompts import load_system_prompt
from schemas.counsel import SafetyVerdict


def create_safety_agent() -> Agent:
    """ADK 안전 스크리닝 에이전트 인스턴스 생성."""
    return Agent(
        name="safety",
        role="safety",
        model=settings.SAFETY_MODEL,
        instruction=load_system_prompt("safety_screening"),
        description="사용자 발화에서 자해, 위기, 범위 밖 신호를 감지하고 안전하게 스크리닝합니다.",
        output_schema=SafetyVerdict,
        temperature=0.0,
    )


async def execute_safety_agent(
    agent: Agent,
    text: str,
    *,
    history: Optional[str] = None,
    client: Optional[LLMClient] = None,
    latched_crisis: bool = False,
) -> SafetyVerdict:
    """ADK 안전 에이전트 실행 함수."""
    llm = agent.get_client(client)
    return await screen(
        text=text,
        history=history,
        client=llm,
        latched_crisis=latched_crisis,
    )
