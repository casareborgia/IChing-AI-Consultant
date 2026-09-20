# -*- coding: utf-8 -*-
"""AG-1: 법적 동의 및 연령 확인 HTTP 계약 단위 테스트 (tests/test_consent.py)."""

from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import check_rate_limit, require_user
from api.main import app
from api.routers import consent as consent_router


class _MappingsResult:
    def __init__(self, items):
        self._items = items

    def mappings(self):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def one(self):
        return self._items[0]

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar_one(self):
        return self._items[0]


class FakeConsentSession:
    def __init__(self, existing_row=None, inserted_row=None):
        self.existing_row = existing_row
        self.inserted_row = inserted_row
        self.commits = 0
        self.rollbacks = 0
        self.executed_stmts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt, params=None):
        stmt_str = str(stmt).strip()
        self.executed_stmts.append((stmt_str, params))
        if "SELECT" in stmt_str and self.existing_row is not None:
            return _MappingsResult([self.existing_row])
        elif "INSERT" in stmt_str and self.inserted_row is not None:
            return _MappingsResult([self.inserted_row])
        return _MappingsResult([])

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def clean_overrides(monkeypatch):
    monkeypatch.setattr(consent_router.settings, "LEGAL_DOCUMENTS_VERSION", "2026-09-12")
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_consent_fail_closed_when_legal_version_unset(monkeypatch):
    """LEGAL_DOCUMENTS_VERSION이 비어 있으면 503 fail-closed (FIX-4.2)."""
    monkeypatch.setattr(consent_router.settings, "LEGAL_DOCUMENTS_VERSION", "")
    app.dependency_overrides[require_user] = lambda: "test-user-id"
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res.status_code == 503
        data = res.json()
        assert data["detail"]["code"] == "LEGAL_VERSION_UNSET"


@pytest.mark.asyncio
async def test_consent_unauthorized_returns_401():
    """인증 헤더 없이 요청 시 401 반환 (A29-7)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_consent_age_confirmed_false_or_string_returns_422():
    """age_confirmed가 false이거나 문자열 'true'인 경우 422 반환 (A24-1)."""
    app.dependency_overrides[require_user] = lambda: "test-user-id"
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. age_confirmed: False
        res = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": False,
            },
        )
        assert res.status_code == 422

        # 2. age_confirmed: "true" (문자열) -> StrictBool에 의해 422
        res2 = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": "true",
            },
        )
        assert res2.status_code == 422


@pytest.mark.asyncio
async def test_consent_invalid_version_returns_422_or_409():
    """형식이 틀린 버전은 422, 서버 버전과 다른 버전은 409 반환 (A23-1)."""
    app.dependency_overrides[require_user] = lambda: "test-user-id"
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 형식 오류 (정규식 불일치)
        res_fmt = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "v1.0.0",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res_fmt.status_code == 422

        # 버전 불일치 (2025-01-01 != 2026-09-12)
        res_conflict = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2025-01-01",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res_conflict.status_code == 409


@pytest.mark.asyncio
async def test_consent_creation_and_idempotency(monkeypatch):
    """신규 동의 201 반환 및 동일 버전 재요청 시 200 반환 멱등성 검증 (A23-1)."""
    app.dependency_overrides[require_user] = lambda: "test-user-id"
    app.dependency_overrides[check_rate_limit] = lambda: None

    now = datetime.now(timezone.utc)

    # 1. 신규 저장 (existing 없음)
    fake_new = FakeConsentSession(
        existing_row=None,
        inserted_row={"created_at": now, "terms_version": "2026-09-12", "privacy_version": "2026-09-12"},
    )
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_new)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res1.status_code == 201
        assert res1.json()["terms_version"] == "2026-09-12"
        assert fake_new.commits == 1

    # 2. 멱등 재요청 (기존 row 있음)
    fake_existing = FakeConsentSession(
        existing_row={"created_at": now, "terms_version": "2026-09-12", "privacy_version": "2026-09-12", "action": "GRANT"}
    )
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_existing)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2026-09-12",
                "privacy_version": "2026-09-12",
                "age_confirmed": True,
            },
        )
        assert res2.status_code == 200
        assert res2.json()["terms_version"] == "2026-09-12"
        assert fake_existing.commits == 0  # no new commit on idempotency hit


@pytest.mark.asyncio
async def test_get_consent_returns_record_or_null(monkeypatch):
    """GET /api/me/consent 정상 조회 및 없을 때 null 반환."""
    app.dependency_overrides[require_user] = lambda: "test-user-id"
    app.dependency_overrides[check_rate_limit] = lambda: None

    now = datetime.now(timezone.utc)

    # 1. 기록이 있는 경우
    fake_session = FakeConsentSession(
        existing_row={
            "id": "11111111-1111-1111-1111-111111111111",
            "terms_version": "2026-09-12",
            "privacy_version": "2026-09-12",
            "age_confirmed": True,
            "action": "GRANT",
            "created_at": now,
        }
    )
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/me/consent")
        assert res.status_code == 200
        data = res.json()
        assert data["current"] is not None
        assert data["current"]["terms_version"] == "2026-09-12"

    # 2. 기록이 없는 경우
    fake_empty = FakeConsentSession(existing_row=None)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_empty)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.get("/api/me/consent")
        assert res2.status_code == 200
        assert res2.json()["current"] is None
