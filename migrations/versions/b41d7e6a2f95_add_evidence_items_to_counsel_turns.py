"""add evidence_items to counsel_turns

그 턴에 프롬프트로 들어간 주석을 보관한다. 검색은 괘를 뽑은 턴에만 돌기 때문에,
저장하지 않으면 상담사가 근거 주석을 손에 쥐는 것도 그 한 턴뿐이다.

Revision ID: b41d7e6a2f95
Revises: 9c2f81a4d7b3
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b41d7e6a2f95'
down_revision: Union[str, Sequence[str], None] = '9c2f81a4d7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'counsel_turns',
        sa.Column('evidence_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('counsel_turns', 'evidence_items')
