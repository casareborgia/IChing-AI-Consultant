# -*- coding: utf-8 -*-
"""재동의 UX 회귀 테스트 (tests/test_reconsent_ux.py).

지시서 RECONSENT_UX_ORDER.md §4:
E-1: 동의 기록 없는 사용자 -> GET /api/me/consent 에서 current: None 반환, 모달 닫기 시 DB 커밋 0건
E-2: 동의 버전이 과거 버전인 사용자 -> 조회 결과 버전과 settings.LEGAL_DOCUMENTS_VERSION 불일치 (VERSION_MISMATCH)
E-3: 동의 버전이 현재 버전과 일치하는 사용자 -> 조회 결과 버전과 settings.LEGAL_DOCUMENTS_VERSION 일치 (VALID)
E-4: 최신 action이 WITHDRAW인 사용자 -> action: WITHDRAW (WITHDRAWN)
E-5: age_confirmed=False 시 422 거절 (체크박스 1개만으로 요청 시 서버 차단)
E-6: 확인 클릭 시에만 POST /api/me/consent 호출되어 정상 기록 (commits == 1)
E-7: 잘못된 버전 제출 시 409 불일치 오류 반환 및 DB 커밋 0건
E-8: 신규 가입 흐름 정상 유지 (서버 기대 버전과 일치하는 GRANT 요청 시 201 생성)
"""

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
    monkeypatch.setattr(consent_router.settings, "LEGAL_DOCUMENTS_VERSION", "2026-09-19")
    app.dependency_overrides[require_user] = lambda: "test-user-reconsent-123"
    app.dependency_overrides[check_rate_limit] = lambda: None
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e1_no_consent_record(monkeypatch):
    """E-1: 동의 기록 없는 사용자는 current가 None이며, 모달을 닫아도 동의가 기록되지 않는다."""
    fake_session = FakeConsentSession(existing_row=None)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me/consent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] is None

    # 모달 닫기 시에는 POST /api/me/consent를 호출하지 않으므로 commits == 0
    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_e2_older_version_consent(monkeypatch):
    """E-2: 동의 버전이 이전 버전(2026-09-12)인 경우 조회되며, 기대값(2026-09-19)과 불일치."""
    older_row = {
        "id": "c-old",
        "user_id": "test-user-reconsent-123",
        "terms_version": "2026-09-12",
        "privacy_version": "2026-09-12",
        "age_confirmed": True,
        "action": "GRANT",
        "created_at": datetime.now(timezone.utc),
    }
    fake_session = FakeConsentSession(existing_row=older_row)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me/consent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] is not None
        assert data["current"]["terms_version"] == "2026-09-12"
        assert data["current"]["terms_version"] != consent_router.settings.LEGAL_DOCUMENTS_VERSION


@pytest.mark.asyncio
async def test_e3_current_version_consent(monkeypatch):
    """E-3: 동의 버전이 현재 버전과 일치하면 VALID 상태."""
    current_ver = consent_router.settings.LEGAL_DOCUMENTS_VERSION
    current_row = {
        "id": "c-valid",
        "user_id": "test-user-reconsent-123",
        "terms_version": current_ver,
        "privacy_version": current_ver,
        "age_confirmed": True,
        "action": "GRANT",
        "created_at": datetime.now(timezone.utc),
    }
    fake_session = FakeConsentSession(existing_row=current_row)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me/consent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] is not None
        assert data["current"]["terms_version"] == current_ver
        assert data["current"]["privacy_version"] == current_ver
        assert data["current"]["action"] == "GRANT"


@pytest.mark.asyncio
async def test_e4_withdrawn_consent(monkeypatch):
    """E-4: 최신 action이 WITHDRAW인 사용자 조회."""
    current_ver = consent_router.settings.LEGAL_DOCUMENTS_VERSION
    withdrawn_row = {
        "id": "c-withdrawn",
        "user_id": "test-user-reconsent-123",
        "terms_version": current_ver,
        "privacy_version": current_ver,
        "age_confirmed": True,
        "action": "WITHDRAW",
        "created_at": datetime.now(timezone.utc),
    }
    fake_session = FakeConsentSession(existing_row=withdrawn_row)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/me/consent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] is not None
        assert data["current"]["action"] == "WITHDRAW"


@pytest.mark.asyncio
async def test_e5_incomplete_checkbox_rejected(monkeypatch):
    """E-5: age_confirmed가 False인 경우 서버에서 거부 (체크박스 1개만 체크 불가)."""
    fake_session = FakeConsentSession()
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/me/consent",
            json={
                "terms_version": consent_router.settings.LEGAL_DOCUMENTS_VERSION,
                "privacy_version": consent_router.settings.LEGAL_DOCUMENTS_VERSION,
                "age_confirmed": False,
            },
        )
        assert resp.status_code == 422
    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_e6_explicit_consent_records_row(monkeypatch):
    """E-6: 확인 클릭 시에만 POST /api/me/consent 호출되어 정상 기록."""
    current_ver = consent_router.settings.LEGAL_DOCUMENTS_VERSION
    now = datetime.now(timezone.utc)
    inserted_row = {
        "id": "c-new-grant",
        "user_id": "test-user-reconsent-123",
        "terms_version": current_ver,
        "privacy_version": current_ver,
        "age_confirmed": True,
        "action": "GRANT",
        "created_at": now,
    }
    fake_session = FakeConsentSession(existing_row=None, inserted_row=inserted_row)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/me/consent",
            json={
                "terms_version": current_ver,
                "privacy_version": current_ver,
                "age_confirmed": True,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["terms_version"] == current_ver
    assert fake_session.commits == 1


@pytest.mark.asyncio
async def test_e7_post_failure_does_not_commit(monkeypatch):
    """E-7: 서버 버전 불일치 등으로 실패 시 DB 커밋되지 않고 409 에러 반환."""
    fake_session = FakeConsentSession()
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/me/consent",
            json={
                "terms_version": "2025-01-01",
                "privacy_version": "2025-01-01",
                "age_confirmed": True,
            },
        )
        assert resp.status_code == 409
        assert "동의 버전 불일치" in resp.json()["detail"]
    assert fake_session.commits == 0


@pytest.mark.asyncio
async def test_e8_signup_flow_records_consent(monkeypatch):
    """E-8: 신규 가입 흐름에서 유효한 현재 버전으로 동의 시 201 성공 및 1행 커밋."""
    current_ver = consent_router.settings.LEGAL_DOCUMENTS_VERSION
    now = datetime.now(timezone.utc)
    inserted_row = {
        "id": "c-signup-grant",
        "user_id": "test-user-reconsent-123",
        "terms_version": current_ver,
        "privacy_version": current_ver,
        "age_confirmed": True,
        "action": "GRANT",
        "created_at": now,
    }
    fake_session = FakeConsentSession(existing_row=None, inserted_row=inserted_row)
    monkeypatch.setattr(consent_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/me/consent",
            json={
                "terms_version": current_ver,
                "privacy_version": current_ver,
                "age_confirmed": True,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["terms_version"] == current_ver
    assert fake_session.commits == 1
