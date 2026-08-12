from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class Hexagram(Base):
    __tablename__ = "hexagrams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    binary_code: Mapped[str] = mapped_column(String(6), index=True, nullable=False)
    name_ko: Mapped[str] = mapped_column(String(50), nullable=False)
    name_hanja: Mapped[str] = mapped_column(String(50), nullable=False)
    name_full: Mapped[str] = mapped_column(String(100), nullable=False)
    
    judgment_text: Mapped[str] = mapped_column(Text, nullable=False)  # 괘사 원문
    judgment_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 괘사 한글 번역
    tanjon_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 단전 원문
    xiang_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 대상전 원문
    wenyan_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 문언전 원문

    lines: Mapped[List["Line"]] = relationship("Line", back_populates="hexagram", cascade="all, delete-orphan")


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hexagram_id: Mapped[int] = mapped_column(Integer, ForeignKey("hexagrams.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1~6효 (초효~상효)
    
    statement_text: Mapped[str] = mapped_column(Text, nullable=False)  # 효사 원문
    statement_ko: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 효사 한글 번역
    small_xiang_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 소상전 원문

    hexagram: Mapped["Hexagram"] = relationship("Hexagram", back_populates="lines")
