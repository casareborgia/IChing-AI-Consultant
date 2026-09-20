# -*- coding: utf-8 -*-
"""주역 상담 앱 - 사용자 법적 동의 및 연령 확인 라우터 (AG-1 / A19, A21, A22, A24).

사용자의 이용약관, 개인정보처리방침 동의 및 만 19세 이상 확인 이력을 영속화한다.
- user_consents 테이블은 append-only 원장이다.
- service_gate에 종속되지 않는다 (서비스가 내려가도 동의 확인 및 조회가 가능해야 함).
- 멱등성을 보장한다: 동일 사용자/동일 버전에 대해 중복 저장하지 않고 200 반환.
"""

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import text

from api.deps import check_rate_limit, require_user
from core.config import settings
from core.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["Consent"])

_VERSION_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(\.\d+)?$")


def _get_expected_version() -> str:
    expected = (settings.LEGAL_DOCUMENTS_VERSION or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "LEGAL_VERSION_UNSET", "message": "정책 문서 버전이 설정되지 않았습니다."},
        )
    return expected


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms_version: str = Field(..., description="이용약관 버전 (YYYY-MM-DD[.N])")
    privacy_version: str = Field(..., description="개인정보처리방침 버전 (YYYY-MM-DD[.N])")
    age_confirmed: StrictBool = Field(..., description="만 19세 이상 여부 (엄격한 boolean)")

    @field_validator("age_confirmed")
    @classmethod
    def validate_age_confirmed(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("만 19세 이상 확인이 필요합니다.")
        return v

    @field_validator("terms_version", "privacy_version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        if not _VERSION_PATTERN.match(v.strip()):
            raise ValueError("버전 형식이 올바르지 않습니다 (YYYY-MM-DD 또는 YYYY-MM-DD.N).")
        return v.strip()


@router.post(
    "/consent",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit)],
    summary="법적 동의 및 연령 확인 기록",
)
async def record_consent(
    payload: ConsentRequest,
    user_id: str = Depends(require_user),
):
    """이용약관, 개인정보처리방침 동의 및 연령 확인을 기록합니다.

    - age_confirmed가 true가 아니면 422
    - 버전이 서버가 인지하는 현재 버전과 다르면 409
    - 같은 사용자, 같은 버전으로 이미 GRANT가 있으면 200 반환 (멱등)
    - 신규 저장이면 201 반환
    """
    expected_version = _get_expected_version()
    if (
        payload.terms_version != expected_version
        or payload.privacy_version != expected_version
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"동의 버전 불일치: 현재 서비스 약관 버전은 {expected_version}입니다."
            ),
        )

    async with AsyncSessionLocal() as db:
        try:
            # 0. 프로필 존재 보장 (FK 제약조건 만족)
            from services.credit_service import ensure_user_profile
            await ensure_user_profile(db, user_id)

            # 1. 멱등성 검사: 현재 최신 상태가 이미 동일 버전의 GRANT인지 확인
            check_stmt = text(
                """
                SELECT action, terms_version, privacy_version, created_at
                FROM public.user_consents
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            res = await db.execute(check_stmt, {"user_id": user_id})
            latest = res.mappings().first()
            if (
                latest
                and latest.get("action", "GRANT") == "GRANT"
                and latest.get("terms_version") == payload.terms_version
                and latest.get("privacy_version") == payload.privacy_version
            ):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "recorded_at": latest["created_at"].isoformat(),
                        "terms_version": latest["terms_version"],
                        "privacy_version": latest["privacy_version"],
                    },
                )

            # 2. 신규 동의 기록 생성 (GRANT)
            import uuid
            consent_id = str(uuid.uuid4())
            insert_stmt = text(
                """
                INSERT INTO public.user_consents
                    (id, user_id, terms_version, privacy_version, age_confirmed, action)
                VALUES
                    (:id, :user_id, :terms_version, :privacy_version, :age_confirmed, 'GRANT')
                RETURNING created_at, terms_version, privacy_version
                """
            )
            res = await db.execute(
                insert_stmt,
                {
                    "id": consent_id,
                    "user_id": user_id,
                    "terms_version": payload.terms_version,
                    "privacy_version": payload.privacy_version,
                    "age_confirmed": payload.age_confirmed,
                },
            )
            row = res.mappings().one()
            await db.commit()

            return {
                "recorded_at": row["created_at"].isoformat(),
                "terms_version": row["terms_version"],
                "privacy_version": row["privacy_version"],
            }
        except HTTPException:
            raise
        except Exception:
            await db.rollback()
            logger.error("동의 기록 저장 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="동의 기록 처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            )


@router.post(
    "/consent/withdraw",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_rate_limit)],
    summary="법적 동의 철회",
)
async def withdraw_consent(
    user_id: str = Depends(require_user),
):
    """현재 사용자의 유효 동의를 철회하고 action='WITHDRAW' 행을 append합니다.

    - 동의 이력이 전혀 없으면 404
    - 최신 기록이 이미 WITHDRAW이면 409
    - 최신 GRANT의 terms_version, privacy_version을 복사하여 WITHDRAW 행 생성 (201)
    """
    async with AsyncSessionLocal() as db:
        try:
            stmt = text(
                """
                SELECT id, action, terms_version, privacy_version, age_confirmed
                FROM public.user_consents
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            res = await db.execute(stmt, {"user_id": user_id})
            latest = res.mappings().first()

            if not latest:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="동의 이력이 존재하지 않아 철회할 수 없습니다.",
                )

            if latest["action"] == "WITHDRAW":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="이미 동의가 철회된 상태입니다.",
                )

            import uuid
            withdraw_id = str(uuid.uuid4())
            insert_stmt = text(
                """
                INSERT INTO public.user_consents
                    (id, user_id, terms_version, privacy_version, age_confirmed, action)
                VALUES
                    (:id, :user_id, :terms_version, :privacy_version, :age_confirmed, 'WITHDRAW')
                RETURNING created_at, terms_version, privacy_version
                """
            )
            res = await db.execute(
                insert_stmt,
                {
                    "id": withdraw_id,
                    "user_id": user_id,
                    "terms_version": latest["terms_version"],
                    "privacy_version": latest["privacy_version"],
                    "age_confirmed": latest["age_confirmed"],
                },
            )
            row = res.mappings().one()
            await db.commit()

            return {
                "withdrawn_at": row["created_at"].isoformat(),
                "terms_version": row["terms_version"],
                "privacy_version": row["privacy_version"],
            }
        except HTTPException:
            raise
        except Exception:
            await db.rollback()
            logger.error("동의 철회 처리 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="동의 철회 처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            )


@router.get(
    "/consent",
    dependencies=[Depends(check_rate_limit)],
    summary="최신 동의 및 연령 확인 이력 조회",
)
async def get_consent(user_id: str = Depends(require_user)):
    """현재 사용자의 최신 유효 동의 이력 1건을 조회합니다 (GRANT 또는 WITHDRAW)."""
    async with AsyncSessionLocal() as db:
        try:
            stmt = text(
                """
                SELECT id, terms_version, privacy_version, age_confirmed, action, created_at
                FROM public.user_consents
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            res = await db.execute(stmt, {"user_id": user_id})
            row = res.mappings().first()
            if not row:
                return {"current": None}

            return {
                "current": {
                    "id": str(row["id"]),
                    "terms_version": row["terms_version"],
                    "privacy_version": row["privacy_version"],
                    "age_confirmed": row["age_confirmed"],
                    "action": row["action"],
                    "created_at": row["created_at"].isoformat(),
                }
            }
        except Exception:
            logger.error("동의 기록 조회 실패", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="동의 기록 조회에 실패했습니다. 잠시 후 다시 시도해 주세요.",
            )

