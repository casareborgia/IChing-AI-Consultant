import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects import postgresql
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
    duplicate_session_ref: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("counsel_sessions.id", ondelete="SET NULL"), nullable=True
    )
    
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)  # active, completed, safety_redirect
    
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
    )  # e.g., [1, 3]
    
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    agent_response: Mapped[str] = mapped_column(Text, nullable=False)

    # 괘를 뽑은 턴에서 해석 에이전트가 만든 상황 매핑 초안.
    #
    # 저장하는 이유는 후속 턴 때문이다. 이 값이 없던 동안 파이프라인은 그 자리에
    # 사용자의 질문을 대신 넣었고, 상담사는 사연을 괘의 해석으로 알고 읽었다.
    # 세션당 한 번(괘를 뽑은 턴)만 채워지고 나머지 턴은 비어 있다.
    contextual_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 그 턴에 프롬프트로 들어간 주석. 매핑과 같은 이유로 저장한다.
    #
    # 첫 턴에만 검색이 돌기 때문에, 저장하지 않으면 상담사가 근거 주석을 보는 것도
    # 첫 턴뿐이다. 둘째 턴부터 손이 비면 모델은 괘 이름의 통념으로 물러난다 —
    # 자르기 문제로 첫 턴이 그랬던 것과 같은 일이 뒤 턴에서 벌어진다.
    #
    # 청크 ID만 두고 다시 읽지 않고 내용을 통째로 박아 둔다. 이 값은 "그때 모델이
    # 실제로 본 것"의 기록이라, 나중에 번역을 고쳤다고 지난 답변의 근거까지 조용히
    # 바뀌면 안 된다.
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
