# -*- coding: utf-8 -*-
"""자체 1st-party 방문 통계 서비스 (운영 대시보드의 방문자수·재방문 횟수).

왜 자체 수집인가
----------------
`@vercel/analytics`는 Vercel 대시보드로만 가고 우리 DB에 아무 것도 남기지 않는다.
Vercel Web Analytics API는 Pro 플랜이 전제이고, 무엇보다 **"방문자별 재방문 횟수"
라는 지표를 제공하지 않는다.** 그래서 방문 이벤트를 직접 적재한다.

수집 최소화 (가명처리)
-----------------------
- IP·User-Agent 원문을 저장하지 않는다. 기기는 mobile/tablet/desktop 세 값으로만.
- 방문자 식별자는 서버 pepper를 섞은 SHA-256 해시로 가명처리하여 남긴다(익명화가 아닌
  가명처리). pepper가 없으면 수집 자체를 하지 않는다(fail-closed).
- referrer는 host만 남긴다. path·query는 버린다.

방문(visit)의 정의
------------------
같은 방문자의 요청이 `VISIT_SESSION_GAP_MINUTES` 안에 다시 들어오면 새 방문으로
세지 않는다. 이건 통계적 관례이면서 동시에 **지표 조작 방어**다. 이 엔드포인트는
비로그인도 호출할 수 있으므로, 새로고침을 반복해 방문 수를 부풀리는 것을 서버가
막아야 한다. `visit_index`(그 방문자의 n번째 방문)도 서버가 계산해 박는다.
"""

import hashlib
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.config import settings

logger = logging.getLogger(__name__)

# 브라우저가 발급하는 방문자 식별자의 허용 형식. UUID v4 또는 32~64자 hex.
# 임의 길이의 문자열을 그대로 해시 입력으로 받지 않는다.
_VISITOR_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{32,64}$")

# pepper가 이보다 짧으면 해시가 사실상 방문자 식별자 원문과 다름없다.
_MIN_PEPPER_LENGTH = 16

_ALLOWED_DEVICES = {"mobile", "tablet", "desktop"}

# 집계 기준 시간대. 운영자가 한국에서 보는 대시보드이므로 UTC 날짜로 끊으면
# "오늘 방문자"가 오전 9시에 리셋된다.
_TZ = "Asia/Seoul"

_TREND_DAYS = 14


_INSERT_VISIT = text(
    """
    INSERT INTO public.site_visits
        (visitor_hash, visit_index, user_id, entry_path, referrer_host, device)
    VALUES
        (:visitor_hash, :visit_index, CAST(:user_id AS uuid), :entry_path, :referrer_host, :device)
    """
)


class VisitAnalyticsDisabled(Exception):
    """수집이 꺼져 있거나 pepper가 없어 방문을 기록할 수 없는 상태."""


def is_enabled() -> bool:
    """방문 수집이 실제로 가능한 상태인지. 설정 스위치와 pepper를 함께 본다."""
    if not getattr(settings, "VISITOR_ANALYTICS_ENABLED", False):
        return False
    pepper = (getattr(settings, "VISITOR_ID_PEPPER", "") or "").strip()
    if len(pepper) < _MIN_PEPPER_LENGTH:
        logger.warning(
            "VISITOR_ANALYTICS_ENABLED가 켜져 있으나 VISITOR_ID_PEPPER가 없거나 "
            "%d자 미만입니다. 방문 수집을 하지 않습니다.",
            _MIN_PEPPER_LENGTH,
        )
        return False
    return True


def disabled_reason() -> Optional[str]:
    """수집이 안 되는 이유. 가능한 상태면 None. 운영 대시보드에 그대로 띄운다."""
    if not getattr(settings, "VISITOR_ANALYTICS_ENABLED", False):
        return "VISITOR_ANALYTICS_ENABLED가 꺼져 있습니다."
    if len((getattr(settings, "VISITOR_ID_PEPPER", "") or "").strip()) < _MIN_PEPPER_LENGTH:
        return f"VISITOR_ID_PEPPER가 비었거나 {_MIN_PEPPER_LENGTH}자 미만입니다."
    return None


def hash_visitor_id(visitor_id: str) -> str:
    """방문자 식별자를 서버 pepper와 함께 해시한다. 원문은 저장하지 않는다."""
    pepper = (getattr(settings, "VISITOR_ID_PEPPER", "") or "").strip()
    if len(pepper) < _MIN_PEPPER_LENGTH:
        raise VisitAnalyticsDisabled("VISITOR_ID_PEPPER가 설정되지 않았습니다.")
    digest = hashlib.sha256(f"{pepper}:{visitor_id.strip().lower()}".encode("utf-8"))
    return digest.hexdigest()


