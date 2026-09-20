# -*- coding: utf-8 -*-
"""방문 기록 수집 라우터 (자체 1st-party 방문 통계).

- POST /api/telemetry/visit: 브라우저의 방문 1건을 기록한다.

인증을 요구하지 않는다. 비로그인 방문자를 세는 것이 이 엔드포인트의 목적이기
때문이다. 대신 다음으로 방어한다.
- check_rate_limit (IP/토큰 기준 분당 한도)
- 서버 측 세션 병합: 같은 방문자의 재호출은 새 방문으로 세지 않는다.
- visit_index를 서버가 계산한다. 클라이언트가 보내는 값은 없다.
- 수집 스위치(VISITOR_ANALYTICS_ENABLED)와 pepper가 모두 갖춰져야 적재한다.

실패해도 200을 돌려준다. 통계 적재 실패가 화면에 오류로 뜨면 안 된다.
"""

import logging
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from api.deps import check_rate_limit
from core.db import AsyncSessionLocal
from services.visit_analytics_service import (
    VisitAnalyticsDisabled,
    is_valid_visitor_id,
    record_visit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])

# telemetry 전용 IP 기준 분당 호출 제한 (F3 방어)
# Authorization 헤더 회전 공격을 방어하기 위해 request.client.host 기준으로만 센다.
_TELEMETRY_WINDOW_SECONDS = 60.0
_TELEMETRY_MAX_REQUESTS = 10
_telemetry_ip_requests: Dict[str, deque] = defaultdict(deque)


def _is_telemetry_rate_limited(ip: str) -> bool:
    """IP 기준 분당 10회 초과 여부를 확인하고 호출 시각을 기록한다."""
    now = time.time()
    times = _telemetry_ip_requests[ip]
    cutoff = now - _TELEMETRY_WINDOW_SECONDS
    while times and times[0] < cutoff:
        times.popleft()
    if len(times) >= _TELEMETRY_MAX_REQUESTS:
        return True
    times.append(now)
    # 메모리 정리: 1000개 초과 시 빈 큐 정리
    if len(_telemetry_ip_requests) > 1000:
        empty_keys = [k for k, q in _telemetry_ip_requests.items() if not q]
        for k in empty_keys:
            _telemetry_ip_requests.pop(k, None)
    return False


def _reset_telemetry_rate_limit() -> None:
    """테스트용 레이트 리미트 상태 초기화."""
    _telemetry_ip_requests.clear()


class VisitPingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visitor_id: str = Field(..., description="브라우저가 발급한 익명 방문자 식별자 (UUID)")
    path: Optional[str] = Field(None, max_length=512, description="진입 경로 (query는 서버에서 제거)")
    referrer: Optional[str] = Field(None, max_length=512, description="유입 referrer (host만 저장)")
    device: Optional[str] = Field(None, max_length=16, description="mobile | tablet | desktop")


async def _optional_user_id(request: Request) -> Optional[str]:
    """Authorization 헤더가 유효하면 user_id를, 아니면 None을 준다.

    require_user를 직접 의존성으로 걸면 비로그인 방문이 401로 떨어진다. 여기서는
    회원 방문 비율을 알기 위한 부가 정보일 뿐이므로 실패를 삼킨다(만료 토큰,
    사용자 단위 rate limit 초과 등 전부 '익명 방문'으로 처리).
    """
    if not request.headers.get("authorization", "").strip():
        return None
    try:
        from api.deps import require_user

        return await require_user(request)
    except Exception:
        return None


@router.post(
    "/visit",
    dependencies=[Depends(check_rate_limit)],
    summary="방문 1건 기록 (익명 허용)",
)
async def record_site_visit(
    payload: VisitPingRequest,
    request: Request,
) -> Dict[str, Any]:
    """방문을 기록하고 그 방문자의 누적 방문 횟수를 돌려준다.

    응답의 status가 'recorded'가 아니면 클라이언트는 방문자 식별자를 저장하지
    않는다. 수집이 꺼진 상태에서 브라우저에 식별자만 남기지 않기 위한 계약이다.
    """
    # F3 방어: 신뢰 프록시 체인을 통과한 클라이언트 IP 기준 분당 10회 제한 (P0)
    from core.ip_trust import extract_trusted_client_ip

    client_ip = extract_trusted_client_ip(request)
    if _is_telemetry_rate_limited(client_ip):
        return {"status": "throttled"}

    if not is_valid_visitor_id(payload.visitor_id):
        # 400/422로 떨어뜨리지 않는다. 지표 수집은 사용자 경험에 개입하지 않는다.
        return {"status": "rejected", "reason": "INVALID_VISITOR_ID"}

    user_id = await _optional_user_id(request)

    try:
        async with AsyncSessionLocal() as session:
            return await record_visit(
                session,
                visitor_id=payload.visitor_id,
                user_id=user_id,
                entry_path=payload.path,
                referrer=payload.referrer,
                device=payload.device,
            )
    except VisitAnalyticsDisabled:
        return {"status": "disabled"}
    except Exception as e:
        logger.warning("방문 기록 실패(무시하고 계속): %s", e)
        return {"status": "error"}
