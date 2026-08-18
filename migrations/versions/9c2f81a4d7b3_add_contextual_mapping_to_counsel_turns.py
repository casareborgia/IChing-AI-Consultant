"""add contextual_mapping to counsel_turns

괘를 뽑은 턴의 상황 매핑 초안을 보관한다. 이 칼럼이 없던 동안 후속 턴은
매핑 자리에 사용자의 질문을 대신 넣었고, 상담사는 사연을 괘의 해석으로 읽었다.

Revision ID: 9c2f81a4d7b3
Revises: 6e421e60c756
Create Date: 2026-08-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c2f81a4d7b3'
down_revision: Union[str, Sequence[str], None] = '6e421e60c756'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('counsel_turns', sa.Column('contextual_mapping', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('counsel_turns', 'contextual_mapping')
