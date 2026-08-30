import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator

from core.db import Base


class UUIDType(TypeDecorator):
    """PostgreSQL에서는 UUID로, SQLite에서는 CHAR(36)으로 동작하는 크로스 DB 호환 타입"""
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


class CounselSession(Base):
    """상담 세션 엔티티"""
    __tablename__ = "counsel_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    raw_question: Mapped[str] = mapped_column(Text, nullable=False)
    clarified_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_session_ref: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("counsel_sessions.id", ondelete="SET NULL"), nullable=True
    )
    
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    turns: Mapped[List["CounselTurn"]] = relationship("CounselTurn", back_populates="session", cascade="all, delete-orphan")
    journal: Mapped[Optional["JournalEntry"]] = relationship("JournalEntry", back_populates="session", uselist=False, cascade="all, delete-orphan")


class CounselTurn(Base):
    """상담 차수 (루프 대화 턴)"""
    __tablename__ = "counsel_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_number", name="uq_turn_session_turnnumber"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("counsel_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    original_hexagram_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hexagrams.id"), nullable=True)
    transformed_hexagram_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hexagrams.id"), nullable=True)
    changing_lines: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True
    )
    
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)

    contextual_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    evidence_items: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True
    )
    
    needs_followup: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["CounselSession"] = relationship("CounselSession", back_populates="turns")


class JournalEntry(Base):
    """상담 종료 후 회고 요약 (저널 에이전트 생성)"""
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("counsel_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_insights: Mapped[str] = mapped_column(Text, nullable=False)
    action_items: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["CounselSession"] = relationship("CounselSession", back_populates="journal")


class UserProfile(Base):
    """사용자 프로필 및 크레딧 잔액 (profiles)"""
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(UUIDType(), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CreditLedger(Base):
    """크레딧 입출금 장부 (credit_ledger)"""
    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUIDType(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
