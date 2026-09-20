# -*- coding: utf-8 -*-
"""자체 방문 통계 (site_visits / /api/telemetry/visit) 단위 테스트.

DB를 쓰지 않는다. 세션은 mock으로 대체하고, SQL이 아니라 **판정 로직**을 본다.
- 수집 fail-closed (스위치 꺼짐 / pepper 미설정)
- 방문자 식별자 형식 검증과 입력 정규화(query 제거, referrer host만, 기기 화이트리스트)
- 세션 병합: 간격 안의 재호출은 새 방문으로 세지 않는다 (지표 부풀리기 방어)
- visit_index 증가와 첫 방문 판정
- 엔드포인트가 어떤 경우에도 화면에 오류를 내지 않는다
"""

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import check_rate_limit
from api.main import app
from services import visit_analytics_service as vas

_PEPPER = "0123456789abcdef0123456789abcdef"
_VISITOR_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"


@pytest.fixture(autouse=True)
def clean_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _settings(enabled=True, pepper=_PEPPER, gap=30, retention=180):
    return SimpleNamespace(
        VISITOR_ANALYTICS_ENABLED=enabled,
        VISITOR_ID_PEPPER=pepper,
        VISIT_SESSION_GAP_MINUTES=gap,
        VISIT_RETENTION_DAYS=retention,
    )


def _mock_session(last_row=None):
    """execute()가 항상 last_row 한 건을 돌려주는 가짜 세션."""
    session = MagicMock()
    result = MagicMock()
    result.fetchone = MagicMock(return_value=last_row)
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


# --- 수집 활성화 판정 (fail-closed) ---


def test_disabled_when_switch_off():
    with patch.object(vas, "settings", _settings(enabled=False)):
        assert vas.is_enabled() is False
        assert "VISITOR_ANALYTICS_ENABLED" in vas.disabled_reason()


def test_disabled_when_pepper_missing_even_if_switch_on():
    """스위치만 켜고 pepper를 빠뜨린 배포에서 식별자 원문이 저장되면 안 된다."""
    with patch.object(vas, "settings", _settings(pepper="")):
        assert vas.is_enabled() is False
        assert "VISITOR_ID_PEPPER" in vas.disabled_reason()

    with patch.object(vas, "settings", _settings(pepper="tooshort")):
        assert vas.is_enabled() is False


def test_enabled_with_switch_and_pepper():
    with patch.object(vas, "settings", _settings()):
        assert vas.is_enabled() is True
        assert vas.disabled_reason() is None


@pytest.mark.asyncio
async def test_record_visit_raises_when_disabled():
    with patch.object(vas, "settings", _settings(enabled=False)):
        with pytest.raises(vas.VisitAnalyticsDisabled):
            await vas.record_visit(_mock_session(), visitor_id=_VISITOR_ID)


# --- 식별자 해시 및 입력 정규화 ---


def test_visitor_hash_is_stable_and_pepper_dependent():
    with patch.object(vas, "settings", _settings()):
        first = vas.hash_visitor_id(_VISITOR_ID)
        assert first == vas.hash_visitor_id(_VISITOR_ID.upper())  # 대소문자 무관
        assert len(first) == 64
        assert _VISITOR_ID not in first  # 원문이 남지 않는다

    with patch.object(vas, "settings", _settings(pepper="f" * 32)):
        assert vas.hash_visitor_id(_VISITOR_ID) != first  # pepper가 바뀌면 해시도 바뀐다


def test_visitor_id_format_validation():
    assert vas.is_valid_visitor_id(_VISITOR_ID) is True
    assert vas.is_valid_visitor_id("a" * 32) is True
    assert vas.is_valid_visitor_id("short") is False
    assert vas.is_valid_visitor_id("x" * 200) is False
    assert vas.is_valid_visitor_id("'; DROP TABLE site_visits; --") is False
    assert vas.is_valid_visitor_id("") is False


