"""add card_data column to journal_entries

Revision ID: c08b01a7f39d
Revises: a02c057b8e1a
Create Date: 2026-09-12 11:35:00.000000

BLK-C08-01: 서버 저장본 기반 카드 이미지 렌더링 및 산출물 진위 보장.
- journal_entries 테이블에 card_data JSONB NULL 컬럼 추가
- 상담 종료 시 저널 에이전트가 생성한 full_schema card_data를 영속화
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c08b01a7f39d"
down_revision: Union[str, Sequence[str], None] = "a02c057b8e1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.journal_entries
            ADD COLUMN IF NOT EXISTS card_data JSONB NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.journal_entries
            DROP COLUMN IF EXISTS card_data;
        """
    )
