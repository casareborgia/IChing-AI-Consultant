"""llm cost usage tracking table

Revision ID: a02c057b8e1a
Revises: f4b1e8a92c3d
Create Date: 2026-09-12 11:10:00.000000

A02-R1: 런타임 AI 비용 상한(Cost Budget Quota) 영속화를 위한 테이블 추가.
- llm_cost_usage: 일일/월간 LLM 비용 누적액 및 호출 수 영속화
- Cloud Run scale-to-zero 콜드 스타트 및 다중 인스턴스 환경에서 예산 누적 보존
- service_role에만 SELECT, INSERT, UPDATE 권한 부여 (클라이언트 직접 접근 차단)
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a02c057b8e1a"
down_revision: Union[str, Sequence[str], None] = "f4b1e8a92c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. llm_cost_usage 테이블 생성
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.llm_cost_usage (
            period_kind TEXT NOT NULL,
            period_key TEXT NOT NULL,
            cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0,
            call_count INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (period_kind, period_key)
        )
        """
    )

    # 2. RLS 활성화
    op.execute("ALTER TABLE public.llm_cost_usage ENABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.llm_cost_usage FROM PUBLIC")

    # 3. Role 권한 설정
    op.execute(
        """
        DO $roles$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.llm_cost_usage FROM anon;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.llm_cost_usage FROM authenticated;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.llm_cost_usage FROM service_role;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.llm_cost_usage TO service_role;
            END IF;
        END
        $roles$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.llm_cost_usage CASCADE")