def test_entry_path_drops_query_and_fragment():
    """OAuth 콜백의 code, 검색 유입의 검색어가 통계 테이블에 실려오면 안 된다."""
    assert vas.normalize_entry_path("/auth/callback?code=secret#x") == "/auth/callback"
    assert vas.normalize_entry_path("/") == "/"
    assert vas.normalize_entry_path(None) is None
    assert len(vas.normalize_entry_path("/" + "a" * 500)) == 128


def test_referrer_keeps_host_only():
    assert vas.normalize_referrer_host("https://www.google.com/search?q=주역") == "www.google.com"
    assert vas.normalize_referrer_host("not a url") is None
    assert vas.normalize_referrer_host(None) is None


def test_device_whitelist():
    assert vas.normalize_device("Mobile") == "mobile"
    assert vas.normalize_device("desktop") == "desktop"
    assert vas.normalize_device("<script>") is None
    assert vas.normalize_device(None) is None


# --- 방문 계수 ---


@pytest.mark.asyncio
async def test_first_visit_gets_index_one():
    session = _mock_session(last_row=None)
    with patch.object(vas, "settings", _settings()):
        result = await vas.record_visit(session, visitor_id=_VISITOR_ID)

    assert result == {"status": "recorded", "visit_index": 1, "is_returning": False}
    assert session.commit.await_count == 1


@pytest.mark.asyncio
async def test_visit_after_gap_increments_index():
    last = SimpleNamespace(id="row-1", visit_index=4, user_id=None, within_gap=False)
    session = _mock_session(last_row=last)
    with patch.object(vas, "settings", _settings()):
        result = await vas.record_visit(session, visitor_id=_VISITOR_ID)

    assert result == {"status": "recorded", "visit_index": 5, "is_returning": True}


@pytest.mark.asyncio
async def test_visit_within_gap_is_merged_not_counted():
    """새로고침을 반복해도 방문 수가 늘지 않아야 한다."""
    last = SimpleNamespace(id="row-1", visit_index=2, user_id="u-1", within_gap=True)
    session = _mock_session(last_row=last)
    with patch.object(vas, "settings", _settings()):
        result = await vas.record_visit(session, visitor_id=_VISITOR_ID)

    assert result == {"status": "merged", "visit_index": 2, "is_returning": True}
    # 조회 1회만 하고 INSERT는 하지 않는다.
    assert session.execute.await_count == 1
    assert session.commit.await_count == 0


@pytest.mark.asyncio
async def test_merged_visit_backfills_user_id_on_mid_visit_login():
    """방문 중에 로그인하면 그 방문은 회원 방문으로 잡혀야 한다."""
    last = SimpleNamespace(id="row-1", visit_index=1, user_id=None, within_gap=True)
    session = _mock_session(last_row=last)
    with patch.object(vas, "settings", _settings()):
        result = await vas.record_visit(session, visitor_id=_VISITOR_ID, user_id="user-9")

    assert result["status"] == "merged"
    assert session.execute.await_count == 2  # 조회 + user_id UPDATE
    assert session.commit.await_count == 1


# --- 집계 결과 형태 ---


def test_trend_fills_missing_days_with_zero():
    rows = [
        SimpleNamespace(kst_date=date(2026, 9, 17), visits=5, unique_visitors=4, new_visitors=2),
    ]
    series = vas._fill_trend(rows, date(2026, 9, 18), days=3)

    assert [d["date"] for d in series] == ["2026-09-16", "2026-09-17", "2026-09-18"]
    assert series[0]["visits"] == 0
    assert series[1] == {"date": "2026-09-17", "visits": 5, "unique_visitors": 4, "new_visitors": 2}
    assert series[2]["visits"] == 0


def test_revisit_rate_handles_zero_visitors():
    assert vas._revisit_rate(0, 0) == 0.0
    assert vas._revisit_rate(8, 2) == 25.0


@pytest.mark.asyncio
async def test_summarize_returns_disabled_instead_of_raising():
    """수집이 꺼져 있어도 대시보드의 나머지 지표가 함께 죽으면 안 된다."""
    with patch.object(vas, "settings", _settings(enabled=False)):
        summary = await vas.summarize_visits(_mock_session())

    assert summary["enabled"] is False
    assert "reason" in summary


