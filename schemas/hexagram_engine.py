from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FocusType(str, Enum):
    """주자 점법 중점 해석 대상 유형"""
    ORIGINAL_JUDGMENT = "ORIGINAL_JUDGMENT"            # 본괘 괘사만 (동효 0개)
    SINGLE_LINE_STATEMENT = "SINGLE_LINE_STATEMENT"    # 본괘/지괘 단일 효사 (동효 1개, 5개)
    MULTIPLE_LINE_STATEMENTS = "MULTIPLE_LINE_STATEMENTS" # 본괘/지괘 복수 효사 (동효 2개, 4개)
    BOTH_JUDGMENTS = "BOTH_JUDGMENTS"                  # 본괘 괘사 + 지괘 괘사 (동효 3개)
    TRANSFORMED_JUDGMENT = "TRANSFORMED_JUDGMENT"      # 지괘 괘사만 (동효 6개 일반괘)
    SPECIAL_USE_LINE = "SPECIAL_USE_LINE"              # 건괘 용구 / 곤괘 용육 (동효 6개 특수)


class LineCastResult(BaseModel):
    """개별 효 산출 결과"""
    position: int = Field(..., ge=1, le=6, description="효 위치 (1: 초효 ~ 6: 상효)")
    value: int = Field(..., ge=6, le=9, description="효 수치 (6: 노음, 7: 소양, 8: 소음, 9: 노양)")
    original_bit: str = Field(..., description="본괘 효 비트 ('1': 양, '0': 음)")
    is_changing: bool = Field(..., description="동효(변효) 여부 (6 또는 9일 때 True)")
    transformed_bit: str = Field(..., description="지괘 효 비트 ('1': 양, '0': 음)")


class FocusRuleResult(BaseModel):
    """해석 포커스 판단 결과"""
    focus_type: FocusType = Field(..., description="주자 점법 해석 중심 유형")
    target_hexagram_type: str = Field(..., description="주 해석 대상 괘 ('ORIGINAL', 'TRANSFORMED', 'BOTH')")
    target_line_numbers: List[int] = Field(default_factory=list, description="주 해석 대상 효 번호 목록 (예: [1], [2, 5], [7] 용구/용육)")
    description_ko: str = Field(..., description="해석 지침 설명 (한글)")


class HexagramCastResult(BaseModel):
    """괘 도출 전체 결과"""
    original_hexagram_id: int = Field(..., ge=1, le=64, description="본괘 ID (1~64)")
    original_binary: str = Field(..., min_length=6, max_length=6, description="본괘 이진 코드 (예: '111111')")
    transformed_hexagram_id: Optional[int] = Field(None, ge=1, le=64, description="지괘 ID (1~64, 동효 없으면 None)")
    transformed_binary: Optional[str] = Field(None, min_length=6, max_length=6, description="지괘 이진 코드")
    changing_lines: List[int] = Field(default_factory=list, description="동효 위치 리스트 (예: [1, 4])")
    lines: List[LineCastResult] = Field(..., min_length=6, max_length=6, description="6개 효 산출 정보 (초효~상효)")
    focus_rule: FocusRuleResult = Field(..., description="해석 포커스 안내 결과")
