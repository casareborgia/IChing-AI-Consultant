"""점괘 사전 분석 리포트 v2 계약.

v1(`schemas/report.py`)과의 차이는 화면 구성이 아니라 **무엇을 사실로 다루는가**다.

- 서버가 확정한 것(괘·초점 규칙·원문·번역·출처)과 모델이 쓴 서술을 분리한다.
  `academic_details.sources`에는 LLM이 채우는 칸이 하나도 없다.
- 사용자가 말하지 않은 것을 사실로 올리지 않는다. 공감(`validation`)은 실제 발화
  발췌(`user_fact_refs`)에 연결하고, 관찰된 적 없는 패턴은 `pattern_hypothesis`에
  가설로 남긴다. 정보가 없으면 `null`이다.
- 고전이 말하는 바(`classical_reading`)와 이번 사연에 적용한 해석
  (`applied_reading`)을 별개 칸으로 둔다. 한 칸에 섞으면 '利用獄 = 인지적 탈융합'처럼
  원전의 뜻이 현대 심리 용어로 **대체**된다.
- 지괘는 파국 예고가 아니라 점검할 조건(`conditions_to_check`)이다.

필드 이름에 치료 기법명(EFT·CBT·ACT…)을 쓰지 않는다. 기법명을 스키마에 박으면
모듈마다 그 기법을 수행하게 되고, 결국 어느 괘를 뽑아도 같은 틀로 수렴한다.
운영자 결정(2026-09-12)이며 배경은
`docs/commercialization/notes/claude/PRE_COUNSELING_REPORT_V2_PLAN.md` §3-1에 있다.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION = "2.0"

# 본문 칸의 상한. 넘치면 조용히 자르지 않고 검증 오류로 돌린다 — 자르면 문장이
# 중간에서 끊겨 뜻이 바뀌고, 그 상태로 `ready`가 되면 사용자는 잘린 줄 모른다.
_SHORT = 200
_MEDIUM = 500
_LONG = 800


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# 서버 확정 사실 — LLM이 채우는 칸이 없다
# ---------------------------------------------------------------------------


class SourceRole(str, Enum):
    """근거가 이번 판단에서 맡은 자리."""

    PRIMARY = "primary"          # 초점 규칙이 지목한 주 근거
    AUXILIARY = "auxiliary"      # 함께 보는 보조 근거
    BACKGROUND = "background"    # 배경 (효사가 주 근거일 때의 본괘 괘사)
    BODY_USE = "body_use"        # 체용 참작 — 근거를 고르지 않고 무게만 보탠다
    SUPPLEMENT = "supplement"    # 대상전 등 보충. 주 근거로 승격하지 않는다
    ANNOTATION = "annotation"    # 검색된 고전 주석 (정전·본의·소상전)


class ReportSource(_Base):
    """근거 한 건의 스냅샷.

    `locator`는 확인된 원전 위치만 담는다. 『역학계몽』의 편명·페이지를 추측해
    적지 않는다 — 저장소가 확인한 범위는 `data/PROVENANCE.md`에 있다.
    """

    id: str = Field(pattern=r"^E\d{1,3}$", description="이 리포트 안에서만 유효한 근거 ID")
    role: SourceRole
    hexagram_id: int = Field(ge=1, le=64)
    hexagram_name: str = Field(min_length=1, max_length=100)
    line_number: Optional[int] = Field(default=None, ge=1, le=7)
    classical_text: str = Field(min_length=1, max_length=2000, description="원문. 번역으로 대신하지 않는다")
    classical_translation: Optional[str] = Field(default=None, max_length=2000)
    annotation: Optional[str] = Field(default=None, max_length=4000, description="검색된 주석 본문 스냅샷")
    annotation_source: Optional[str] = Field(default=None, max_length=200)
    locator: Optional[str] = Field(default=None, max_length=200, description="확인된 원전 위치. 불명이면 null")

    @field_validator("classical_translation", "annotation", "annotation_source", "locator")
    @classmethod
    def _blank_is_null(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class UserFact(_Base):
    """사용자가 실제로 쓴 문장의 발췌. 서술이 사실이라고 주장할 수 있는 유일한 근거다."""

    id: str = Field(pattern=r"^U\d{1,3}$")
    text: str = Field(min_length=1, max_length=1000)


class CastingLine(_Base):
    position: int = Field(ge=1, le=6)
    value: int = Field(ge=6, le=9)
    line_type_ko: str = Field(min_length=1, max_length=20)
    is_changing: bool


class CastingDetail(_Base):
    lines: List[CastingLine] = Field(min_length=6, max_length=6)
    original_hexagram_id: int = Field(ge=1, le=64)
    original_name: str = Field(min_length=1, max_length=100)
    original_lower_trigram: str = Field(min_length=1, max_length=30)
    original_upper_trigram: str = Field(min_length=1, max_length=30)
    changing_lines: List[int] = Field(default_factory=list, max_length=6)
    has_transformation: bool
    # 불변괘에서는 본괘 ID를 되풀이하지 않고 null이다. 같은 괘를 '지괘'라고 부르면
    # 변화가 없다는 사실이 변화가 있는 것처럼 읽힌다.
    transformed_hexagram_id: Optional[int] = Field(default=None, ge=1, le=64)
    transformed_name: Optional[str] = Field(default=None, max_length=100)


class FocusRuleDetail(_Base):
    changing_count: int = Field(ge=0, le=6)
    focus_type: str = Field(min_length=1, max_length=40)
    target_hexagram_type: str = Field(min_length=1, max_length=20)
    target_line_numbers: List[int] = Field(default_factory=list, max_length=6)
    description_ko: str = Field(min_length=1, max_length=_MEDIUM)
    body_use_type: str = Field(min_length=1, max_length=40)
    body_use_note_ko: Optional[str] = Field(default=None, max_length=_MEDIUM)
    rule_version: str = Field(min_length=1, max_length=40)


class AcademicDetails(_Base):
    casting: CastingDetail
    focus_rule: FocusRuleDetail
    sources: List[ReportSource] = Field(min_length=1, max_length=30)
    user_facts: List[UserFact] = Field(default_factory=list, max_length=30)


# ---------------------------------------------------------------------------
# 서술 — 모델이 쓰고 서버가 검증한다
# ---------------------------------------------------------------------------


class EmotionalContext(_Base):
    """지금의 마음과 상황.

    `validation`은 사용자가 실제로 말한 것에 대한 공감이다. `pattern_hypothesis`는
    관찰된 적 없는 반복 패턴이라 **가설**로만 존재한다 — 없으면 `null`이고,
    있어도 상담에서 확인할 대상이지 확정 사실이 아니다.
    """

    validation: str = Field(min_length=10, max_length=_LONG)
    pattern_hypothesis: Optional[str] = Field(default=None, max_length=_MEDIUM)
    user_fact_refs: List[str] = Field(default_factory=list, max_length=10)

    @field_validator("pattern_hypothesis")
    @classmethod
    def _blank_is_null(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class Perspective(_Base):
    """다른 각도에서 살펴보기.

    `classical_reading`과 `applied_reading`이 갈라져 있는 것이 이 모델의 핵심이다.
    한 칸이면 "利用獄은 인지적 탈융합을 뜻합니다"가 나온다 — 원전의 뜻이 현대
    심리 용어로 대체된 것이고, 고전이 그렇게 말한 적은 없다. 두 칸이면
    "옥사를 다스린다는 것은 …"(고전)과 "이번 사연에 옮기면 …"(적용)이 각각 제 자리에
    선다.
    """

    thought_observation: Optional[str] = Field(default=None, max_length=_MEDIUM)
    classical_reading: str = Field(min_length=10, max_length=_MEDIUM)
    applied_reading: str = Field(min_length=10, max_length=_LONG)
    alternative_perspective: str = Field(min_length=10, max_length=_LONG)
    evidence_refs: List[str] = Field(min_length=1, max_length=10)

    @field_validator("thought_observation")
    @classmethod
    def _blank_is_null(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)


class ValueDirection(_Base):
    """지키고 싶은 가치와 점검할 조건.

    지괘가 들어오는 자리다. 확정적 미래나 파국 예고가 아니라 `conditions_to_check`
    — 선택할 때 무엇을 살펴볼지다.
    """

    proposed_value: Optional[str] = Field(default=None, max_length=_SHORT)
    rationale: str = Field(min_length=10, max_length=_LONG)
    conditions_to_check: List[str] = Field(min_length=1, max_length=5)
    evidence_refs: List[str] = Field(min_length=1, max_length=10)

    @field_validator("proposed_value")
    @classmethod
    def _blank_is_null(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)

    @field_validator("conditions_to_check")
    @classmethod
    def _no_blank_items(cls, items: List[str]) -> List[str]:
        cleaned = [i.strip() for i in items if i and i.strip()]
        if len(cleaned) != len(items):
            raise ValueError("빈 항목은 조건으로 세지 않습니다")
        for item in cleaned:
            if len(item) > _SHORT:
                raise ValueError(f"조건 항목이 {_SHORT}자를 넘습니다")
        return cleaned


class MicroActionTask(_Base):
    """오늘 시도해 볼 작은 행동.

    `duration_minutes`의 상한이 15인 것은 수행 가능성 때문이다. 10분은 기본 제안이지
    고정값이 아니다. 사용자의 생활 조건(퇴근 시각, 업무 알림 정책)을 모르면
    `when`에 특정 시각을 강제하지 않는다.

    **이 칸은 제안이다.** 사용자가 고른 적도 끝낸 적도 없다. 선택·완료는 별도
    상태로 관리한다(카드 C).
    """

    title: str = Field(min_length=2, max_length=100)
    duration_minutes: int = Field(ge=1, le=15)
    when: str = Field(min_length=2, max_length=_SHORT)
    steps: List[str] = Field(min_length=1, max_length=3)
    completion_criterion: str = Field(min_length=5, max_length=_SHORT)
    smaller_alternative: Optional[str] = Field(default=None, max_length=_SHORT)

    @field_validator("smaller_alternative")
    @classmethod
    def _blank_is_null(cls, v: Optional[str]) -> Optional[str]:
        return _strip_or_none(v)

    @field_validator("steps")
    @classmethod
    def _no_blank_steps(cls, items: List[str]) -> List[str]:
        cleaned = [i.strip() for i in items if i and i.strip()]
        if len(cleaned) != len(items):
            raise ValueError("빈 단계는 단계로 세지 않습니다")
        for item in cleaned:
            if len(item) > _SHORT:
                raise ValueError(f"단계가 {_SHORT}자를 넘습니다")
        return cleaned


class ReportNarrative(_Base):
    headline_metaphor: str = Field(min_length=5, max_length=_SHORT)
    emotional_context: EmotionalContext
    perspective: Perspective
    value_direction: ValueDirection
    micro_action_task: MicroActionTask


class CounselingHandoff(_Base):
    """다음 상담 턴으로 넘기는 것.

    무엇이 확인됐고 무엇이 아직 아닌지를 갈라 둔다. 이 구분이 없으면 리포트의
    잠정 해석이 다음 턴에서 확정 사실로 굳는다.

    카드 B에서는 생성·저장만 한다. 5턴 상담이 이 구조를 실제로 소비하는 것은
    카드 E다.
    """

    working_hypotheses: List[str] = Field(default_factory=list, max_length=5)
    unconfirmed_points: List[str] = Field(default_factory=list, max_length=5)
    suggested_action_title: str = Field(min_length=2, max_length=100)
    opening_question: str = Field(min_length=5, max_length=_SHORT)


class GenerationMetadata(_Base):
    """무엇으로 만들었는지. **지어내지 않는다.**

    클라이언트가 확인해 주지 않는 상세 모델 버전은 `null`로 둔다 — 모르는 것을
    적어 두면 나중에 그 값으로 재현을 시도하게 된다.
    """

    generated_at: str = Field(min_length=10, max_length=40, description="타임존 포함 ISO-8601")
    provider: Optional[str] = Field(default=None, max_length=60)
    model: Optional[str] = Field(default=None, max_length=120)
    prompt_version: str = Field(min_length=1, max_length=40)
    rule_version: str = Field(min_length=1, max_length=40)
    evidence_snapshot_hash: str = Field(min_length=8, max_length=64)
    repair_count: int = Field(ge=0, le=1)


class PreCounselingReport(_Base):
    """점괘 사전 분석 리포트 v2.

    본문은 **생성 시점의 스냅샷**이다. 사용자의 행동 선택·완료 같은 현재 상태를
    이 JSON 안에서 계속 덮어쓰지 않는다.
    """

    schema_version: str = Field(default=SCHEMA_VERSION, pattern=r"^2\.0$")
    report_id: str = Field(min_length=36, max_length=36)
    session_id: str = Field(min_length=1, max_length=64)
    narrative: ReportNarrative
    academic_details: AcademicDetails
    counseling_handoff: CounselingHandoff
    generation_metadata: GenerationMetadata


# 모델이 채우는 부분만 따로. 서버 확정값은 여기에 없다 — 모델이 괘 ID나 원문을
# 되돌려 보낼 수 있으면 그 값이 확정값을 덮어쓸 자리가 생긴다.
class NarrativeDraft(_Base):
    """LLM 출력 계약. `narrative` + `counseling_handoff`만 받는다."""

    narrative: ReportNarrative
    counseling_handoff: CounselingHandoff
