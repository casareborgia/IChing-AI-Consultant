"""Google ADK 호환 기본 에이전트 및 런너 추상화 레이어.

google-adk의 핵심 클래스 구조(Agent, Tool, Runner, Context)와 일치하는
인터페이스를 제공하여 로컬 및 Cloud Run 배포 환경에서 유연하게 작동하도록 합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel

from core.llm import LLMClient, get_client


@dataclass
class Tool:
    """ADK 규격 도구 정의."""
    name: str
    description: str
    func: Callable
    parameters_schema: Optional[Type[BaseModel]] = None

    async def __call__(self, *args, **kwargs):
        return await self.func(*args, **kwargs)


@dataclass
class Agent:
    """ADK 규격 에이전트 정의."""
    name: str
    instruction: str
    model: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    tools: List[Callable] = field(default_factory=list)
    output_schema: Optional[Type[BaseModel]] = None
    temperature: float = 0.0

    def get_client(self, client_override: Optional[LLMClient] = None) -> LLMClient:
        if client_override:
            return client_override
        return get_client(role=self.role or self.name, model=self.model)


@dataclass
class InvocationContext:
    """에이전트 실행 컨텍스트."""
    session_id: str
    user_id: Optional[str] = None
    turn_number: int = 1
    state: Dict[str, Any] = field(default_factory=dict)
