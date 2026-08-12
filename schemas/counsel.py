from typing import Optional, List
from pydantic import BaseModel, Field


class IntakeOutput(BaseModel):
    """[1] 정리 에이전트 출력 스키마"""
    clarified_question: str = Field(..., description="명확하게 재구성된 고민 내용")
    topic_category: str = Field(..., description="고민의 주제 카테고리 (예: 관계, 커리어, 결단 등)")
    is_duplicate_question: bool = Field(False, description="중복 질의(재삼독) 여부")
    duplicate_session_ref: Optional[str] = Field(None, description="중복 질의 시 이전 세션 ID 참조")


class HexagramInterpretationSchema(BaseModel):
    """[2] 괘 해석 에이전트 출력 스키마"""
    original_hexagram_id: int = Field(..., description="본괘 ID (1~64)")
    transformed_hexagram_id: Optional[int] = Field(None, description="지괘 ID (1~64)")
    changing_lines: List[int] = Field(default_factory=list, description="변효 위치 리스트 (예: [1, 4])")
    raw_text: str = Field(..., description="DB 조회로 확정된 괘사/효사 원문 및 해석 가이드")
    contextual_mapping: str = Field(..., description="사용자의 고민 상황과 괘상의 연결 초안")


class CounselTurnSchema(BaseModel):
    """[3] 상담 에이전트 대화 턴 스키마"""
    message: str = Field(..., description="사용자에게 전달할 감응형 상담 답변")
    needs_followup: bool = Field(True, description="추가 대화/되묻기가 필요한지 여부 (루프 연장)")
    followup_question: Optional[str] = Field(None, description="사용자의 깊은 성찰을 끌어내기 위한 되묻기 질문")
    is_final: bool = Field(False, description="상담 세션이 종료되었는지 여부 (저널 에이전트로 핸드오프)")


class JournalEntrySchema(BaseModel):
    """[+1] 저널 에이전트 요약 스키마"""
    summary: str = Field(..., description="상담 세션 전체 내용 요약")
    key_insights: str = Field(..., description="주역 괘상과 대화를 통해 얻은 핵심 성찰")
    action_items: Optional[str] = Field(None, description="향후 고민해볼 점 또는 실천해볼 방향")
