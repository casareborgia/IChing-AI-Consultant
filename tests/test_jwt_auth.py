"""Supabase JWT 인증 및 엔드포인트 보안 검증 테스트."""

import time
import pytest
import jwt
from httpx import ASGITransport, AsyncClient

from api.main import app
from core.config import settings


TEST_JWT_SECRET = "super-secret-test-jwt-key-for-unit-testing-only-12345"


@pytest.fixture(autouse=True)
def setup_jwt_secret(monkeypatch):
    """테스트 시 SUPABASE_JWT_SECRET을 주입하여 엄격한 서명 검증을 활성화합니다."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_JWT_SECRET)


def create_test_token(sub: str = "user-uuid-1234", exp_delta: int = 3600, aud: str = "authenticated") -> str:
    """테스트용 서명된 Supabase JWT를 생성합니다."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": aud,
        "role": "authenticated",
        "exp": now + exp_delta,
        "iat": now,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.mark.asyncio
async def test_start_consultation_without_token_returns_401():
    """토큰 없이 상담 시작 요청 시 401 Unauthorized 반환."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/counsel/start", json={"question": "취업 고민이 있습니다."})
        assert res.status_code == 401
        assert res.json()["detail"] == "인증이 필요합니다."


@pytest.mark.asyncio
async def test_start_consultation_with_invalid_jwt_returns_401():
    """서명이 위조된 잘못된 JWT로 요청 시 401 반환."""
    invalid_token = jwt.encode({"sub": "hacker", "aud": "authenticated", "exp": int(time.time()) + 3600}, "wrong-secret", algorithm="HS256")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/counsel/start",
            headers={"Authorization": f"Bearer {invalid_token}"},
            json={"question": "취업 고민이 있습니다."},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "인증 정보가 유효하지 않습니다."


@pytest.mark.asyncio
async def test_start_consultation_with_expired_jwt_returns_401():
    """만료된 JWT로 요청 시 401 반환."""
    expired_token = create_test_token(exp_delta=-100)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/counsel/start",
            headers={"Authorization": f"Bearer {expired_token}"},
            json={"question": "취업 고민이 있습니다."},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "인증 정보가 유효하지 않습니다."


@pytest.mark.asyncio
async def test_start_consultation_with_wrong_audience_returns_401():
    """잘못된 audience를 가진 JWT로 요청 시 401 반환."""
    wrong_aud_token = create_test_token(aud="anon")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/counsel/start",
            headers={"Authorization": f"Bearer {wrong_aud_token}"},
            json={"question": "취업 고민이 있습니다."},
        )
        assert res.status_code == 401
        assert res.json()["detail"] == "인증 정보가 유효하지 않습니다."


@pytest.mark.asyncio
async def test_turn_endpoint_without_token_returns_401():
    """토큰 없이 상담 턴 요청 시 401 반환."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/counsel/turn",
            json={"session_id": "test-session-123", "user_message": "답변입니다."},
        )
        assert res.status_code == 401
