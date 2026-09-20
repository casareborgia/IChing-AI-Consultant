"""user consents and support inquiries

Revision ID: f4b1e8a92c3d
Revises: e8b72c4a91d0
Create Date: 2026-09-12 01:50:00.000000

AG-0: 법적 동의 및 고객지원 문의 영속화를 위한 테이블 추가.
- user_consents: 이용약관/개인정보 동의 및 연령 확인 이력 (append-only)
- support_inquiries: 고객지원 문의 접수 내역
두 테이블 모두 e8b72c4a91d0의 RLS 패턴을 따라 anon/authenticated의 직접 접근을
차단하고 service_role에만 최소 권한을 부여한다.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f4b1e8a92c3d"
down_revision: Union[str, Sequence[str], None] = "e8b72c4a91d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. user_consents
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.user_consents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
            terms_version TEXT NOT NULL,
            privacy_version TEXT NOT NULL,
            age_confirmed BOOLEAN NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_user_consents_user_id_created_at
            ON public.user_consents (user_id, created_at DESC)
        """
    )

    # 2. support_inquiries
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.support_inquiries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ticket_no TEXT NOT NULL UNIQUE,
            user_id UUID NULL REFERENCES public.profiles(id) ON DELETE SET NULL,
            category TEXT NOT NULL,
            email TEXT NOT NULL,
            order_id TEXT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'RECEIVED',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_support_inquiries_created_at
            ON public.support_inquiries (created_at DESC)
        """
    )

    # 3. RLS 및 Role Grants
    op.execute("ALTER TABLE public.user_consents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.support_inquiries ENABLE ROW LEVEL SECURITY")

    for table in ("user_consents", "support_inquiries"):
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC")

    op.execute(
        """
        DO $roles$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.user_consents FROM anon;
                REVOKE ALL PRIVILEGES ON TABLE public.support_inquiries FROM anon;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.user_consents FROM authenticated;
                REVOKE ALL PRIVILEGES ON TABLE public.support_inquiries FROM authenticated;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.user_consents FROM service_role;
                REVOKE ALL PRIVILEGES ON TABLE public.support_inquiries FROM service_role;
                GRANT SELECT, INSERT ON TABLE public.user_consents TO service_role;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.support_inquiries TO service_role;
            END IF;
        END
        $roles$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.support_inquiries CASCADE")
    op.execute("DROP TABLE IF EXISTS public.user_consents CASCADE")
