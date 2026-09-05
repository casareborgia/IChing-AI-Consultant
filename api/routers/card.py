# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 마음 전념 카드 / SPI 카드 래스터화 스트리밍 라우터
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from core.card_image import CardImageRenderer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/counsel", tags=["Card"])


class CardExportRequest(BaseModel):
    card_data: Dict[str, Any] = Field(..., description="마음 전념 카드 또는 SPI 카드의 구조화된 데이터")


@router.post("/card/export", summary="마음 전념 카드 / SPI 카드 서버 래스터화 EXIF 세척 이미지 다운로드")
async def export_card_image(req: CardExportRequest):
    """
    모바일 인앱 브라우저나 브라우저 Canvas 제약 환경을 위한
    Pillow 기반 EXIF 완전 세척 고화질 래스터화 PNG 스트리밍 다운로드 API.
    """
    try:
        renderer = CardImageRenderer()
        stream = renderer.render_card_png(req.card_data)
        is_crisis = bool(req.card_data.get("is_crisis", False))
        filename = "emergency_safety_card.png" if is_crisis else "action_commitment_card.png"
        return StreamingResponse(
            stream,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except Exception as e:
        logger.error("카드 이미지 래스터화 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="카드 이미지를 생성하는 중 오류가 발생했습니다.",
        )
