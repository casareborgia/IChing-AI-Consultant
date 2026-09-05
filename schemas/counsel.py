from typing import Any, Dict, List, Literal, Optional
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
    lines_val: Optional[List[int]] = Field(default_factory=list, description="6효 수리 배열 (예: [7, 8, 9, 8, 9, 7])")
    raw_text: str = Field(..., description="DB 조회로 확정된 괘사/효사 원문 및 해석 가이드")

    # 매핑을 쓰기 전에 거쳐야 하는 칸들.
    #
    # 자유 서술 한 칸만 두면 모델은 어느 괘에나 맞는 문장("지금은 멈추어 성찰할 때입니다")을
    # 쓴다. 그런 문장은 괘를 바꿔도 그대로라 다리 역할을 못 한다. 칸을 나눠 두면 효사를
    # 보지 않고는 채울 수 없다 — 특히 `only_this_line`이 그렇다.
    #
    # 채울 수 없으면 빈 문자열이다. 지어내는 것보다 비우는 편이 낫다.
    focus_image: str = Field("", description="초점 효사가 그리는 장면. 효사에 실제로 있는 것만")
    image_position: str = Field("", description="그 장면 안에서 내담자가 서 있는 자리")
    only_this_line: str = Field("", description="이 효가 말하는 것 중 괘 이름의 통념으로는 나오지 않는 것")

    contextual_mapping: str = Field(..., description="위 칸들을 딛고 쓴 상황 연결 초안")
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


class ActionCommitmentCardSchema(BaseModel):
    """[+1] ACT 기반 마음 전념 카드 페이로드 스키마"""
    is_crisis: bool = Field(False, description="위기 여부 (항상 False)")
    universe_transition: str = Field(..., description="괘의 전이 및 흐름 요약")
    sacred_metaphor: str = Field(..., description="고전의 은유적 한 구절")
    client_aha_moment: str = Field(..., description="내려놓을 아집이나 정서적 고착 상태")
    client_action_pledge: str = Field(..., description="10분 이내 실행 가능한 SMART 전념 행동")
    is_smart_compliant: bool = Field(True, description="SMART 기준 부합 여부")
    counselor_reframing: str = Field(..., description="마음의 지지와 격려가 담긴 1문장 리프레이밍")


class SPICardPayloadSchema(BaseModel):
    """[+1] Stanley-Brown 안전계획(SPI) 긴급 안심 카드 페이로드 스키마"""
    is_crisis: bool = Field(True, description="위기 여부 (항상 True)")
    crisis_warning_signs: str = Field(..., description="내담자가 보인 위험 신호 요약")
    inner_coping_strategies: List[str] = Field(..., description="내적 대처 방법 리스트 (호흡, 감각접지 등)")
    external_contacts_advice: str = Field(..., description="신뢰할 수 있는 친구/가족 연락 지침")
    emergency_professional_agencies: List[str] = Field(..., description="24시간 위기 전문기관 리스트")
    safe_environment_steps: List[str] = Field(..., description="물리적 공간 위험요소 제거 등 안전 확보 수칙")


class JournalEntrySchema(BaseModel):
    """[+1] 저널 에이전트 요약 스키마 (v2 행동 전념 카드 호환)"""
    summary: str = Field(..., description="상담 세션 전체 내용 요약")
    key_insights: str = Field(..., description="주역 괘상과 대화를 통해 얻은 핵심 성찰")
    action_items: Optional[str] = Field(None, description="향후 고민해볼 점 또는 실천해볼 방향")
    card_data: Optional[Dict[str, Any]] = Field(None, description="고도화된 행동 전념 카드 또는 SPI 안전계획 카드 페이로드")
    card_markdown: Optional[str] = Field(None, description="카드 인앱 뷰어 렌더링용 마크다운")
    is_crisis: Optional[bool] = Field(False, description="위기 상황(자살/자해) 감지 및 SPI 발동 여부")

