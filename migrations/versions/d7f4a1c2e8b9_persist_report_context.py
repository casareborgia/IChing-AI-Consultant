"""persist report context on counsel sessions

Revision ID: d7f4a1c2e8b9
Revises: b41d7e6a2f95
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d7f4a1c2e8b9"
down_revision: Union[str, Sequence[str], None] = "b41d7e6a2f95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "counsel_sessions",
        sa.Column("report_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "counsel_sessions",
        sa.Column(
            "report_status",
            sa.String(length=20),
            server_default="not_requested",
            nullable=False,
        ),
    )
    op.add_column(
        "counsel_sessions",
        sa.Column("report_error_code", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("counsel_sessions", "report_error_code")
    op.drop_column("counsel_sessions", "report_status")
    op.drop_column("counsel_sessions", "report_data")
