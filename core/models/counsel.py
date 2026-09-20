import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
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
    report_data: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True
    )
    report_status: Mapped[str] = mapped_column(
        String(20), default="not_requested", server_default="not_requested", nullable=False
    )
    report_error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
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
    card_data: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped["CounselSession"] = relationship("CounselSession", back_populates="journal")



class UserProfile(Base):
    """사용자 프로필 및 크레딧 잔액 (profiles)"""
    __tablename__ = "profiles"
    __table_args__ = (
        # 잔액이 음수로 내려가는 것은 어떤 경로로도 허용하지 않는다. 애플리케이션의
        # 조건부 UPDATE가 뚫리더라도 DB가 마지막으로 막는다.
        CheckConstraint(
            "credit_balance >= 0", name="ck_profiles_credit_balance_non_negative"
        ),
    )

    id: Mapped[str] = mapped_column(UUIDType(), primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_balance: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    last_refilled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CreditOperation(Base):
    """크레딧 예약 단위 작업 (credit_operations).

    한 번의 `/start` 또는 `/turn` POST가 여기 한 행으로 대응한다. 결제 의미는
    이 행의 `status` 하나로 결정된다 (`SUCCEEDED`만 최종 -amount, `RELEASED`와
    `REJECTED`는 최종 0).

    `fencing_token`은 lease 만료 복구와 늦게 돌아온 원래 실행이 경합할 때
    누가 종결을 쓸 자격이 있는지 가른다. 모든 상태 전이는 현재 상태와 이
    토큰을 함께 조건으로 거는 원자적 UPDATE로만 일어난다.
    """

    __tablename__ = "credit_operations"
    __table_args__ = (
        # 멱등 키의 범위는 (인증된 사용자, endpoint)다. 다른 사용자가 같은 키를
        # 써도 서로의 작업을 건드리지 못한다.
        UniqueConstraint(
            "user_id",
            "endpoint",
            "idempotency_key",
            name="uq_credit_operations_user_endpoint_key",
        ),
        CheckConstraint(
            "status IN ('PROCESSING', 'SUCCEEDED', 'RELEASED', 'REJECTED')",
            name="ck_credit_operations_status",
        ),
        CheckConstraint("amount >= 0", name="ck_credit_operations_amount_non_negative"),
        Index("ix_credit_operations_user_id", "user_id"),
        # 만료된 예약을 찾는 복구 스캔용. 이미 종결된 행은 인덱스에 담지 않는다.
        Index(
            "ix_credit_operations_stale_lease",
            "lease_expires_at",
            postgresql_where=text("status = 'PROCESSING'"),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        UUIDType(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # 같은 키를 다른 body에 재사용했는지 판정하는 근거. 원문 대신 해시만 남긴다.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # 종결 전에는 아직 확정된 값이 없다는 뜻으로 NULL이다.
    credit_delta: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    fencing_token: Mapped[str] = mapped_column(UUIDType(), nullable=False)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 재생용 저장 결과. 성공/위기 응답 본문과 실패 사유를 그대로 담는다.
    response_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(postgresql.JSONB, "postgresql"), nullable=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CreditLedger(Base):
    """크레딧 입출금 장부 (credit_ledger).

    append-only로 취급한다. 갱신하거나 지우지 않고 반대 부호의 행을 덧붙인다.
    중복 차감·중복 환불·웰컴 재지급은 아래 partial UNIQUE 인덱스가 DB에서 막는다.
    """

    __tablename__ = "credit_ledger"
    __table_args__ = (
        # operation 하나당 DEBIT 1건, RELEASE 1건까지만. 늦은 응답과 복구가
        # 동시에 환불을 시도해도 둘 중 하나만 성사된다.
        Index(
            "uq_credit_ledger_operation_event",
            "operation_id",
            "event_type",
            unique=True,
            postgresql_where=text("operation_id IS NOT NULL"),
        ),
        # 사용자당 웰컴 1건. 동시 가입 경합에서도 두 번 지급되지 않는다.
        Index(
            "uq_credit_ledger_welcome_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("event_type = 'WELCOME'"),
        ),
    )

    id: Mapped[str] = mapped_column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUIDType(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 기존 행에는 없으므로 nullable이다. 새 경로는 항상 채운다.
    operation_id: Mapped[Optional[str]] = mapped_column(
        UUIDType(), ForeignKey("credit_operations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserConsent(Base):
    """이용약관, 개인정보처리방침 동의 및 연령 확인 이력 (user_consents, append-only)."""

    __tablename__ = "user_consents"
    __table_args__ = (
        Index("ix_user_consents_user_id_created_at", "user_id", text("created_at DESC")),
    )

    id: Mapped[str] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(UUIDType(), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    terms_version: Mapped[str] = mapped_column(Text, nullable=False)
    privacy_version: Mapped[str] = mapped_column(Text, nullable=False)
    age_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="GRANT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupportInquiry(Base):
    """고객지원 문의 접수 내역 (support_inquiries)."""

    __tablename__ = "support_inquiries"
    __table_args__ = (
        Index("ix_support_inquiries_created_at", text("created_at DESC")),
    )

    id: Mapped[str] = mapped_column(
        UUIDType(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    ticket_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(UUIDType(), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="RECEIVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LLMCostUsage(Base):
    """일일 및 월간 LLM 호출 비용 누적 및 호출 수 (llm_cost_usage, A02-R1)."""

    __tablename__ = "llm_cost_usage"

    period_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    period_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