def is_valid_visitor_id(visitor_id: str) -> bool:
    return bool(_VISITOR_ID_PATTERN.match((visitor_id or "").strip()))


def normalize_entry_path(raw: Optional[str]) -> Optional[str]:
    """진입 경로에서 path만 남긴다. query·fragment는 버린다.

    query string에 무엇이 실려 올지는 우리가 통제하지 못한다(OAuth 콜백의 code,
    검색 유입의 검색어 등). 그래서 저장 전에 잘라낸다.
    """
    if not raw:
        return None
    path = urlsplit(raw.strip()).path or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path[:128]


def normalize_referrer_host(raw: Optional[str]) -> Optional[str]:
    """referrer에서 host만 남긴다. 같은 사이트 내 이동은 유입이 아니므로 버린다."""
    if not raw:
        return None
    host = (urlsplit(raw.strip()).hostname or "").lower()
    if not host:
        return None
    return host[:128]


def normalize_device(raw: Optional[str]) -> Optional[str]:
    value = (raw or "").strip().lower()
    return value if value in _ALLOWED_DEVICES else None


async def record_visit(
    session,
    *,
    visitor_id: str,
    user_id: Optional[str] = None,
    entry_path: Optional[str] = None,
    referrer: Optional[str] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """방문을 기록하고 그 방문자의 누적 방문 횟수를 돌려준다.

    세션 간격(`VISIT_SESSION_GAP_MINUTES`) 안의 재호출은 새 방문으로 세지 않고
    기존 방문에 병합한다. 그때 회원 연결만 뒤늦게 채워준다(방문 도중 로그인).
    """
    if not is_enabled():
        raise VisitAnalyticsDisabled(disabled_reason() or "수집이 비활성 상태입니다.")

    visitor_hash = hash_visitor_id(visitor_id)
    gap_minutes = max(1, int(getattr(settings, "VISIT_SESSION_GAP_MINUTES", 30) or 30))

    last_row = (
        await session.execute(
            text(
                """
                SELECT id, visit_index, user_id,
                       (now() - started_at) < make_interval(mins => :gap) AS within_gap
                FROM public.site_visits
                WHERE visitor_hash = :visitor_hash
                ORDER BY started_at DESC
                LIMIT 1
                """
            ),
            {"visitor_hash": visitor_hash, "gap": gap_minutes},
        )
    ).fetchone()

    if last_row is not None and last_row.within_gap:
        # 같은 방문으로 본다. 방문 중에 로그인했다면 회원 연결만 채운다.
        if user_id and last_row.user_id is None:
            await session.execute(
                text(
                    "UPDATE public.site_visits SET user_id = CAST(:user_id AS uuid) WHERE id = :id"
                ),
                {"user_id": user_id, "id": last_row.id},
            )
            await session.commit()
        return {
            "status": "merged",
            "visit_index": last_row.visit_index,
            "is_returning": last_row.visit_index > 1,
        }

    visit_index = (last_row.visit_index + 1) if last_row is not None else 1
    params = {
        "visitor_hash": visitor_hash,
        "visit_index": visit_index,
        "user_id": user_id,
        "entry_path": normalize_entry_path(entry_path),
        "referrer_host": normalize_referrer_host(referrer),
        "device": normalize_device(device),
    }

    try:
        await session.execute(_INSERT_VISIT, params)
        await session.commit()
    except IntegrityError:
        # user_id는 profiles를 참조한다. 프로필 행이 아직 없는 로그인 사용자
        # (가입 트리거 실패 등)라면 FK가 걸린다. 그때 방문을 통째로 버리지 않고
        # 익명 방문으로 남긴다 — 회원 연결은 부가 정보이고, 방문자수가 본 지표다.
        # 이걸 놓치면 그 사용자의 방문이 영구히, 조용히 사라진다.
        if not user_id:
            raise
        await session.rollback()
        logger.warning("방문 기록의 회원 연결 실패(익명 방문으로 기록): user_id=%s", user_id)
        await session.execute(_INSERT_VISIT, {**params, "user_id": None})
        await session.commit()

    return {
        "status": "recorded",
        "visit_index": visit_index,
        "is_returning": visit_index > 1,
    }


def _fill_trend(rows: List[Any], today: date, days: int = _TREND_DAYS) -> List[Dict[str, Any]]:
    """비어 있는 날짜를 0으로 채운 일별 추이. 방문이 없는 날도 자리를 차지해야 한다."""
    by_date = {
        row.kst_date: {
            "visits": int(row.visits or 0),
            "unique_visitors": int(row.unique_visitors or 0),
            "new_visitors": int(row.new_visitors or 0),
        }
        for row in rows
    }
    series: List[Dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        entry = by_date.get(day, {"visits": 0, "unique_visitors": 0, "new_visitors": 0})
        series.append({"date": day.isoformat(), **entry})
    return series


def _revisit_rate(unique_visitors: int, returning_visitors: int) -> float:
    if unique_visitors <= 0:
        return 0.0
    return round(returning_visitors * 100.0 / unique_visitors, 1)


async def purge_expired_visits(session) -> int:
    """보존 기간이 지난 방문 로그를 파기하고 삭제 건수를 돌려준다.

    별도 배치 스케줄러가 없어 운영 대시보드를 열 때 함께 돈다. 인덱스가 있는
    started_at 범위 삭제라 비용이 크지 않고, 지표는 기간 집계라 영향이 없다.
    """
    retention_days = int(getattr(settings, "VISIT_RETENTION_DAYS", 180) or 180)
    if retention_days <= 0:
        return 0
    result = await session.execute(
        text(
            """
            DELETE FROM public.site_visits
            WHERE started_at < now() - make_interval(days => :days)
            """
        ),
        {"days": retention_days},
    )
    await session.commit()
    return int(result.rowcount or 0)


async def summarize_visits(session) -> Dict[str, Any]:
    """운영 대시보드용 방문자·재방문 지표 묶음.

    수집이 꺼져 있어도 예외를 던지지 않는다. 대시보드의 다른 지표가 방문 통계
    때문에 같이 죽으면 안 된다.
    """
    reason = disabled_reason()
    if reason is not None:
        return {"enabled": False, "reason": reason}

    # 1. 기간별 방문/방문자/신규/재방문. 한 번의 스캔으로 끝낸다.
    period_row = (
        await session.execute(
            text(
                f"""
                WITH v AS (
                    SELECT visitor_hash,
                           visit_index,
                           user_id,
                           (started_at AT TIME ZONE '{_TZ}')::date AS kst_date
                    FROM public.site_visits
                ),
                b AS (SELECT (now() AT TIME ZONE '{_TZ}')::date AS today)
                SELECT
                    b.today AS today,
                    COUNT(*) FILTER (WHERE kst_date = b.today) AS today_visits,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date = b.today) AS today_uv,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date = b.today AND visit_index = 1) AS today_new,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date = b.today AND visit_index > 1) AS today_returning,
                    COUNT(*) FILTER (WHERE kst_date >= b.today - 6) AS week_visits,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 6) AS week_uv,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 6 AND visit_index = 1) AS week_new,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 6 AND visit_index > 1) AS week_returning,
                    COUNT(*) FILTER (WHERE kst_date >= b.today - 29) AS month_visits,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 29) AS month_uv,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 29 AND visit_index = 1) AS month_new,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE kst_date >= b.today - 29 AND visit_index > 1) AS month_returning,
                    COUNT(*) AS total_visits,
                    COUNT(DISTINCT visitor_hash) AS total_uv,
                    COUNT(*) FILTER (WHERE user_id IS NOT NULL) AS member_visits
                FROM v CROSS JOIN b
                GROUP BY b.today
                """
            )
        )
    ).fetchone()

    # 방문이 한 건도 없으면 GROUP BY 결과가 비어 있다.
    if period_row is None:
        today_date = (
            await session.execute(
                text(f"SELECT (now() AT TIME ZONE '{_TZ}')::date AS today")
            )
        ).scalar()
        return {
            "enabled": True,
            "timezone": _TZ,
            "today": _empty_period(),
            "last_7d": _empty_period(),
            "last_30d": _empty_period(),
            "total": {"visits": 0, "unique_visitors": 0, "avg_visits_per_visitor": 0.0},
            "revisit_buckets": _empty_buckets(),
            "member_visits": 0,
            "anonymous_visits": 0,
            "trend": _fill_trend([], today_date or date.today()),
            "top_referrers": [],
            "devices": [],
        }

    # 2. 재방문 횟수 분포. 방문자 단위로 묶어 구간별 인원을 센다.
    bucket_row = (
        await session.execute(
            text(
                """
                WITH per_visitor AS (
                    SELECT visitor_hash, COUNT(*) AS visits
                    FROM public.site_visits
                    GROUP BY visitor_hash
                )
                SELECT
                    COUNT(*) FILTER (WHERE visits = 1) AS bucket_1,
                    COUNT(*) FILTER (WHERE visits BETWEEN 2 AND 3) AS bucket_2_3,
                    COUNT(*) FILTER (WHERE visits BETWEEN 4 AND 9) AS bucket_4_9,
                    COUNT(*) FILTER (WHERE visits >= 10) AS bucket_10,
                    COALESCE(AVG(visits), 0) AS avg_visits,
                    COALESCE(MAX(visits), 0) AS max_visits
                FROM per_visitor
                """
            )
        )
    ).fetchone()

    # 3. 최근 14일 일별 추이.
    trend_rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    (started_at AT TIME ZONE '{_TZ}')::date AS kst_date,
                    COUNT(*) AS visits,
                    COUNT(DISTINCT visitor_hash) AS unique_visitors,
                    COUNT(DISTINCT visitor_hash) FILTER (WHERE visit_index = 1) AS new_visitors
                FROM public.site_visits
                WHERE (started_at AT TIME ZONE '{_TZ}')::date
                      >= (now() AT TIME ZONE '{_TZ}')::date - CAST(:span AS integer)
                GROUP BY kst_date
                ORDER BY kst_date ASC
                """
            ),
            {"span": _TREND_DAYS - 1},
        )
    ).fetchall()

    # 4. 최근 30일 유입 출처와 기기 분포.
    referrer_rows = (
        await session.execute(
            text(
                f"""
                SELECT referrer_host, COUNT(*) AS visits
                FROM public.site_visits
                WHERE referrer_host IS NOT NULL
                  AND (started_at AT TIME ZONE '{_TZ}')::date
                      >= (now() AT TIME ZONE '{_TZ}')::date - 29
                GROUP BY referrer_host
                ORDER BY visits DESC
                LIMIT 5
                """
            )
        )
    ).fetchall()
    device_rows = (
        await session.execute(
            text(
                f"""
                SELECT COALESCE(device, 'unknown') AS device, COUNT(*) AS visits
                FROM public.site_visits
                WHERE (started_at AT TIME ZONE '{_TZ}')::date
                      >= (now() AT TIME ZONE '{_TZ}')::date - 29
                GROUP BY COALESCE(device, 'unknown')
                ORDER BY visits DESC
                """
            )
        )
    ).fetchall()

    total_visits = int(period_row.total_visits or 0)
    total_uv = int(period_row.total_uv or 0)
    member_visits = int(period_row.member_visits or 0)

    return {
        "enabled": True,
        "timezone": _TZ,
        "today": _period(period_row, "today"),
        "last_7d": _period(period_row, "week"),
        "last_30d": _period(period_row, "month"),
        "total": {
            "visits": total_visits,
            "unique_visitors": total_uv,
            "avg_visits_per_visitor": round(float(bucket_row.avg_visits or 0), 2),
            "max_visits_per_visitor": int(bucket_row.max_visits or 0),
        },
        "revisit_buckets": [
            {"label": "1회 (첫 방문)", "visitors": int(bucket_row.bucket_1 or 0)},
            {"label": "2~3회", "visitors": int(bucket_row.bucket_2_3 or 0)},
            {"label": "4~9회", "visitors": int(bucket_row.bucket_4_9 or 0)},
            {"label": "10회 이상", "visitors": int(bucket_row.bucket_10 or 0)},
        ],
        "member_visits": member_visits,
        "anonymous_visits": max(0, total_visits - member_visits),
        "trend": _fill_trend(trend_rows, period_row.today),
        "top_referrers": [
            {"host": row.referrer_host, "visits": int(row.visits or 0)} for row in referrer_rows
        ],
        "devices": [
            {"device": row.device, "visits": int(row.visits or 0)} for row in device_rows
        ],
    }


def _period(row: Any, prefix: str) -> Dict[str, Any]:
    unique_visitors = int(getattr(row, f"{prefix}_uv") or 0)
    returning_visitors = int(getattr(row, f"{prefix}_returning") or 0)
    return {
        "visits": int(getattr(row, f"{prefix}_visits") or 0),
        "unique_visitors": unique_visitors,
        "new_visitors": int(getattr(row, f"{prefix}_new") or 0),
        "returning_visitors": returning_visitors,
        "revisit_rate_pct": _revisit_rate(unique_visitors, returning_visitors),
    }


def _empty_period() -> Dict[str, Any]:
    return {
        "visits": 0,
        "unique_visitors": 0,
        "new_visitors": 0,
        "returning_visitors": 0,
        "revisit_rate_pct": 0.0,
    }


def _empty_buckets() -> List[Dict[str, Any]]:
    return [
        {"label": "1회 (첫 방문)", "visitors": 0},
        {"label": "2~3회", "visitors": 0},
        {"label": "4~9회", "visitors": 0},
        {"label": "10회 이상", "visitors": 0},
    ]
