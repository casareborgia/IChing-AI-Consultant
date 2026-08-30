"""크레딧 검증 및 차감 로직 단위 테스트 스위트."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import cast, delete, select, String


from api.main import app
from core.config import settings
from core.db import AsyncSessionLocal, Base, engine
from core.models.counsel import CounselSession, CreditLedger, UserProfile


@pytest.fixture(autouse=True)
async def setup_db():
    """테스트 전 테이블 레코드 정돈."""
    async with AsyncSessionLocal() as session:
        await session.execute(delete(CreditLedger))
        await session.execute(delete(CounselSession))
        await session.execute(delete(UserProfile))
        await session.commit()
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


@pytest.mark.asyncio
async def test_multiple_consecutive_consultations_deduct_credits_correctly():
    """동일 유저가 5회 연속 상담 시작 시 50->40->30->20->10->0으로 계속 차감되고 6회째에 402 반환됨을 검증."""
    test_user_id = str(uuid.uuid4())

    async def mock_require_user():
        return test_user_id

    from api.deps import require_user
    app.dependency_overrides[require_user] = mock_require_user

    mock_turn_result = AsyncMock()
    mock_turn_result.session_id = "test-session-id-consec"
    mock_turn_result.turn_number = 1
    mock_turn_result.user_facing_message = "연속 차감 테스트 응답"
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
            # 1회차: 50 -> 40
            res1 = await client.post("/api/counsel/start", json={"question": "질문 1"})
            assert res1.status_code == 200
            assert res1.json()["remaining_credits"] == 40

            # 2회차: 40 -> 30
            res2 = await client.post("/api/counsel/start", json={"question": "질문 2"})
            assert res2.status_code == 200
            assert res2.json()["remaining_credits"] == 30

            # 3회차: 30 -> 20
            res3 = await client.post("/api/counsel/start", json={"question": "질문 3"})
            assert res3.status_code == 200
            assert res3.json()["remaining_credits"] == 20

            # 4회차: 20 -> 10
            res4 = await client.post("/api/counsel/start", json={"question": "질문 4"})
            assert res4.status_code == 200
            assert res4.json()["remaining_credits"] == 10

            # 5회차: 10 -> 0
            res5 = await client.post("/api/counsel/start", json={"question": "질문 5"})
            assert res5.status_code == 200
            assert res5.json()["remaining_credits"] == 0

            # 6회차: 0 < 10 -> 402 Error
            res6 = await client.post("/api/counsel/start", json={"question": "질문 6"})
            assert res6.status_code == 402

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_counsel_turn_deducts_credit_and_handles_402():
    """상담 대화 턴 (/api/counsel/turn) 호출 시에도 10 크레딧이 차감되고 잔액 부족 시 402 반환됨을 검증."""
    test_user_id = str(uuid.uuid4())
    session_id = "test-turn-session-001"

    # 사전 DB 준비: 유저 잔액 15C 및 상담 세션 생성
    async with AsyncSessionLocal() as session:
        session.add(UserProfile(id=test_user_id, credit_balance=15))
        session.add(
            __import__("core.models.counsel", fromlist=["CounselSession"]).CounselSession(
                id=session_id, user_id=test_user_id, raw_question="턴 테스트"
            )
        )
        await session.commit()

    async def mock_require_user():
        return test_user_id

    from api.deps import require_user
    app.dependency_overrides[require_user] = mock_require_user

    mock_turn_result = AsyncMock()
    mock_turn_result.session_id = session_id
    mock_turn_result.turn_number = 2
    mock_turn_result.user_facing_message = "턴 대화 응답"
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
            # 1번째 턴: 15 -> 5
            res1 = await client.post(
                "/api/counsel/turn",
                json={"session_id": session_id, "user_message": "턴 메세지 1"},
            )
            assert res1.status_code == 200
            assert res1.json()["remaining_credits"] == 5

            # 2번째 턴: 5 < 10 -> 402 Payment Required
            res2 = await client.post(
                "/api/counsel/turn",
                json={"session_id": session_id, "user_message": "턴 메세지 2"},
            )
            assert res2.status_code == 402
            assert "크레딧이 부족합니다" in res2.json()["detail"]

    app.dependency_overrides.clear()




# --- 회귀 고정 ---------------------------------------------------------------
# 아래 셋은 각각 실제로 프로덕션에 나갔던 결함을 잡는다. 지우지 말 것.
#   · 위기 판정에도 크레딧을 받던 것 (가입 화면이 미차감을 약속한다)
#   · 동시 요청이 서로의 차감을 덮어써 잔액을 넘겨 쓰던 것
#   · 재삼독을 환불 대상에 넣었던 것 (받는 것이 맞다)
# 순차 차감 테스트로는 두 번째가 잡히지 않는다 — 반드시 동시에 던져야 드러난다.

from core.models.counsel import CounselSession  # noqa: E402


def _mock_turn(safety_category: str = "NORMAL", is_duplicate: bool = False, session_id: str = "sess-x"):
    r = AsyncMock()
    r.session_id = session_id
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


def _override_auth(user_id: str):
    from api.deps import require_user

    async def mock_require_user():
        return user_id

    app.dependency_overrides = {require_user: mock_require_user}


async def _post_start():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/counsel/start",
            headers={"Authorization": "Bearer fake-token"},
            json={"question": "취업에 관한 고민이 있습니다."},
        )


async def _post_turn(session_id: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/api/counsel/turn",
            headers={"Authorization": "Bearer fake-token"},
            json={"session_id": session_id, "user_message": "이어지는 이야기입니다."},
        )


async def _start(user_id: str, turn_result):
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


async def _seed_session(user_id: str, session_id: str, balance: int):
    async with AsyncSessionLocal() as session:
        session.add(UserProfile(id=user_id, credit_balance=balance))
        session.add(CounselSession(id=session_id, user_id=user_id, raw_question="회귀 테스트"))
        await session.commit()


@pytest.mark.asyncio
async def test_crisis_turn_is_refunded_on_start():
    """위기 판정이면 첫 턴 크레딧을 받지 않는다."""
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
async def test_crisis_turn_is_refunded_on_followup():
    """대화 도중 위기 판정이 나와도 크레딧을 받지 않는다.

    위기 신호는 첫 질문보다 대화가 풀린 뒤에 나올 여지가 크다. start 에만 환불을
    붙여두면 정작 필요한 자리가 비게 된다.
    """
    user_id = str(uuid.uuid4())
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    await _seed_session(user_id, session_id, balance=30)

    _override_auth(user_id)
    try:
        with patch("api.main.run_turn", return_value=_mock_turn("BLOCK_CRISIS", session_id=session_id)):
            res = await _post_turn(session_id)
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["remaining_credits"] == 30
    assert await _balance(user_id) == 30


@pytest.mark.asyncio
async def test_duplicate_question_is_still_charged():
    """재삼독 턴도 크레딧을 받는다.

    괘를 새로 뽑지 않을 뿐 파이프라인이 그대로 돌아 비용이 나가고, 이전 상담을
    되짚어 주는 것 자체가 제공하는 값이다. 환불은 위기 판정 하나뿐이다.
    """
    user_id = str(uuid.uuid4())
    res = await _start(user_id, _mock_turn(is_duplicate=True))

    assert res.status_code == 200
    assert res.json()["remaining_credits"] == 40
    assert await _balance(user_id) == 40


@pytest.mark.asyncio
async def test_concurrent_starts_cannot_overspend():
    """동시 요청이 잔액을 넘겨 쓸 수 없다 (start)."""
    import asyncio

    user_id = str(uuid.uuid4())
    assert (await _start(user_id, _mock_turn())).status_code == 200
    assert await _balance(user_id) == 40

    # patch 를 호출마다 걸면 먼저 끝난 요청이 남의 패치를 풀어 진짜 run_turn 이
    # 새어 나간다. gather 전체를 한 번만 감싼다.
    _override_auth(user_id)
    try:
        with patch("api.main.run_turn", return_value=_mock_turn()):
            results = await asyncio.gather(*[_post_start() for _ in range(8)])
    finally:
        app.dependency_overrides.clear()
    codes = [r.status_code for r in results]

    assert codes.count(200) == 4, f"과다/과소 차감: {codes}"
    assert await _balance(user_id) == 0


@pytest.mark.asyncio
async def test_concurrent_turns_cannot_overspend():
    """동시 요청이 잔액을 넘겨 쓸 수 없다 (turn)."""
    import asyncio

    user_id = str(uuid.uuid4())
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    await _seed_session(user_id, session_id, balance=30)

    _override_auth(user_id)
    try:
        with patch("api.main.run_turn", return_value=_mock_turn(session_id=session_id)):
            results = await asyncio.gather(*[_post_turn(session_id) for _ in range(6)])
    finally:
        app.dependency_overrides.clear()
    codes = [r.status_code for r in results]

    assert codes.count(200) == 3, f"과다/과소 차감: {codes}"
    assert await _balance(user_id) == 0
