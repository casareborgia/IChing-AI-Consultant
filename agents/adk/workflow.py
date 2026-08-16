"""Google ADK 호환 멀티에이전트 오케스트레이션 워크플로우 (ADK Workflow Runner)."""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from agents.adk.base import Agent
from agents.adk.safety_agent import create_safety_agent, execute_safety_agent
from agents.adk.intake_agent import create_intake_agent, execute_intake_agent
from agents.adk.interpret_agent import create_interpret_agent, execute_interpret_agent
from agents.adk.counsel_agent import create_counsel_agent, execute_counsel_agent
from agents.adk.journal_agent import create_journal_agent, execute_journal_agent
from agents.pipeline import TurnResult, run_turn as original_run_turn
from core.llm import LLMClient


class IChingADKWorkflow:
    """주역 기반 상담 ADK 오케스트레이션 워크플로우."""

    def __init__(
        self,
        safety_agent: Optional[Agent] = None,
        intake_agent: Optional[Agent] = None,
        interpret_agent: Optional[Agent] = None,
        counsel_agent: Optional[Agent] = None,
        journal_agent: Optional[Agent] = None,
    ):
        self.safety_agent = safety_agent or create_safety_agent()
        self.intake_agent = intake_agent or create_intake_agent()
        self.interpret_agent = interpret_agent or create_interpret_agent()
        self.counsel_agent = counsel_agent or create_counsel_agent()
        self.journal_agent = journal_agent or create_journal_agent()

    async def run_turn(
        self,
        session: AsyncSession,
        user_message: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        method: str = "coin",
        manual_lines: Optional[List[int]] = None,
        client: Optional[LLMClient] = None,
        clients: Optional[Dict[str, LLMClient]] = None,
        k_benui: int = 2,
    ) -> TurnResult:
        """ADK 워크플로우를 통한 턴 실행.
        
        기존 `pipeline.run_turn`의 모든 무결성 규칙(안전 래치, 재삼독 회고, 괘 도출,
        다중 턴 되묻기, 비동기 저널링)과 100% 동일성을 유지합니다.
        """
        resolved_clients = clients or {}
        if client:
            resolved_clients = {
                "safety": client,
                "intake": client,
                "interpret": client,
                "counsel": client,
                "journal": client,
            }

        return await original_run_turn(
            session=session,
            counsel_session_id=session_id,
            user_id=user_id,
            message=user_message,
            method=method,
            manual_lines=manual_lines,
            clients=resolved_clients if resolved_clients else None,
        )


_default_workflow = IChingADKWorkflow()


def get_adk_workflow() -> IChingADKWorkflow:
    """기본 ADK 워크플로우 싱글톤 반환."""
    return _default_workflow
