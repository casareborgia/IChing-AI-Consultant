"""Google ADK 표준 도구 (Tools) 모듈.

주역 괘 산출, DB 원문 조회, pgvector RAG 주석 검색, 과거 세션 이력 조회를
ADK 호환 Tool 함수로 정의합니다.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.hexagram_engine import HexagramCastResult
from core.hexagram_engine import cast_hexagram, rebuild_cast
from core.reading import ReadingEvidence, build_evidence
from core.rag import RetrievedChunk, search_balanced
from agents.pipeline import _get_past_sessions


async def cast_hexagram_tool(
    method: str = "coin",
    manual_lines: Optional[List[int]] = None,
) -> HexagramCastResult:
    """주역 괘를 산출하는 규칙 엔진 도구.
    
    Args:
        method: 산출 방식 ("coin" | "yarrow")
        manual_lines: 수동 지정 효 리스트 (선택 사항)
    
    Returns:
        HexagramCastResult 객체 (본괘, 지괘, 동효, 초점효 판정 결과)
    """
    return cast_hexagram(method=method, manual_lines=manual_lines)


async def lookup_hexagram_text_tool(
    session: AsyncSession,
    cast_result: HexagramCastResult,
) -> ReadingEvidence:
    """도출된 괘에 대해 DB에서 괘사/효사 확정 원문 및 번역을 조회하는 도구.
    
    Args:
        session: DB 비동기 세션
        cast_result: 괘 산출 결과
        
    Returns:
        ReadingEvidence 객체 (본괘/지괘/초점효의 확정 텍스트)
    """
    return await build_evidence(session, cast_result)


async def search_iching_commentaries_tool(
    session: AsyncSession,
    query: str,
    hexagram_id: int,
    line_number: Optional[int] = None,
    k_jeongjeon: int = 3,
    k_benui: int = 2,
) -> List[RetrievedChunk]:
    """pgvector를 통해 정전(伊川易傳) 및 본의(周易本義) 주석을 균형 검색하는 RAG 도구.
    
    Args:
        session: DB 비동기 세션
        query: 검색할 내담자의 질문 또는 맥락 질의
        hexagram_id: 괘 ID (1~64)
        line_number: 특정 효 번호 (1~6, 선택 사항)
        k_jeongjeon: 정전 주석 최대 검색 개수
        k_benui: 본의 주석 최대 검색 개수
        
    Returns:
        검색된 RetrievedChunk 리스트
    """
    return await search_balanced(
        session,
        query,
        hexagram_id=hexagram_id,
        line_number=line_number,
        k_jeongjeon=k_jeongjeon,
        k_benui=k_benui,
    )


async def lookup_past_sessions_tool(
    session: AsyncSession,
    user_id: Optional[str],
    limit: int = 10,
    exclude_session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """사용자의 최근 상담 이력과 저널 요약을 조회하는 도구 (재삼독 감지용).
    
    Args:
        session: DB 비동기 세션
        user_id: 사용자 고유 식별자
        limit: 조회할 세션 수
        exclude_session_id: 현재 세션 ID (제외 대상)
        
    Returns:
        과거 세션 정보 목록 (session_id, clarified_question, summary)
    """
    return await _get_past_sessions(
        session,
        user_id=user_id,
        limit=limit,
        exclude_session_id=exclude_session_id,
    )
