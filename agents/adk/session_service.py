"""Google ADK 호환 Postgres SessionService 구현.

Cloud SQL / Postgres 환경에서 CounselSession 및 CounselTurn의
영속성을 ADK 표준 인터페이스로 관리합니다.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.counsel import CounselSession, CounselTurn, JournalEntry


class PostgresADKSessionService:
    """Postgres DB 기반 ADK 세션 관리 서비스."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(self, session_id: str) -> Optional[CounselSession]:
        """세션 조회."""
        stmt = select(CounselSession).where(CounselSession.id == session_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_turns(self, session_id: str) -> List[CounselTurn]:
        """세션 내 모든 턴 이력 조회."""
        stmt = (
            select(CounselTurn)
            .where(CounselTurn.session_id == session_id)
            .order_by(CounselTurn.turn_number.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_journal(self, session_id: str) -> Optional[JournalEntry]:
        """세션 저널 요약 조회."""
        stmt = select(JournalEntry).where(JournalEntry.session_id == session_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()
