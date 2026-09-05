# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 안전 및 공공 위기 리소스 라우터
"""

from typing import Optional
from fastapi import APIRouter
from core.crisis_resources import get_all_crisis_resources, get_crisis_resources_by_context

router = APIRouter(prefix="/api/safety", tags=["Safety"])


@router.get("/resources", summary="위기상담 리소스 목록")
async def get_safety_resources(context: Optional[str] = None):
    """한국 위기상담 공공 리소스 목록을 반환합니다."""
    if context:
        return {"resources": get_crisis_resources_by_context(context)}
    return {"resources": get_all_crisis_resources()}
