"""[4] 괘해석 리포트 전용 Pydantic 스키마."""

from typing import List, Optional
from pydantic import BaseModel, Field


class QuestionSettingSchema(BaseModel):
    """1. 질문 및 마음가짐 세팅"""
    question: str = Field(description="질문자의 고민")
    mindset_rule: str = Field(description="재삼덕 금기 및 무념무상의 점서 예식 문구")


class LineCastingItem(BaseModel):
    """효 도출 항목"""
    position: int = Field(description="효 위치 (1~6)")
    name: str = Field(description="효 명칭 (예: 1효 (초효))")
    value: int = Field(description="수리값 (7, 8, 9, 6)")
    line_type_ko: str = Field(description="소양, 소음, 노양, 노음 명칭")
    symbol: str = Field(description="⚊ 또는 ⚋ 또는 ⚊○ 또는 ⚋✕")
    is_changing: bool = Field(description="동효 여부")
    note: str = Field(description="효 상태 설명")


class HexagramCastingSchema(BaseModel):
    """2. 괘 도출 과정"""
    lines: List[LineCastingItem] = Field(description="6효 수리 배열 목록 (초효~상효)")
    original_hex_id: int = Field(description="본괘 ID")
    original_name_full: str = Field(description="본괘 풀네임 (예: 제49괘 택화혁)")
    original_name_hanja: str = Field(description="본괘 한자명")
    original_upper_trigram: str = Field(description="상괘 명칭")
    original_lower_trigram: str = Field(description="하괘 명칭")
    original_summary: str = Field(description="본괘 핵심 상징 의미")
    
    has_transformation: bool = Field(description="변효 발생 여부")
    transformed_hex_id: Optional[int] = Field(None, description="지괘 ID")
    transformed_name_full: Optional[str] = Field(None, description="지괘 풀네임")
    transformed_name_hanja: Optional[str] = Field(None, description="지괘 한자명")
    transformed_summary: Optional[str] = Field(None, description="지괘 핵심 상징 의미")


class FocusAndBodyUseSchema(BaseModel):
    """3. 고변점 및 체용 해석 규칙"""
    changing_count: int = Field(description="동효 개수")
    rule_description: str = Field(description="주자 고변점 규칙 적용 내역 (예: 동효가 2개일 때 상층부 5효 채택)")
    primary_target_name: str = Field(description="주요 해석 대상 명칭 (예: 택화혁 괘 구오 효사)")
    body_use_flow: str = Field(description="체(體, 본괘 대전제)와 용(用, 지괘 지향점)의 흐름 설명")


class SectionItemSchema(BaseModel):
    """4. 괘사·효사 종합 해석 세부 섹션"""
    title: str = Field(description="섹션 제목 (예: ① 현재 상황 진단 (본괘: 택화혁))")
    target_name: str = Field(description="해석 대상 명칭")
    hanja_text: Optional[str] = Field(None, description="한문 효사/괘사 원문 (예: 大人虎變 未占有孚)")
    interpretation: str = Field(description="현대적 실질 사연 맞춤 해석 조언")


class HexagramReportSchema(BaseModel):
    """수석 주역 AI 컨설팅 통합 보고서 스키마"""
    question_setting: QuestionSettingSchema
    hexagram_casting: HexagramCastingSchema
    focus_and_body_use: FocusAndBodyUseSchema
    
    section1_diagnosis: SectionItemSchema = Field(description="① 현재 상황 진단 (본괘)")
    section2_action: SectionItemSchema = Field(description="② 핵심 행동 지침 (주 주요 해석 대상 + 한문 원문)")
    section3_warning: SectionItemSchema = Field(description="③ 보조 경계 지침 (함께 동한 효사 + 한문 원문)")
    section4_future: SectionItemSchema = Field(description="④ 미래의 귀결 및 주의점 (지괘 대상전/괘사 + 한문 원문)")
    
    final_summary: str = Field(description="💡 질문자에 대한 최종 종합 컨설팅 요약")
