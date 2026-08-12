import pytest
from sqlalchemy import select
from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line
from core.models.counsel import CounselSession, CounselTurn


@pytest.mark.asyncio
async def test_db_session_and_hexagram_crud():
    async with AsyncSessionLocal() as session:
        # Hexagram 생성
        hex_data = Hexagram(
            id=1,
            binary_code="111111",
            name_ko="건",
            name_hanja="乾",
            name_full="중천건",
            judgment_text="乾：元，亨，利，貞。",
        )
        session.add(hex_data)
        
        # Line 생성
        line_data = Line(
            hexagram_id=1,
            line_number=1,
            statement_text="初九：潛龍勿用。",
        )
        session.add(line_data)
        
        await session.commit()

        # 조회 검증
        stmt = select(Hexagram).where(Hexagram.id == 1)
        result = await session.execute(stmt)
        fetched_hex = result.scalar_one_or_none()

        assert fetched_hex is not None
        assert fetched_hex.name_ko == "건"
        assert fetched_hex.binary_code == "111111"

        # 세션 정리 (테스트 데이터 삭제)
        await session.delete(fetched_hex)
        await session.commit()
