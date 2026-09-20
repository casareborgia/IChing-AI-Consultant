# -*- coding: utf-8 -*-
"""주역 상담 앱 - 회원 탈퇴 및 계정 파기 라우터 (AccountRouter / A31, A32).

개인정보보호법 및 잊힐 권리(Right to be Forgotten) 보장을 위한 계정 및 상담 데이터 영구 파기 엔드포인트.
- DELETE /api/me/account: 본인 계정, 프로필, 상담 기록, 저널, 크레딧 원장을 원자적으로 즉시 영구 삭제합니다.
- 본인 인증(JWT sub) 필수 (require_user).
"""

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from api.deps import check_rate_limit, require_user
from core.db import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["Account"])


@router.delete(
    "/account",
    dependencies=[Depends(check_rate_limit)],
    summary="회원 탈퇴 및 계정/데이터 영구 파기",
)
async def delete_my_account(
    user_id: str = Depends(require_user),
) -> Dict[str, Any]:
    """인증된 사용자의 모든 상담 데이터, 저널, 크레딧 원장 및 인증 계정을 즉시 영구 파기합니다."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바른 UUID 형식이 아닙니다.",
        )

    async with AsyncSessionLocal() as session:
        try:
            # 1. 사용자의 상담 세션에 종속된 턴 및 저널 삭제
            await session.execute(
                text("""
                    DELETE FROM public.counsel_turns 
                    WHERE session_id IN (SELECT id FROM public.counsel_sessions WHERE user_id = :uid_str)
                """),
                {"uid_str": str(user_uuid)},
            )
            await session.execute(
                text("""
                    DELETE FROM public.journal_entries 
                    WHERE session_id IN (SELECT id FROM public.counsel_sessions WHERE user_id = :uid_str)
                """),
                {"uid_str": str(user_uuid)},
            )

            # 2. 상담 세션 삭제
            await session.execute(
                text("DELETE FROM public.counsel_sessions WHERE user_id = :uid_str"),
                {"uid_str": str(user_uuid)},
            )

            # 3. 크레딧 작업 및 원장 내역 삭제
            await session.execute(
                text("DELETE FROM public.credit_operations WHERE user_id = :uid"),
                {"uid": user_uuid},
            )
            await session.execute(
                text("DELETE FROM public.credit_ledger WHERE user_id = :uid"),
                {"uid": user_uuid},
            )

            # 4. 법적 동의 내역 삭제
            await session.execute(
                text("DELETE FROM public.user_consents WHERE user_id = :uid"),
                {"uid": user_uuid},
            )

            # 5. 고객지원 문의 내역에서 사용자 식별자 분리 (익명화 보존)
            await session.execute(
                text("UPDATE public.support_inquiries SET user_id = NULL WHERE user_id = :uid"),
                {"uid": user_uuid},
            )

            # 5-1. 방문 로그 완전 삭제 (F2: 탈퇴 회원의 브라우저 재식별·재연결 방지)
            #
            # user_id만 NULL로 두면 안정적인 visitor_hash가 남아 동일 브라우저의
            # 새 계정에 과거 방문 행이 재연결된다. visitor_hash는 익명이 아닌 가명처리이므로
            # 잊힐 권리를 보장하기 위해 해당 사용자의 모든 방문 기록(비로그인 포함)을 영구 삭제한다.
            # 반드시 public.profiles 삭제 전에 실행하여 user_id를 기준으로 대상을 특정한다.
            await session.execute(
                text("""
                    DELETE FROM public.site_visits
                    WHERE visitor_hash IN (
                        SELECT DISTINCT visitor_hash FROM public.site_visits WHERE user_id = :uid
                    )
                """),
                {"uid": user_uuid},
            )

            # 6. 프로필 삭제
            await session.execute(
                text("DELETE FROM public.profiles WHERE id = :uid"),
                {"uid": user_uuid},
            )

            # 1~6단계 주 개인정보 및 상담 데이터 파기 1차 확정 (주 트랜잭션 커밋)
            # auth.users 삭제 전에 먼저 커밋하여, auth.users 삭제가 실패해도
            # 이미 실행된 프로필/상담/방문기록 등의 영구 파기가 되돌아가지(롤백) 않도록 보장합니다.
            await session.commit()

            # 7. auth.users 인증 계정 영구 삭제 (별도 트랜잭션에서 시도)
            # 주의: auth.users 삭제가 실패하더라도 1~6단계의 개인 데이터는 이미 확정 파기되었습니다.
            # 다만 auth.users 계정 껍데기가 남으면 재로그인 시 Supabase handle_new_user 트리거로
            # 빈 프로필이 생성될 수 있으므로, auth_account_deleted=False로 분기하여
            # 운영자 ERROR 로그를 남기고 이용자에게 고객지원 문의를 명확히 안내합니다.
            auth_account_deleted = True
            try:
                await session.execute(
                    text("DELETE FROM auth.users WHERE id = :uid"),
                    {"uid": user_uuid},
                )
                await session.commit()
            except Exception as auth_err:
                auth_account_deleted = False
                await session.rollback()
                logger.error(
                    "auth.users 삭제 실패 (주 데이터는 파기 완료, 인증 계정 껍데기 잔류): user_id=%s, err=%s",
                    user_id,
                    auth_err,
                )

            if auth_account_deleted:
                logger.info("회원 탈퇴 및 계정 완전 파기 완료: user_id=%s", user_id)
                return {
                    "success": True,
                    "auth_account_deleted": True,
                    "message": "회원 탈퇴 및 모든 개인 데이터가 영구적으로 파기되었습니다.",
                }
            else:
                logger.warning("회원 탈퇴 부분 완료 (인증 계정 잔류): user_id=%s", user_id)
                return {
                    "success": True,
                    "auth_account_deleted": False,
                    "message": "상담 기록과 개인 데이터는 영구 파기되었으나, 로그인 계정 삭제가 완료되지 않았습니다. 고객지원으로 문의해 주시기 바랍니다.",
                }
        except Exception as exc:
            await session.rollback()
            logger.error("회원 탈퇴 처리 중 오류: user_id=%s", user_id, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="회원 탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
