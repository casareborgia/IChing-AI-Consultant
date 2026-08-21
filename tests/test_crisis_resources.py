"""한국 위기상담 리소스 DB 단위 테스트."""

import pytest
from core.crisis_resources import (
    KOREAN_CRISIS_RESOURCES,
    get_all_crisis_resources,
    get_crisis_resources_by_context,
)


def test_korean_crisis_resources_contains_essential_hotlines():
    """자살예방 109, 정신건강 1577-0199, 청소년 1388, 여성 1366 필수 핫라인이 존재하는지 검증."""
    assert "109" in KOREAN_CRISIS_RESOURCES
    assert "1577-0199" in KOREAN_CRISIS_RESOURCES
    assert "1388" in KOREAN_CRISIS_RESOURCES
    assert "1366" in KOREAN_CRISIS_RESOURCES

    r109 = KOREAN_CRISIS_RESOURCES["109"]
    assert r109.tel == "109"
    assert "24시간" in r109.hours


def test_get_crisis_resources_by_context():
    """정황별(minor, violence, general) 리소스 우선순위 정렬 검증."""
    # 청소년 정황: 1388이 최상위
    minor_res = get_crisis_resources_by_context("minor")
    assert minor_res[0].id == "1388"

    # 폭력 정황: 1366이 최상위
    violence_res = get_crisis_resources_by_context("violence")
    assert violence_res[0].id == "1366"

    # 기본 정황: 109가 최상위
    default_res = get_crisis_resources_by_context()
    assert default_res[0].id == "109"
