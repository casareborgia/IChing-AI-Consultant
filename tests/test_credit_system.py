"""크레딧 검증 및 차감 로직 단위 테스트 스위트."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from api.main import app
from core.config import settings
from core.db import AsyncSessionLocal, Base, engine
from core.models.counsel import CreditLedger, UserProfile


@pytest.fixture(autouse=True)
async def setup_db():
    """테스트 전 DB 테이블 자동 생성."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_start_consultation_deducts_credit(monkeypatch):
    """최초 상담 시작 시 10 크레딧이 차감되고 장부에 이력이 기록되는지 검증."""
    test_user_id = f"test-user-deduct-{uuid.uuid4().hex[:8]}"

    # JWT 인증 require_user 모킹
    async def mock_require_user():
        return test_user_id

    app.dependency_overrides = {}
    from api.deps import require_user
    app.dependency_overrides[require_user] = mock_require_user

    # run_turn 모킹 (실제 LLM 호출 방지)
    mock_turn_result = AsyncMock()
    mock_turn_result.session_id = "test-session-id-001"
    mock_turn_result.turn_number = 1
    mock_turn_result.user_facing_message = "테스트 괘 해설 메시지입니다."
    mock_turn_result.needs_followup = True
    mock_turn_result.is_final = False
    mock_turn_result.hexagram_id = 1
    mock_turn_result.transformed_hexagram_id = 1
    mock_turn_result.changing_lines = []
    mock_turn_result.safety_category = "NORMAL"
    mock_turn_result.is_duplicate = False
    mock_turn_result.journal_summary = None
    mock_turn_result.focus_rule = None
    mock_turn_result.evidences = []

    with patch("api.main.run_turn", return_value=mock_turn_result):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/counsel/start",
                headers={"Authorization": "Bearer fake-token"},
                json={"question": "취업에 관한 고민이 있습니다."},
            )

        assert res.status_code == 200
        data = res.json()
        assert data["remaining_credits"] == 40

        # DB 검증: 50 -> 40 차감
        async with AsyncSessionLocal() as session:
            profile = (
                await session.execute(select(UserProfile).where(UserProfile.id == test_user_id))
            ).scalar_one_or_none()
            assert profile is not None
            assert profile.credit_balance == 40

            ledger_entries = (
                (
                    await session.execute(
                        select(CreditLedger).where(CreditLedger.user_id == test_user_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(ledger_entries) == 2  # 웰컴 +50, 차감 -10

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_insufficient_credit_returns_402(monkeypatch):
    """크레딧이 10 미만일 경우 402 Payment Required 반환 검증."""
    test_user_id = f"test-user-low-{uuid.uuid4().hex[:8]}"

    # 사전 DB 준비: 크레딧 5 설정
    async with AsyncSessionLocal() as session:
        session.add(UserProfile(id=test_user_id, credit_balance=5))
        await session.commit()

    async def mock_require_user():
        return test_user_id

    from api.deps import require_user
    app.dependency_overrides[require_user] = mock_require_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/counsel/start",
            headers={"Authorization": "Bearer fake-token"},
            json={"question": "크레딧 부족 테스트입니다."},
        )

    assert res.status_code == 402
    assert "크레딧이 부족합니다" in res.json()["detail"]

    app.dependency_overrides.clear()
