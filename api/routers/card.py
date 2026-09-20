# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 마음 전념 카드 / SPI 카드 래스터화 스트리밍 라우터
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from api.deps import check_rate_limit, require_user
from core.card_image import CardImageRenderer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/counsel", tags=["Card"])

# 렌더러가 실제로 읽는 필드만 받는다. 캔버스 크기(1080x1520)와 폰트 경로는
# core/card_image.py에 하드코딩돼 있어 외부 입력이 정하지 못한다.
_TEXT_MAX = 2000
_ITEM_MAX = 300
_LIST_MAX = 20


class CardData(BaseModel):
    """카드 렌더링 입력.

    예전에는 `Dict[str, Any]`라 길이 제한 없는 임의 구조가 그대로 들어왔다.
    렌더링은 CPU를 쓰므로 길이 상한이 곧 비용 상한이다.

    `extra="ignore"`인 이유: 서버가 생성한 `journal_data`가 그대로 넘어오는
    경로가 있어, 지금 forbid로 막으면 알 수 없는 필드 하나에 카드 저장이
    깨진다. forbid 전환은 실제 payload를 Antigravity와 대조한 뒤 한다
    (CR-claude-008).
    """

    model_config = ConfigDict(extra="ignore")

    is_crisis: bool = False
    universe_transition: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    sacred_metaphor: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    client_aha_moment: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    client_action_pledge: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    counselor_reframing: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    crisis_warning_signs: Optional[str] = Field(default=None, max_length=_TEXT_MAX)
    inner_coping_strategies: Optional[List[str]] = Field(default=None, max_length=_LIST_MAX)
    emergency_professional_agencies: Optional[List[str]] = Field(
        default=None, max_length=_LIST_MAX
    )

    def to_renderer_dict(self) -> dict:
        """렌더러에 넘길 dict. 미지정 필드는 빼서 기존 기본값을 살린다."""
        data = self.model_dump(exclude_none=True)
        for key in ("inner_coping_strategies", "emergency_professional_agencies"):
            if key in data:
                data[key] = [str(item)[:_ITEM_MAX] for item in data[key]]
        return data


class CardExportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="상담 세션 식별자 (UUID)")


@router.post(
    "/card/export",
    dependencies=[Depends(check_rate_limit)],
    summary="마음 전념 카드 / SPI 카드 서버 래스터화 EXIF 세척 이미지 다운로드",
)
async def export_card_image(
    req: CardExportRequest,
    user_id: str = Depends(require_user),
):
    """
    모바일 인앱 브라우저나 브라우저 Canvas 제약 환경을 위한
    Pillow 기반 EXIF 완전 세척 고화질 래스터화 PNG 스트리밍 다운로드 API (BLK-C08-01).

    - 클라이언트가 제공한 임의 텍스트가 아닌, 서버 DB(journal_entries.card_data)에
      영속 저장된 공인 산출물만 렌더링하여 산출물 진위를 원천 보장합니다 (A37-8).
    - 본인 소유의 세션(cs.user_id = user_id)만 조회하며, 타인의 세션이나 미존재,
      card_data가 NULL인 과거 세션은 404로 일관되게 차단합니다 (경로 은닉).
    - require_consent는 걸지 않습니다 (이미 생성된 본인 결과물 조회).
    """
    from core.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        stmt = text(
            """
            SELECT je.card_data
            FROM public.journal_entries je
            JOIN public.counsel_sessions cs ON cs.id = je.session_id
            WHERE je.session_id = :session_id
              AND cs.user_id = :user_id
            LIMIT 1
            """
        )
        res = await db.execute(stmt, {"session_id": req.session_id, "user_id": user_id})
        row = res.mappings().first()

    if not row or not row["card_data"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="카드 데이터를 찾을 수 없거나 접근 권한이 없습니다.",
        )

    try:
        raw_card = row["card_data"]
        card_data_obj = CardData.model_validate(raw_card)
        card_data_dict = card_data_obj.to_renderer_dict()

        renderer = CardImageRenderer()
        stream = renderer.render_card_png(card_data_dict)
        is_crisis = card_data_obj.is_crisis
        filename = "emergency_safety_card.png" if is_crisis else "action_commitment_card.png"

        return StreamingResponse(
            stream,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-cache, no-store, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("카드 이미지 래스터화 실패: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="카드 이미지를 생성하는 중 오류가 발생했습니다.",
        )