# --- 엔드포인트 ---


@pytest.mark.asyncio
async def test_visit_endpoint_accepts_anonymous_and_needs_no_auth():
    app.dependency_overrides[check_rate_limit] = lambda: None

    with patch("api.routers.telemetry.record_visit", new_callable=AsyncMock) as mock_record:
        mock_record.return_value = {"status": "recorded", "visit_index": 1, "is_returning": False}
        with patch("api.routers.telemetry.AsyncSessionLocal"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.post(
                    "/api/telemetry/visit",
                    json={"visitor_id": _VISITOR_ID, "path": "/", "device": "mobile"},
                )

    assert res.status_code == 200
    assert res.json()["visit_index"] == 1
    # 비로그인 방문은 user_id 없이 기록된다.
    assert mock_record.await_args.kwargs["user_id"] is None


@pytest.mark.asyncio
async def test_visit_endpoint_rejects_malformed_visitor_id_without_error_status():
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/telemetry/visit", json={"visitor_id": "bogus"})

    assert res.status_code == 200
    assert res.json() == {"status": "rejected", "reason": "INVALID_VISITOR_ID"}


@pytest.mark.asyncio
async def test_visit_endpoint_forbids_unknown_fields():
    """클라이언트가 visit_index 같은 값을 직접 넣으려 하면 거절한다."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/telemetry/visit",
            json={"visitor_id": _VISITOR_ID, "visit_index": 999},
        )

    assert res.status_code == 422


@pytest.mark.asyncio
async def test_visit_endpoint_swallows_backend_failure():
    """통계 적재 실패가 이용자 화면의 오류로 보이면 안 된다."""
    app.dependency_overrides[check_rate_limit] = lambda: None

    with patch("api.routers.telemetry.AsyncSessionLocal", side_effect=RuntimeError("db down")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/api/telemetry/visit", json={"visitor_id": _VISITOR_ID})

    assert res.status_code == 200
    assert res.json() == {"status": "error"}


@pytest.mark.asyncio
async def test_member_link_failure_still_records_anonymous_visit():
    """프로필 행이 없는 로그인 사용자의 방문이 통째로 사라지면 안 된다.

    user_id는 profiles를 참조한다. 가입 트리거가 실패해 프로필이 없으면 FK가
    걸리는데, 그때 방문 자체를 버리면 그 사용자의 방문이 영구히 조용히 누락된다.
    회원 연결만 포기하고 익명 방문으로 남겨야 한다.
    """
    from sqlalchemy.exc import IntegrityError

    session = _mock_session(last_row=None)
    calls = []

    async def execute(stmt, params=None):
        calls.append(params)
        result = MagicMock()
        result.fetchone = MagicMock(return_value=None)
        # 첫 호출은 마지막 방문 조회, 두 번째가 회원 연결이 붙은 INSERT다.
        if len(calls) == 2:
            raise IntegrityError("insert", {}, Exception("FK violation"))
        return result

    session.execute = AsyncMock(side_effect=execute)
    session.rollback = AsyncMock()

    with patch.object(vas, "settings", _settings()):
        result = await vas.record_visit(session, visitor_id=_VISITOR_ID, user_id="ghost-user")

    assert result == {"status": "recorded", "visit_index": 1, "is_returning": False}
    assert session.rollback.await_count == 1
    assert calls[1]["user_id"] == "ghost-user"   # 처음엔 회원 연결을 시도하고
    assert calls[2]["user_id"] is None           # 실패하면 익명으로 다시 넣는다


# --- Codex 독립 검수 반려(F1, F2, F3, F5) 회귀 테스트 ---


@pytest.mark.asyncio
async def test_f1_1_purge_called_when_analytics_disabled():
    """F1-1: 수집이 꺼져 있어도 purge_expired_visits가 호출된다."""
    from api.routers.ops import get_ops_dashboard

    call_order = []

    async def mock_purge(session):
        call_order.append("purge")
        return 0

    async def mock_summarize(session):
        call_order.append("summarize")
        return {"enabled": False, "reason": "disabled"}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    with patch("api.routers.ops.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("api.routers.ops.budget_tracker.get_status_async", new_callable=AsyncMock) as mock_budget, \
         patch("api.routers.ops.purge_expired_visits", side_effect=mock_purge), \
         patch("api.routers.ops.summarize_visits", side_effect=mock_summarize):
        mock_budget.return_value = {"status": "ok"}
        res = await get_ops_dashboard(operator_id="test-op")

    assert "purge" in call_order
    assert res["visitors"]["enabled"] is False


@pytest.mark.asyncio
async def test_f1_2_purge_called_before_summarize():
    """F1-2: 파기가 summarize_visits보다 먼저 호출된다 (호출 순서 검증)."""
    from api.routers.ops import get_ops_dashboard

    call_order = []

    async def mock_purge(session):
        call_order.append("purge")
        return 3

    async def mock_summarize(session):
        call_order.append("summarize")
        return {"enabled": True, "total": {"visits": 10}}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    with patch("api.routers.ops.AsyncSessionLocal", return_value=mock_session_ctx), \
         patch("api.routers.ops.budget_tracker.get_status_async", new_callable=AsyncMock) as mock_budget, \
         patch("api.routers.ops.purge_expired_visits", side_effect=mock_purge), \
         patch("api.routers.ops.summarize_visits", side_effect=mock_summarize):
        mock_budget.return_value = {"status": "ok"}
        await get_ops_dashboard(operator_id="test-op")

    assert call_order == ["purge", "summarize"]


@pytest.mark.asyncio
async def test_f2_1_account_deletion_deletes_by_visitor_hash_before_profiles():
    """F2-1: 탈퇴 SQL이 visitor_hash 기준 DELETE이고 profiles 삭제보다 앞선다."""
    from api.routers.account import delete_my_account

    sql_executed = []

    async def mock_execute(stmt, params=None):
        sql_text = str(stmt.text if hasattr(stmt, "text") else stmt)
        sql_executed.append((sql_text, params))
        result = MagicMock()
        return result

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(side_effect=mock_execute)
    mock_session.commit = AsyncMock()
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    user_id = "00000000-0000-0000-0000-000000000001"

    with patch("api.routers.account.AsyncSessionLocal", return_value=mock_session_ctx):
        res = await delete_my_account(user_id=user_id)

    assert res["success"] is True

    site_visits_idx = -1
    profiles_idx = -1
    for idx, (sql, params) in enumerate(sql_executed):
        if "site_visits" in sql and "DELETE FROM public.site_visits" in sql:
            site_visits_idx = idx
            assert "visitor_hash IN (" in sql
            assert "WHERE user_id = :uid" in sql
        if "profiles" in sql and "DELETE FROM public.profiles" in sql:
            profiles_idx = idx

    assert site_visits_idx != -1, "site_visits 삭제 쿼리가 실행되지 않음"
    assert profiles_idx != -1, "profiles 삭제 쿼리가 실행되지 않음"
    assert site_visits_idx < profiles_idx, "site_visits 삭제가 profiles 삭제보다 먼저 실행되어야 함"


@pytest.mark.asyncio
async def test_f2_2_new_user_ping_after_deletion_does_not_relink_old_records():
    """F2-2: 탈퇴 후 같은 visitor_id + 새 user_id ping이 옛 행을 덮지 않는다."""
    session = _mock_session(last_row=None)

    with patch.object(vas, "settings", _settings()):
        res = await vas.record_visit(session, visitor_id=_VISITOR_ID, user_id="new-user-5678")

    assert res == {"status": "recorded", "visit_index": 1, "is_returning": False}
    insert_call = session.execute.call_args_list[-1]
    params = insert_call[0][1]
    assert params["visit_index"] == 1
    assert params["user_id"] == "new-user-5678"


@pytest.mark.asyncio
async def test_f3_1_telemetry_rate_limit_same_ip_rotating_auth():
    """F3-1: Authorization을 회전시켜도 같은 IP면 한도에 걸린다."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(10):
            headers = {"Authorization": f"Bearer fake_token_{i}"}
            res = await client.post("/api/telemetry/visit", json={"visitor_id": _VISITOR_ID}, headers=headers)
            assert res.status_code == 200
            assert res.json().get("status") != "throttled"

        # 11번째 요청은 토큰이 달라도 IP가 같으므로 throttled
        headers = {"Authorization": "Bearer fake_token_11"}
        res = await client.post("/api/telemetry/visit", json={"visitor_id": _VISITOR_ID}, headers=headers)
        assert res.status_code == 200
        assert res.json() == {"status": "throttled"}


@pytest.mark.asyncio
async def test_f3_2_telemetry_rate_limit_response_200_throttled():
    """F3-2: 한도 초과 시 200 + {"status":"throttled"} 반환."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(10):
            await client.post("/api/telemetry/visit", json={"visitor_id": _VISITOR_ID})
        res = await client.post("/api/telemetry/visit", json={"visitor_id": _VISITOR_ID})
        assert res.status_code == 200
        assert res.json() == {"status": "throttled"}


@pytest.mark.asyncio
async def test_f5_1_revisit_buckets_use_count_star():
    """F5-1: 분포·평균이 COUNT(*) 기준이다 (index가 5인 행 1건 → 평균 1.0)."""
    executed_sql = []

    async def mock_execute(stmt, params=None):
        sql_text = str(stmt.text if hasattr(stmt, "text") else stmt)
        executed_sql.append(sql_text)
        result = MagicMock()
        if "COUNT(*) FROM public.site_visits" in sql_text:
            result.scalar = MagicMock(return_value=1)
        elif "per_visitor" in sql_text:
            result.fetchone = MagicMock(return_value=SimpleNamespace(
                bucket_1=1, bucket_2_3=0, bucket_4_9=0, bucket_10=0, avg_visits=1.0, max_visits=1
            ))
        elif "started_at" in sql_text:
            result.fetchall = MagicMock(return_value=[])
        elif "referrer_host" in sql_text:
            result.fetchall = MagicMock(return_value=[])
        elif "device" in sql_text:
            result.fetchall = MagicMock(return_value=[])
        else:
            result.fetchone = MagicMock(return_value=(0, 0, 0, 0, 0))
            result.fetchall = MagicMock(return_value=[])
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=mock_execute)

    with patch.object(vas, "settings", _settings()):
        summary = await vas.summarize_visits(session)

    bucket_sql = [s for s in executed_sql if "per_visitor" in s][0]
    assert "COUNT(*) AS visits" in bucket_sql
    assert "MAX(visit_index)" not in bucket_sql
    assert summary["revisit_buckets"][0]["visitors"] == 1
    assert summary["total"]["avg_visits_per_visitor"] == 1.0


# --- P0: 방문자 IP 신뢰 경계 및 스푸핑 방어 회귀 테스트 (VA-P0-1 ~ VA-P0-6) ---


@pytest.mark.asyncio
async def test_va_p0_1_same_peer_rotating_spoofed_xff_throttled():
    """VA-P0-1: 같은 실제 peer/client가 XFF 앞부분만 20회 회전 시 한 IP 버킷으로 묶여 10회 이후 throttled."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    # 신뢰 프록시 대역(169.254.0.0/16)을 direct peer로 설정한 ASGI client 생성
    # 실제 클라이언트는 203.0.113.195이고, 공격자가 앞부분(1.1.1.{i})을 계속 위조
    transport = ASGITransport(app=app, client=("169.254.8.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        recorded_count = 0
        throttled_count = 0
        for i in range(20):
            # GCP External ALB 구조: <client-supplied-spoofed>, <real-client-ip>
            spoofed_xff = f"1.1.1.{i}, 203.0.113.195"
            headers = {"X-Forwarded-For": spoofed_xff}
            res = await client.post(
                "/api/telemetry/visit",
                json={"visitor_id": str(uuid.uuid4())},
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            if data.get("status") == "throttled":
                throttled_count += 1
            else:
                recorded_count += 1

        assert recorded_count == 10, f"최초 10회만 허용되어야 함 (실제: {recorded_count})"
        assert throttled_count == 10, f"이후 10회는 모두 throttled되어야 함 (실제: {throttled_count})"


@pytest.mark.asyncio
async def test_va_p0_2_different_clients_same_cloud_run_peer_separated():
    """VA-P0-2: 서로 다른 실제 client 2명이 같은 Cloud Run peer를 사용할 때 서로 다른 버킷으로 분리."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    transport = ASGITransport(app=app, client=("169.254.8.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Client A: 10회 요청
        for _ in range(10):
            headers = {"X-Forwarded-For": "198.51.100.10"}
            res = await client.post(
                "/api/telemetry/visit",
                json={"visitor_id": str(uuid.uuid4())},
                headers=headers,
            )
            assert res.status_code == 200
            assert res.json().get("status") != "throttled"

        # Client B: 10회 요청 (Client A와 같은 peer지만 XFF의 실제 IP가 다르므로 차단되지 않아야 함)
        for _ in range(10):
            headers = {"X-Forwarded-For": "198.51.100.20"}
            res = await client.post(
                "/api/telemetry/visit",
                json={"visitor_id": str(uuid.uuid4())},
                headers=headers,
            )
            assert res.status_code == 200
            assert res.json().get("status") != "throttled"


@pytest.mark.asyncio
async def test_va_p0_3_invalid_empty_excessive_xff_safe_handling():
    """VA-P0-3: 잘못된 IP, 빈 항목, 과도한 XFF 목록에 대해 예외·메모리 폭증 없이 안전한 fallback/처리."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    transport = ASGITransport(app=app, client=("169.254.8.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 잘못된 IP 문자열
        res = await client.post(
            "/api/telemetry/visit",
            json={"visitor_id": _VISITOR_ID},
            headers={"X-Forwarded-For": "invalid-ip, ::::, not_an_ip"},
        )
        assert res.status_code == 200

        # 빈 항목 콤마
        res = await client.post(
            "/api/telemetry/visit",
            json={"visitor_id": _VISITOR_ID},
            headers={"X-Forwarded-For": ", , ,   ,"},
        )
        assert res.status_code == 200

        # 과도한 XFF 목록 (100개 홉)
        excessive = ", ".join([f"10.0.0.{i}" for i in range(100)]) + ", 203.0.113.50"
        res = await client.post(
            "/api/telemetry/visit",
            json={"visitor_id": _VISITOR_ID},
            headers={"X-Forwarded-For": excessive},
        )
        assert res.status_code == 200

        # R1: 과도한 XFF 홉에서 오른쪽 경계(203.0.113.50)가 보존되어 실제 IP로 선택되는지 직접 검증
        from starlette.requests import Request
        from core.ip_trust import extract_trusted_client_ip
        scope_excessive = {
            "type": "http",
            "client": ("169.254.8.1", 50000),
            "headers": [(b"x-forwarded-for", excessive.encode("utf-8"))],
        }
        chosen_ip = extract_trusted_client_ip(Request(scope_excessive))
        assert chosen_ip == "203.0.113.50", f"R1 실패: 실제 IP 대신 {chosen_ip} 선택됨"


def test_va_p0_4_production_rejects_wildcard_and_unconfigured_fail_closed():
    """VA-P0-4: production 설정에서 미설정 및 '*' 입력 시 시작 실패 (fail-closed)."""
    from core.config import Settings
    # 1. 미설정 시 기동 실패
    with pytest.raises(ValueError, match=r"프로덕션 환경에서는 FORWARDED_ALLOW_IPS가 반드시 명시적으로 설정되어야 합니다"):
        Settings(ENVIRONMENT="production", FORWARDED_ALLOW_IPS="")

    # 2. '*' 입력 시 기동 실패
    with pytest.raises(ValueError, match=r"프로덕션 환경에서는 FORWARDED_ALLOW_IPS에 '\*'를 사용할 수 없으며"):
        Settings(ENVIRONMENT="production", FORWARDED_ALLOW_IPS="*")

    with pytest.raises(ValueError, match=r"프로덕션 환경에서는 FORWARDED_ALLOW_IPS에 '\*'를 사용할 수 없으며"):
        Settings(ENVIRONMENT="production", FORWARDED_ALLOW_IPS="127.0.0.1, *")


@pytest.mark.asyncio
async def test_va_p0_배포동형_패딩공격_rate_limit_정상동작():
    """R2 반증 2-a: uvicorn ProxyHeadersMiddleware + 앱 extractor 동시 통과 시 31홉 패딩 공격 방어 검증."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()

    docker_trusted = ["127.0.0.1", "169.254.0.0/16"]
    wrapped_app = ProxyHeadersMiddleware(app, trusted_hosts=docker_trusted)

    recorded = 0
    throttled = 0
    async with AsyncClient(transport=ASGITransport(app=wrapped_app, client=("169.254.8.1", 12345)), base_url="http://test") as client:
        for i in range(20):
            vid = str(uuid.uuid4())
            fake_hops = [f"9.9.9.{k}_{i}" for k in range(31)]
            xff = ", ".join(fake_hops + ["203.0.113.195"])
            res = await client.post("/api/telemetry/visit", json={"visitor_id": vid, "path": "/"}, headers={"x-forwarded-for": xff})
            if res.json().get("status") == "throttled":
                throttled += 1
            else:
                recorded += 1

    assert recorded == 10, f"기대 10, 실제 recorded={recorded}"
    assert throttled == 10, f"기대 10, 실제 throttled={throttled}"


@pytest.mark.asyncio
async def test_va_p0_배포동형_사설대역홉_삽입_우회차단():
    """R2 반증 2-b: uvicorn ProxyHeadersMiddleware + 사설대역 홉 삽입 시 우회 차단 검증."""
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()

    docker_trusted = ["127.0.0.1", "169.254.0.0/16"]
    wrapped_app = ProxyHeadersMiddleware(app, trusted_hosts=docker_trusted)

    recorded = 0
    throttled = 0
    async with AsyncClient(transport=ASGITransport(app=wrapped_app, client=("169.254.8.1", 12345)), base_url="http://test") as client:
        for i in range(20):
            vid = str(uuid.uuid4())
            xff = f"1.1.1.{i}, 10.20.30.40"
            res = await client.post("/api/telemetry/visit", json={"visitor_id": vid, "path": "/"}, headers={"x-forwarded-for": xff})
            if res.json().get("status") == "throttled":
                throttled += 1
            else:
                recorded += 1

    assert recorded == 10, f"기대 10, 실제 recorded={recorded}"
    assert throttled == 10, f"기대 10, 실제 throttled={throttled}"


@pytest.mark.asyncio
async def test_va_p0_5_direct_local_peer_without_proxy_headers():
    """VA-P0-5: proxy header가 없는 로컬 요청에서 직접 peer를 일관되게 사용."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    transport = ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(10):
            res = await client.post(
                "/api/telemetry/visit",
                json={"visitor_id": str(uuid.uuid4())},
            )
            assert res.status_code == 200
            assert res.json().get("status") != "throttled"

        # 11번째 요청은 direct peer 127.0.0.1 기준으로 throttled
        res = await client.post(
            "/api/telemetry/visit",
            json={"visitor_id": str(uuid.uuid4())},
        )
        assert res.status_code == 200
        assert res.json() == {"status": "throttled"}


@pytest.mark.asyncio
async def test_va_p0_6_visitor_id_rotation_rate_limited():
    """VA-P0-6: 기존 UUID 회전 14회 요청 시 recorded=10, throttled=4 유지."""
    from api.routers.telemetry import _reset_telemetry_rate_limit
    _reset_telemetry_rate_limit()
    app.dependency_overrides[check_rate_limit] = lambda: None

    transport = ASGITransport(app=app, client=("127.0.0.1", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        recorded_count = 0
        throttled_count = 0
        for _ in range(14):
            res = await client.post(
                "/api/telemetry/visit",
                json={"visitor_id": str(uuid.uuid4())},
            )
            assert res.status_code == 200
            if res.json().get("status") == "throttled":
                throttled_count += 1
            else:
                recorded_count += 1

        assert recorded_count == 10
        assert throttled_count == 4

