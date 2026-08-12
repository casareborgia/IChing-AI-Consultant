"""Initial schema setup with extensions and constraints

Revision ID: 3642be719bfd
Revises: 
Create Date: 2026-08-13 00:38:47.805732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '3642be719bfd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Extensions 생성 (Cloud SQL / 일반 Postgres 환경 자동 활성화)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 1. counsel_sessions
    op.create_table(
        'counsel_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=True),
        sa.Column('raw_question', sa.Text(), nullable=False),
        sa.Column('clarified_question', sa.Text(), nullable=True),
        sa.Column('topic_category', sa.String(length=50), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('duplicate_session_ref', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['duplicate_session_ref'], ['counsel_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_counsel_sessions_user_id'), 'counsel_sessions', ['user_id'], unique=False)

    # 2. hexagrams
    op.create_table(
        'hexagrams',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('binary_code', sa.String(length=6), nullable=True),
        sa.Column('symbol', sa.String(length=10), nullable=True),
        sa.Column('name_ko', sa.String(length=50), nullable=True),
        sa.Column('name_hanja', sa.String(length=50), nullable=False),
        sa.Column('name_full', sa.String(length=100), nullable=True),
        sa.Column('judgment_text', sa.Text(), nullable=False),
        sa.Column('judgment_ko', sa.Text(), nullable=True),
        sa.Column('tanjon_text', sa.Text(), nullable=True),
        sa.Column('xiang_text', sa.Text(), nullable=True),
        sa.Column('wenyan_text', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hexagrams_binary_code'), 'hexagrams', ['binary_code'], unique=True)

    # 3. counsel_turns
    op.create_table(
        'counsel_turns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('original_hexagram_id', sa.Integer(), nullable=True),
        sa.Column('transformed_hexagram_id', sa.Integer(), nullable=True),
        sa.Column('changing_lines', sa.JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=False),
        sa.Column('agent_response', sa.Text(), nullable=False),
        sa.Column('needs_followup', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_final', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['original_hexagram_id'], ['hexagrams.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['counsel_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transformed_hexagram_id'], ['hexagrams.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'turn_number', name='uq_turn_session_turnnumber')
    )
    op.create_index(op.f('ix_counsel_turns_session_id'), 'counsel_turns', ['session_id'], unique=False)

    # 4. interpretation_chunks
    op.create_table(
        'interpretation_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('hexagram_id', sa.Integer(), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=768), nullable=True),
        sa.ForeignKeyConstraint(['hexagram_id'], ['hexagrams.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_interpretation_chunks_category'), 'interpretation_chunks', ['category'], unique=False)
    op.create_index(op.f('ix_interpretation_chunks_hexagram_id'), 'interpretation_chunks', ['hexagram_id'], unique=False)
    op.create_index(
        'ix_interpretation_chunks_embedding_hnsw',
        'interpretation_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_with={'m': 16, 'ef_construction': 64},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

    # 5. journal_entries
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('key_insights', sa.Text(), nullable=False),
        sa.Column('action_items', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['counsel_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )

    # 6. lines
    op.create_table(
        'lines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('hexagram_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('statement_text', sa.Text(), nullable=False),
        sa.Column('statement_ko', sa.Text(), nullable=True),
        sa.Column('small_xiang_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['hexagram_id'], ['hexagrams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hexagram_id', 'line_number', name='uq_line_hexagram_linenumber')
    )
    op.create_index(op.f('ix_lines_hexagram_id'), 'lines', ['hexagram_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lines_hexagram_id'), table_name='lines')
    op.drop_table('lines')
    op.drop_table('journal_entries')
    op.drop_index('ix_interpretation_chunks_embedding_hnsw', table_name='interpretation_chunks')
    op.drop_index(op.f('ix_interpretation_chunks_hexagram_id'), table_name='interpretation_chunks')
    op.drop_index(op.f('ix_interpretation_chunks_category'), table_name='interpretation_chunks')
    op.drop_table('interpretation_chunks')
    op.drop_index(op.f('ix_counsel_turns_session_id'), table_name='counsel_turns')
    op.drop_table('counsel_turns')
    op.drop_index(op.f('ix_hexagrams_binary_code'), table_name='hexagrams')
    op.drop_table('hexagrams')
    op.drop_index(op.f('ix_counsel_sessions_user_id'), table_name='counsel_sessions')
    op.drop_table('counsel_sessions')
