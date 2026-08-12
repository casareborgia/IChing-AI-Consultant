from typing import Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base


class InterpretationChunk(Base):
    """RAG 해설/주석/사례 벡터 저장소 (정신의학 자료 제외, 주석 및 현대 해설만 포함)"""
    __tablename__ = "interpretation_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hexagram_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("hexagrams.id", ondelete="SET NULL"), nullable=True, index=True)
    line_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 'annotation', 'modern_commentary', 'case_study'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # 768 차원 벡터 (예: Ollama/Gemma 또는 Vertex AI Embedding)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)
