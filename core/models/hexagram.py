from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Hexagram(Base):
    __tablename__ = "hexagrams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    binary_code: Mapped[Optional[str]] = mapped_column(String(6), index=True, unique=True, nullable=True)  # e.g., "111111"
    symbol: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # e.g., "䷀" (유니코드 괘상)
    name_ko: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "건"
    name_hanja: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "乾"
    name_full: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "중천건"
    
    judgment_text: Mapped[str] = mapped_column(Text, nullable=False)  # 괘사 원문
    judgment_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 괘사 한글 번역
    tanjon_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 단전 원문
    xiang_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 대상전 원문
    wenyan_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 문언전 원문

    lines: Mapped[List["Line"]] = relationship("Line", back_populates="hexagram", cascade="all, delete-orphan")


class Line(Base):
    __tablename__ = "lines"
    __table_args__ = (
        UniqueConstraint("hexagram_id", "line_number", name="uq_line_hexagram_linenumber"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hexagram_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexagrams.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1~6효 및 7 (건/곤 용구/용육 포함)
    
    statement_text: Mapped[str] = mapped_column(Text, nullable=False)  # 효사 원문
    statement_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 효사 한글 번역
    small_xiang_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 소상전 원문

    hexagram: Mapped["Hexagram"] = relationship("Hexagram", back_populates="lines")
