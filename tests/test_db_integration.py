import pytest
from sqlalchemy import select
from core.db import AsyncSessionLocal
from core.models.hexagram import Hexagram, Line
from core.models.counsel import CounselSession, CounselTurn


@pytest.mark.asyncio
async def test_db_seeded_hexagrams_and_lines():
    """seed_hexagrams.py로 적재된 64괘 및 386효 DB 조회 검증"""
    async with AsyncSessionLocal() as session:
        # 1. 64괘 총 개수 검증
        stmt_hex = select(Hexagram)
        hexagrams = (await session.execute(stmt_hex)).scalars().all()
        assert len(hexagrams) == 64

        # 2. 386효 총 개수 검증
        stmt_line = select(Line)
        lines = (await session.execute(stmt_line)).scalars().all()
        assert len(lines) == 386

        # 3. 1번 건괘(中天乾) 상세 검증 (용구 7번 포함)
        stmt_qian = select(Hexagram).where(Hexagram.id == 1)
        qian = (await session.execute(stmt_qian)).scalar_one_or_none()
        assert qian is not None
        assert qian.name_ko == "건"
        assert qian.name_full == "중천건"
        assert qian.symbol == "䷀"
        assert qian.binary_code == "111111"

        stmt_qian_lines = select(Line).where(Line.hexagram_id == 1).order_by(Line.line_number)
        qian_lines = (await session.execute(stmt_qian_lines)).scalars().all()
        assert len(qian_lines) == 7  # 초효~상효(6개) + 용구(1개) = 7개


@pytest.mark.asyncio
async def test_db_session_and_counsel_turn_crud():
    """상담 세션 및 턴 생성/조회/FK 제약 검증"""
    async with AsyncSessionLocal() as session:
        session_obj = CounselSession(
            raw_question="새 사업을 시작하려 합니다.",
            clarified_question="사업 시작의 적절한 시기인가요?",
            topic_category="커리어/사업",
        )
        session.add(session_obj)
        await session.commit()

        # DB 영속화 후 server_default=active 검증
        assert session_obj.status == "active"
        session_id = session_obj.id

        turn_obj = CounselTurn(
            session_id=session_id,
            turn_number=1,
            original_hexagram_id=1,
            user_message="사업 추진 시 유의점이 무엇인가요?",
            agent_response="중천건 괘는 결단력과 당당함을 뜻합니다.",
            needs_followup=True,
        )
        session.add(turn_obj)
        await session.commit()

        # 조회 검증 (selectinload 사용으로 eager loading)
        from sqlalchemy.orm import selectinload
        stmt = select(CounselSession).options(selectinload(CounselSession.turns)).where(CounselSession.id == session_id)
        fetched_session = (await session.execute(stmt)).scalar_one_or_none()
        assert fetched_session is not None
        assert len(fetched_session.turns) == 1
        assert fetched_session.turns[0].turn_number == 1


        # 정리
        await session.delete(fetched_session)
        await session.commit()
