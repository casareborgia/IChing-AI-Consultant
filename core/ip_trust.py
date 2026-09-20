# -*- coding: utf-8 -*-
"""클라이언트 IP 신뢰 경계 및 추출 모듈 (IP Trust Boundary).

Google Cloud External Application Load Balancer 및 Cloud Run 프록시 환경에서
X-Forwarded-For(XFF) 스푸핑 공격을 방어하고, 신뢰할 수 있는 실제 클라이언트 IP를 추출합니다.

[신뢰 정책 (경로 A: 검증된 프록시 체인만 신뢰)]:
1. 직접 연결된 peer(request.client.host)가 신뢰 프록시 대역(TRUSTED_PROXIES)에 속하지 않는 경우:
   - 외부 클라이언트가 서버에 직접 연결한 상태이므로, 클라이언트가 임의로 전송한 XFF 헤더는
     완전히 신뢰할 수 없습니다. 따라서 XFF를 무시하고 직접 peer IP를 반환합니다.
2. 직접 연결된 peer가 신뢰 프록시 대역에 속하는 경우:
   - XFF 헤더를 오른쪽부터 역순 탐색(Right-to-Left)하여 최초의 비신뢰 IP(Rightmost Untrusted IP)를
     실제 클라이언트 IP로 채택합니다.
3. 잘못된 IP 형식, 빈 항목, 비정상적으로 긴 XFF 목록 등은 안전하게 필터링 및 fallback 처리합니다.
"""

import ipaddress
import logging
from typing import List, Optional, Sequence, Union

from fastapi import Request

from core.config import settings

logger = logging.getLogger(__name__)

# 신뢰 프록시 네트워크 파싱 캐시 (설정 문자열 변경 시 갱신)
_cached_proxy_str: Optional[str] = None
_cached_networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []


def parse_trusted_networks(
    proxies_str: str,
) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """쉼표로 구분된 IP 또는 CIDR 문자열을 ipaddress 네트워크 객체 목록으로 변환합니다."""
    global _cached_proxy_str, _cached_networks
    if proxies_str == _cached_proxy_str:
        return _cached_networks

    networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]] = []
    for item in proxies_str.split(","):
        cleaned = item.strip()
        if not cleaned or cleaned == "*":
            continue
        try:
            # 단일 IP 주소나 CIDR 모두 ip_network(..., strict=False)로 안전하게 처리
            net = ipaddress.ip_network(cleaned, strict=False)
            networks.append(net)
        except ValueError as exc:
            logger.warning("신뢰 프록시 주소/대역 파싱 실패 (%s): %s", cleaned, exc)

    _cached_proxy_str = proxies_str
    _cached_networks = networks
    return networks


def is_ip_trusted(
    ip_str: str,
    trusted_networks: Sequence[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]],
) -> bool:
    """주어진 IP 문자열이 신뢰할 수 있는 프록시 네트워크 대역에 포함되는지 확인합니다."""
    if not ip_str:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        return any(ip_obj in net for net in trusted_networks)
    except ValueError:
        return False


def extract_trusted_client_ip(
    request: Request,
    trusted_proxies_override: Optional[Sequence[str]] = None,
) -> str:
    """Request로부터 신뢰할 수 있는 클라이언트 IP를 추출합니다.

    Args:
        request: FastAPI Request 객체
        trusted_proxies_override: 테스트 또는 특수 목적을 위한 신뢰 프록시 목록 오버라이드

    Returns:
        신뢰할 수 있는 클라이언트 IP 문자열 (알 수 없는 경우 'unknown')
    """
    direct_peer = (request.client.host if request.client and request.client.host else "").strip()
    if not direct_peer:
        return "unknown"

    # 신뢰 프록시 네트워크 목록 결정
    if trusted_proxies_override is not None:
        networks = []
        for p in trusted_proxies_override:
            cleaned = p.strip()
            if cleaned and cleaned != "*":
                try:
                    networks.append(ipaddress.ip_network(cleaned, strict=False))
                except ValueError:
                    pass
    else:
        proxy_setting = getattr(settings, "FORWARDED_ALLOW_IPS", "")
        networks = parse_trusted_networks(proxy_setting)

    # 1. 직접 peer가 신뢰 프록시가 아니면 XFF를 완전히 무시하고 직접 peer IP 채택 (스푸핑 차단)
    if not is_ip_trusted(direct_peer, networks):
        return direct_peer

    # 2. 직접 peer가 신뢰 프록시인 경우 X-Forwarded-For 헤더 분석
    xff_header = request.headers.get("x-forwarded-for", "").strip()
    if not xff_header:
        return direct_peer

    # 콤마로 분리 (오른쪽 30개 항목을 보존하여 DoS 방어 및 실제 클라이언트/프록시 유지)
    raw_hops = [h.strip() for h in xff_header.split(",") if h.strip()][-30:]
    if not raw_hops:
        return direct_peer

    # 오른쪽부터 역순 탐색하여 최초의 비신뢰 IP(Rightmost Untrusted IP) 탐색
    for hop in reversed(raw_hops):
        try:
            hop_ip = ipaddress.ip_address(hop)
        except ValueError:
            # 잘못된 IP 형식은 비신뢰 호스트로 간주하지 않고 건너뜀
            continue

        # 신뢰 프록시에 속하지 않는 최초의 유효한 IP를 실제 클라이언트로 확정
        if not any(hop_ip in net for net in networks):
            return str(hop_ip)

    # 모든 XFF 홉이 신뢰 프록시인 경우 direct_peer 반환
    return direct_peer
