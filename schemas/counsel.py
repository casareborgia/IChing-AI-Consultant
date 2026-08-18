from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SafetyVerdict(BaseModel):
    """[0] 안전 스크리닝 에이전트 출력 스키마

    ERROR는 모델이 내리는 판정이 아니라 스크리닝 자체가 실패했다는 내부 상태다.
    실패를 다섯 판정 중 하나로 뭉개면 통신 장애가 엉뚱한 안내로 나간다 —
    진로 상담하러 온 사람이 의료·법률 전문가를 찾아가라는 답을 받는 식으로.
    """
    category: Literal["BLOCK_CRISIS", "BLOCK_SCOPE", "ASK", "CAUTION", "NORMAL", "ERROR"] = Field(
        ..., description="안전 분류 카테고리 (ERROR는 스크리닝 실패를 뜻하는 내부 상태)"
    )
    ask: Optional[str] = Field(None, description="ASK 판정 시 사용자에게 되물을 명확화 질문")
    context: Optional[Literal["minor", "violence"]] = Field(
        None,
        description="BLOCK_CRISIS일 때 어느 연락처를 위에 놓을지. 판정에는 영향을 주지 않는다",
    )
    signals: List[str] = Field(default_factory=list, description="감지된 위험/주의 키워드 또는 신호")
    reason: str = Field("", description="판정 이유 및 근거")


class IntakeOutput(BaseModel):
    """[1] 정리 에이전트 출력 스키마"""

    request_type: Literal["counsel", "question"] = Field(
        "counsel",
        description="counsel이면 괘를 뽑아 상담한다. question이면 주역 자체에 대한 물음이라 괘를 뽑지 않는다",
    )
    clarified_question: str = Field(..., description="명확하게 재구성된 고민 내용")
    topic_category: str = Field(..., description="고민의 주제 카테고리 (예: 관계, 커리어, 결단 등)")
    is_duplicate_question: bool = Field(False, description="중복 질의(재삼독) 여부")
    duplicate_session_ref: Optional[str] = Field(None, description="중복 질의 시 이전 세션 ID 참조")


class EvidenceItem(BaseModel):
    """답변을 만드는 데 실제로 쓰인 주석 한 건.

    화면의 근거 패널이 이 값을 그대로 받는다. 예전에는 프론트엔드가 정적 표에서
    "정전(程傳) 및 본의(本義) 주석"이라는 제목을 달아 문장을 조립해 보여줬다 —
    정전을 한 번도 거치지 않은 문장이었다. 근거 투명성이 이 앱의 차별점인데
    화면에 나가는 근거가 지어낸 것이면 그 차별점은 없는 것만 못하다.

    그래서 **프롬프트에 실제로 들어간 청크만** 담는다. 검색은 했지만 몫에 밀려
    프롬프트에 못 들어간 청크는 답변에 영향을 주지 않았으므로 근거가 아니다.
    """

    source_type: str = Field(..., description="내부 출처 코드 (예: line_comm, benui_guasa)")
    source_title: str = Field(..., description="사람이 읽는 출처 이름 (예: 효사 주석(2효))")
    content: str = Field(..., description="주석 한글 번역. 한문은 내보내지 않는다")
    hexagram_id: int = Field(..., description="이 주석이 붙은 괘")
    line_number: Optional[int] = Field(None, description="효 단위 주석이면 효 번호")


class HexagramInterpretationSchema(BaseModel):
    """[2] 괘 해석 에이전트 출력 스키마"""
    original_hexagram_id: int = Field(..., description="본괘 ID (1~64)")
    transformed_hexagram_id: Optional[int] = Field(None, description="지괘 ID (1~64)")
    changing_lines: List[int] = Field(default_factory=list, description="변효 위치 리스트 (예: [1, 4])")
    raw_text: str = Field(..., description="DB 조회로 확정된 괘사/효사 원문 및 해석 가이드")
    contextual_mapping: str = Field(..., description="사용자의 고민 상황과 괘상의 연결 초안")
    evidences: List[EvidenceItem] = Field(
        default_factory=list,
        description="해석 초안을 만들 때 프롬프트에 실제로 들어간 주석",
    )


class CounselTurnSchema(BaseModel):
    """[3] 상담 에이전트 대화 턴 스키마"""
    message: str = Field(..., description="사용자에게 전달할 감응형 상담 답변")
    needs_followup: bool = Field(True, description="추가 대화/되묻기가 필요한지 여부 (루프 연장)")
    followup_question: Optional[str] = Field(None, description="사용자의 깊은 성찰을 끌어내기 위한 되묻기 질문")
    is_final: bool = Field(False, description="상담 세션이 종료되었는지 여부 (저널 에이전트로 핸드오프)")
    evidences: List[EvidenceItem] = Field(
        default_factory=list,
        description="이 턴에 다시 찾아 프롬프트에 붙인 주석 (재검색이 없었으면 빈 목록)",
    )


class JournalEntrySchema(BaseModel):
    """[+1] 저널 에이전트 요약 스키마"""
    summary: str = Field(..., description="상담 세션 전체 내용 요약")
    key_insights: str = Field(..., description="주역 괘상과 대화를 통해 얻은 핵심 성찰")
    action_items: Optional[str] = Field(None, description="향후 고민해볼 점 또는 실천해볼 방향")
