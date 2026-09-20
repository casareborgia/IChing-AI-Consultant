# -*- coding: utf-8 -*-
"""AG-3: 상담 기록 열람 및 삭제 HTTP 계약 단위 테스트 (tests/test_records.py)."""

from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import check_rate_limit, require_user
from api.main import app
from api.routers import records as records_router


class _MappingsResult:
    def __init__(self, rows=None, rowcount=0, scalar_val=0):
        self._rows = rows or []
        self.rowcount = rowcount
        self._scalar_val = scalar_val

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar_val


class FakeRecordsSession:
    def __init__(self, session_row=None, turn_rows=None, journal_row=None, delete_rowcount=1, scrub_rowcount=1):
        self.session_row = session_row
        self.turn_rows = turn_rows or []
        self.journal_row = journal_row
        self.delete_rowcount = delete_rowcount
        self.scrub_rowcount = scrub_rowcount
        self.commits = 0
        self.rollbacks = 0
        self.executed_queries = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, stmt, params=None):
        stmt_str = str(stmt).strip()
        self.executed_queries.append((stmt_str, params))

        if "SELECT COUNT(*) AS cnt FROM public.counsel_turns" in stmt_str:
            return _MappingsResult(scalar_val=len(self.turn_rows))
        elif "SELECT COUNT(*) AS cnt FROM public.journal_entries" in stmt_str:
            return _MappingsResult(scalar_val=1 if self.journal_row else 0)
        elif "DELETE FROM public.counsel_sessions" in stmt_str:
            return _MappingsResult(rowcount=self.delete_rowcount)
        elif "UPDATE public.credit_operations" in stmt_str:
            return _MappingsResult(rowcount=self.scrub_rowcount)
        elif "FROM public.counsel_sessions cs" in stmt_str:
            # 목록 조회
            if self.session_row:
                return _MappingsResult([self.session_row])
            return _MappingsResult([])
        elif "FROM public.counsel_sessions" in stmt_str:
            # 상세 세션 조회
            if self.session_row:
                return _MappingsResult([self.session_row])
            return _MappingsResult([])
        elif "FROM public.counsel_turns" in stmt_str:
            return _MappingsResult(self.turn_rows)
        elif "FROM public.journal_entries" in stmt_str:
            if self.journal_row:
                return _MappingsResult([self.journal_row])
            return _MappingsResult([])

        return _MappingsResult([])

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_records_unauthorized_returns_401():
    """인증 헤더 없이 요청 시 401 반환 (A29-7)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_list = await client.get("/api/me/records")
        assert res_list.status_code == 401

        res_detail = await client.get("/api/me/records/some-session-id")
        assert res_detail.status_code == 401

        res_del = await client.delete("/api/me/records/some-session-id")
        assert res_del.status_code == 401


@pytest.mark.asyncio
async def test_records_list_success(monkeypatch):
    """목록 조회: 본인 세션 메타 및 페이지네이션 반환 (A29-1)."""
    app.dependency_overrides[require_user] = lambda: "user-123"
    app.dependency_overrides[check_rate_limit] = lambda: None

    now = datetime.now(timezone.utc)
    fake_session = FakeRecordsSession(
        session_row={
            "session_id": "session-1",
            "created_at": now,
            "updated_at": now,
            "status": "completed",
            "topic_category": "커리어",
            "turn_count": 3,
            "has_journal": True,
        }
    )
    monkeypatch.setattr(records_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/me/records?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "records" in data
        assert len(data["records"]) == 1
        assert data["records"][0]["session_id"] == "session-1"
        assert data["records"][0]["turn_count"] == 3
        assert data["records"][0]["has_journal"] is True
        # 목록에는 사용자 질문 본문이나 답변 본문이 포함되지 않음
        assert "user_message" not in data["records"][0]
        assert "agent_response" not in data["records"][0]


@pytest.mark.asyncio
async def test_records_detail_and_404_for_foreign_or_missing_session(monkeypatch):
    """상세 조회 성공 및 타인/미존재 세션 404 반환 (A29-2, A29-3)."""
    app.dependency_overrides[require_user] = lambda: "user-123"
    app.dependency_overrides[check_rate_limit] = lambda: None

    now = datetime.now(timezone.utc)

    # 1. 정상 조회
    fake_session = FakeRecordsSession(
        session_row={
            "id": "session-1",
            "created_at": now,
            "updated_at": now,
            "status": "completed",
            "raw_question": "이직할 수 있을까요?",
            "clarified_question": "올해 상반기 이직 시기",
            "topic_category": "커리어",
        },
        turn_rows=[
            {
                "turn_number": 1,
                "user_message": "이직할 수 있을까요?",
                "agent_response": "화천대유 괘가 나왔습니다.",
                "original_hexagram_id": 14,
                "transformed_hexagram_id": 14,
                "changing_lines": [],
                "created_at": now,
            }
        ],
        journal_row={
            "summary": "자신감을 갖고 기회를 잡으십시오.",
            "key_insights": ["역량 발휘의 때"],
            "action_items": ["이력서 정리"],
            "created_at": now,
        },
    )
    monkeypatch.setattr(records_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/me/records/session-1")
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == "session-1"
        assert len(data["turns"]) == 1
        assert data["journal"]["summary"] == "자신감을 갖고 기회를 잡으십시오."

    # 2. 타인 세션 또는 없는 세션 -> 404 Not Found (403 아님!)
    fake_empty = FakeRecordsSession(session_row=None)
    monkeypatch.setattr(records_router, "AsyncSessionLocal", lambda: fake_empty)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_404 = await client.get("/api/me/records/foreign-session")
        assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_records_deletion_and_snapshot_scrubbing(monkeypatch):
    """세션 삭제 시 턴/저널/스냅샷 파기 보고 및 타인 세션 404 (A29-3, A29-5, A29-6)."""
    app.dependency_overrides[require_user] = lambda: "user-123"
    app.dependency_overrides[check_rate_limit] = lambda: None

    # 1. 정상 삭제 (rowcount=1)
    fake_session = FakeRecordsSession(
        turn_rows=[{"id": 1}, {"id": 2}],
        journal_row={"id": 1},
        delete_rowcount=1,
        scrub_rowcount=2,
    )
    monkeypatch.setattr(records_router, "AsyncSessionLocal", lambda: fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.delete("/api/me/records/session-1")
        assert res.status_code == 200
        data = res.json()
        assert data["deleted"] is True
        assert data["session_id"] == "session-1"
        assert data["turns_deleted"] == 2
        assert data["journal_deleted"] == 1
        assert data["operation_snapshots_scrubbed"] == 2
        assert fake_session.commits == 1

    # 2. 타인 세션 또는 없는 세션 삭제 시도 -> 404 (rowcount=0)
    fake_no_match = FakeRecordsSession(delete_rowcount=0)
    monkeypatch.setattr(records_router, "AsyncSessionLocal", lambda: fake_no_match)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_del_404 = await client.delete("/api/me/records/foreign-session")
        assert res_del_404.status_code == 404
        assert fake_no_match.rollbacks == 1
