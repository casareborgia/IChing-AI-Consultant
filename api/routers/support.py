# -*- coding: utf-8 -*-
"""주역 상담 앱 - 고객지원 문의 접수 라우터 (AG-4 / A20).

비로그인 및 로그인 사용자 모두의 고객지원 문의를 영속화한다.
- 5가지 방어 수칙 (서버 단독 강제):
  1. 레이트리밋: IP 기준 check_rate_limit + 이메일 해시 기준 시간당 상한 (최대 5건/시간)
  2. 카테고리: {service, refund, privacy, safety, other} allowlist. 그 외 422
  3. 본문 길이: 1자 이상 4000자 이하. 초과 시 422
  4. 이메일 형식: 엄격한 서버 측 형식 검증 (Pydantic EmailStr / regex). 클라이언트 입력 신뢰 금지
  5. 티켓 번호: 추측 불가능한 난수 포함 서버 생성 (TKT-YYYYMMDD-<8자 이상 영숫자>)
- 무노출 원칙: 문의 내용 및 이메일 주소는 절대 로그에 남기지 않는다.
- 단방향 접수: 접수된 문의를 클라이언트에 노출하는 조회 경로는 생성하지 않는다.
"""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import logging
import re
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from api.deps import check_rate_limit, require_user
from core.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/support", tags=["Support"])

_ALLOWED_CATEGORIES = frozenset({"service", "refund", "privacy", "safety", "other"})
_MAX_MESSAGE_LENGTH = 4000
_EMAIL_WINDOW_SECONDS = 3600
_EMAIL_MAX_REQUESTS = 5
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# 이메일 기준 레이트 리밋 저장소 (email_hash -> list of timestamps)
_email_rate_records: Dict[str, list] = defaultdict(list)


def _prune_email_records(now: float) -> None:
    if len(_email_rate_records) > 5000:
        expired = [
            k for k, v in _email_rate_records.items()
            if not v or (now - v[-1] > _EMAIL_WINDOW_SECONDS)
        ]
        for k in expired:
            _email_rate_records.pop(k, None)


def _check_email_rate_limit(email: str) -> None:
    now = time.time()
    _prune_email_records(now)
    # 이메일 원문을 키로 쓰지 않고 해시를 키로 사용
    email_hash = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:32]

    records = _email_rate_records[email_hash]
    # 1시간 윈도우 내 기록만 필터링
    valid_records = [t for t in records if now - t < _EMAIL_WINDOW_SECONDS]
    if len(valid_records) >= _EMAIL_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="동일 이메일로 단시간 내 너무 많은 문의가 접수되었습니다. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(_EMAIL_WINDOW_SECONDS)},
        )
    valid_records.append(now)
    _email_rate_records[email_hash] = valid_records


def _generate_ticket_no() -> str:
    """TKT-YYYYMMDD-<8자리 이상 암호학적 난수> 생성."""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()  # 8 hex characters
    return f"TKT-{now_str}-{random_part}"


class SupportInquiryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(..., description="문의 유형 (service, refund, privacy, safety, other)")
    email: str = Field(..., description="회신받을 이메일 주소")
    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_LENGTH, description="문의 본문 (최대 4000자)")
    order_id: Optional[str] = Field(None, max_length=100, description="결제 주문 ID (환불 관련)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip()
        if not _EMAIL_REGEX.match(clean) or len(clean) > 254:
            raise ValueError("유효한 이메일 주소 형식이 아닙니다.")
        return clean

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in _ALLOWED_CATEGORIES:
            raise ValueError(f"허용되지 않은 문의 유형입니다: {v}")
        return clean

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("문의 내용을 입력해 주세요.")
        if len(clean) > _MAX_MESSAGE_LENGTH:
            raise ValueError(f"문의 내용은 {_MAX_MESSAGE_LENGTH}자를 초과할 수 없습니다.")
        return clean


async def optional_user(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header:
        return None
    try:
        return await require_user(request)
    except Exception:
        return None


@router.post(
    "/inquiries",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit)],
    summary="고객지원 문의 접수 및 영속화",
)
async def submit_support_inquiry(
    payload: SupportInquiryRequest,
    user_id: Optional[str] = Depends(optional_user),
):
    """고객지원 문의를 DB에 안전하게 기록하고 티켓 번호를 발급합니다.

    - 이메일 및 문의 본문은 절대 로깅하지 않습니다.
    - 비로그인 사용자의 문의 접수를 허용합니다.
    """
    # 1. 이메일 기준 시간당 레이트리밋 확인
    _check_email_rate_limit(payload.email)

    # 2. 티켓 번호 생성
    ticket_no = _generate_ticket_no()

    async with AsyncSessionLocal() as db:
        try:
            if user_id:
                from services.credit_service import ensure_user_profile
                await ensure_user_profile(db, user_id)

            import uuid
            inquiry_id = str(uuid.uuid4())
            insert_stmt = text(
                """
                INSERT INTO public.support_inquiries
                    (id, ticket_no, user_id, category, email, order_id, message, status)
                VALUES
                    (:id, :ticket_no, :user_id, :category, :email, :order_id, :message, 'RECEIVED')
                RETURNING created_at, status
                """
            )
            res = await db.execute(
                insert_stmt,
                {
                    "id": inquiry_id,
                    "ticket_no": ticket_no,
                    "user_id": user_id,
                    "category": payload.category,
                    "email": payload.email,
                    "order_id": payload.order_id,
                    "message": payload.message,
                },
            )
            row = res.mappings().one()
            await db.commit()

            logger.info("고객지원 문의 접수 완료: ticket_no=%s, category=%s", ticket_no, payload.category)

            return {
                "ticket_no": ticket_no,
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
            }
        except Exception:
            await db.rollback()
            # 주의: 에러 로그에 payload(이메일, 본문)를 절대 노출하지 않는다.
            logger.error("고객지원 문의 DB 저장 실패 (ticket_no=%s)", ticket_no, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="고객지원 문의 접수 중 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
