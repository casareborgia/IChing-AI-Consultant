# -*- coding: utf-8 -*-
"""고유 loopback 포트 확보.

사용자가 이미 쓰고 있는 3005·8008 같은 포트를 절대 건드리지 않는다. 프로세스를
죽이지 않고, 비어 있는 포트를 새로 받는다.
"""

from __future__ import annotations

import socket
from typing import List

# 운영자·사용자 프로세스가 쓰는 것으로 알려진 포트. 하네스는 쓰지 않는다.
RESERVED_PORTS = frozenset({3000, 3001, 3005, 5432, 8000, 8008, 8080})


def find_free_port(preferred_start: int = 18000, attempts: int = 400) -> int:
    """127.0.0.1에서 비어 있는 포트 하나를 돌려준다."""
    for port in range(preferred_start, preferred_start + attempts):
        if port in RESERVED_PORTS:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("빈 loopback 포트를 찾지 못했습니다")


def find_free_ports(count: int, preferred_start: int = 18000) -> List[int]:
    ports: List[int] = []
    cursor = preferred_start
    for _ in range(count):
        port = find_free_port(cursor)
        ports.append(port)
        cursor = port + 1
    return ports


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0
