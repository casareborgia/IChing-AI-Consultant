# -*- coding: utf-8 -*-
"""AG-4: 고객지원 문의 접수 HTTP 계약 단위 테스트 (tests/test_support.py)."""

from datetime import datetime, timezone
import re
import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import check_rate_limit, require_user
from api.main import app
from api.routers import support as support_router


class _MappingsResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one(self):
        return self._row

    def scalar_one_or_none(self):
        return self._row if isinstance(self._row, (str, int)) else None

    def scalar_one(self):
        return self._row


class FakeSupportSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.inserted_data = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt, params=None):
        self.inserted_data = params
        now = datetime.now(timezone.utc)
        return _MappingsResult({"status": "RECEIVED", "created_at": now})

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    support_router._email_rate_records.clear()
    yield
    app.dependency_overrides.clear()
    support_router._email_rate_records.clear()


@pytest.mark.asyncio
async def test_support_validation_errors_422():
    """카테고리, 메시지 길이, 이메일 형식 위반 시 각각 422 반환 (A20-2)."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. 카테고리 위반
        res_cat = await client.post(
            "/api/support/inquiries",
            json={
                "category": "invalid_category",
                "email": "user@example.com",
                "message": "문의 내용입니다.",
            },
        )
        assert res_cat.status_code == 422

        # 2. 이메일 형식 위반
        res_email = await client.post(
            "/api/support/inquiries",
            json={
                "category": "service",
                "email": "not-an-email",
                "message": "문의 내용입니다.",
            },
        )
        assert res_email.status_code == 422

        # 3. 메시지 4000자 초과
        res_len = await client.post(
            "/api/support/inquiries",
            json={
                "category": "service",
                "email": "user@example.com",
                "message": "A" * 4001,
            },
        )
        assert res_len.status_code == 422

        # 4. 빈 메시지
        res_empty = await client.post(
            "/api/support/inquiries",
            json={
                "category": "service",
                "email": "user@example.com",
                "message": "   ",
            },
        )
        assert res_empty.status_code == 422


@pytest.mark.asyncio
async def test_support_submission_success_and_ticket_format(monkeypatch):
    """정상 문의 접수 시 201 Created 및 TKT-YYYYMMDD-<8자 이상> 티켓 번호 발급 (A20-1)."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    fake_session = FakeSupportSession()
    monkeypatch.setattr(support_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 비로그인 접수
        res = await client.post(
            "/api/support/inquiries",
            json={
                "category": "service",
                "email": "inquirer@example.com",
                "message": "서비스 관련 문의사항이 있습니다.",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "RECEIVED"
        ticket_no = data["ticket_no"]
        # 티켓 번호 형식 검증: TKT-YYYYMMDD-[A-Z0-9]{8,}
        assert re.match(r"^TKT-\d{8}-[A-F0-9]{8,}$", ticket_no)
        assert fake_session.commits == 1
        assert fake_session.inserted_data["user_id"] is None

        # 로그인 접수 (Authorization 헤더 있는 경우)
        app.dependency_overrides[support_router.optional_user] = lambda: "authenticated-user-uuid"
        res_auth = await client.post(
            "/api/support/inquiries",
            headers={"Authorization": "Bearer some-token"},
            json={
                "category": "refund",
                "email": "authuser@example.com",
                "message": "환불 요청드립니다.",
                "order_id": "ORD-1234",
            },
        )
        assert res_auth.status_code == 201
        assert fake_session.inserted_data["user_id"] == "authenticated-user-uuid"
        assert fake_session.inserted_data["order_id"] == "ORD-1234"


@pytest.mark.asyncio
async def test_support_email_rate_limit(monkeypatch):
    """동일 이메일로 1시간 내 5건 초과 접수 시 429 반환 (A20)."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    fake_session = FakeSupportSession()
    monkeypatch.setattr(support_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            res = await client.post(
                "/api/support/inquiries",
                json={
                    "category": "service",
                    "email": "spammer@example.com",
                    "message": f"문의 {i+1}",
                },
            )
            assert res.status_code == 201

        # 6번째 요청 -> 429
        res_limit = await client.post(
            "/api/support/inquiries",
            json={
                "category": "service",
                "email": "spammer@example.com",
                "message": "초과 문의",
            },
        )
        assert res_limit.status_code == 429
