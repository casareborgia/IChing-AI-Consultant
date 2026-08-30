"""크레딧 검증 및 차감 로직 단위 테스트 스위트."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import cast, delete, select, String


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
    test_user_id = str(uuid.uuid4())


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
                await session.execute(select(UserProfile).where(cast(UserProfile.id, String) == test_user_id))
            ).scalar_one_or_none()
            assert profile is not None
            assert profile.credit_balance == 40

            ledger_entries = (
                (
                    await session.execute(
                        select(CreditLedger).where(cast(CreditLedger.user_id, String) == test_user_id)
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
    test_user_id = str(uuid.uuid4())


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


def _mock_turn(safety_category: str = "NORMAL", is_duplicate: bool = False):
    """run_turn 이 돌려주는 결과의 대역."""
    r = AsyncMock()
    r.session_id = "test-session-id-999"
    r.turn_number = 1
    r.user_facing_message = "테스트 메시지입니다."
    r.needs_followup = True
    r.is_final = False
    r.hexagram_id = 1
    r.transformed_hexagram_id = 1
    r.changing_lines = []
    r.safety_category = safety_category
    r.is_duplicate = is_duplicate
    r.journal_summary = None
    r.focus_rule = None
    r.evidences = []
    return r


async def _post_start():
    """상담 시작을 한 번 호출한다. 인증 우회와 run_turn 패치는 호출자가 건다."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/counsel/start",
            headers={"Authorization": "Bearer fake-token"},
            json={"question": "취업에 관한 고민이 있습니다."},
        )


def _override_auth(user_id: str):
    from api.deps import require_user

    async def mock_require_user():
        return user_id

    app.dependency_overrides = {require_user: mock_require_user}


async def _start(user_id: str, turn_result):
    """인증을 우회하고 상담 시작을 한 번 호출한다."""
    _override_auth(user_id)
    try:
        with patch("api.main.run_turn", return_value=turn_result):
            return await _post_start()
    finally:
        app.dependency_overrides.clear()


async def _balance(user_id: str):
    async with AsyncSessionLocal() as session:
        return (
            await session.execute(
                select(UserProfile.credit_balance).where(UserProfile.id == user_id)
            )
        ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_crisis_turn_is_refunded():
    """위기 판정 세션은 크레딧을 받지 않는다.

    가입 화면이 "위기 감지 시 크레딧 미차감"을 약속하고, SaMD 자가 대조도 이를
    윤리 기준으로 든다. 차감 후 환불이므로 최종 잔액이 그대로여야 한다.
    """
    user_id = str(uuid.uuid4())
    res = await _start(user_id, _mock_turn(safety_category="BLOCK_CRISIS"))

    assert res.status_code == 200
    assert res.json()["remaining_credits"] == 50
    assert await _balance(user_id) == 50

    async with AsyncSessionLocal() as session:
        entries = (
            (await session.execute(select(CreditLedger).where(CreditLedger.user_id == user_id)))
            .scalars()
            .all()
        )
    # 웰컴 +50, 차감 -10, 환불 +10 — 무엇이 왜 되돌아갔는지 장부에 남는다
    assert sorted(e.amount for e in entries) == [-10, 10, 50]


@pytest.mark.asyncio
async def test_duplicate_question_is_refunded():
    """재삼독으로 괘를 뽑지 않은 턴은 크레딧을 받지 않는다."""
    user_id = str(uuid.uuid4())
    res = await _start(user_id, _mock_turn(is_duplicate=True))

    assert res.status_code == 200
    assert res.json()["remaining_credits"] == 50
    assert await _balance(user_id) == 50


@pytest.mark.asyncio
async def test_concurrent_starts_cannot_overspend():
    """동시 요청이 잔액을 넘겨 쓸 수 없다.

    읽고-계산하고-절대값을 쓰는 방식에서는 두 요청이 같은 잔액을 읽어 서로의 차감을
    덮어써, 50 크레딧으로 6회 이상 상담이 나갔다. 조건부 UPDATE 로 그 창을 없앴다.
    """
    import asyncio

    user_id = str(uuid.uuid4())
    # 프로필과 웰컴 50 크레딧을 먼저 만든다
    assert (await _start(user_id, _mock_turn())).status_code == 200
    assert await _balance(user_id) == 40

    # 남은 40 크레딧에 8건을 동시에 던진다. 성공은 4건이어야 한다.
    #
    # patch 를 호출마다 걸면 먼저 끝난 요청이 남의 패치를 풀어버려 진짜 run_turn 이
    # 새어 나간다. gather 전체를 한 번만 감싼다.
    _override_auth(user_id)
    try:
        with patch("api.main.run_turn", return_value=_mock_turn()):
            results = await asyncio.gather(*[_post_start() for _ in range(8)])
    finally:
        app.dependency_overrides.clear()
    codes = [r.status_code for r in results]

    assert codes.count(200) == 4, f"과다 차감 또는 과소 차감: {codes}"
    assert codes.count(402) == 4, f"잔액 부족 응답이 예상과 다름: {codes}"
    assert await _balance(user_id) == 0
