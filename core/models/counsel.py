import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class CounselSession(Base):
    """상담 세션 엔티티"""
    __tablename__ = "counsel_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    raw_question: Mapped[str] = mapped_column(Text, nullable=False)
    clarified_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_session_ref: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)  # active, completed, safety_redirect

    def __init__(self, **kw):
        if "status" not in kw:
            kw["status"] = "active"
        if "is_duplicate" not in kw:
            kw["is_duplicate"] = False
        super().__init__(**kw)


    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    turns: Mapped[List["CounselTurn"]] = relationship("CounselTurn", back_populates="session", cascade="all, delete-orphan")
    journal: Mapped[Optional["JournalEntry"]] = relationship("JournalEntry", back_populates="session", uselist=False, cascade="all, delete-orphan")


class CounselTurn(Base):
    """상담 차수 (루프 대화 턴)"""
    __tablename__ = "counsel_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("counsel_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    
    original_hexagram_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hexagrams.id"), nullable=True)
    transformed_hexagram_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hexagrams.id"), nullable=True)
    changing_lines: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # e.g., [1, 3]
    
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)
    
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
