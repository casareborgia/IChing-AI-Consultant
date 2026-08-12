import pytest
from schemas.counsel import (
    IntakeOutput,
    HexagramInterpretationSchema,
    CounselTurnSchema,
    JournalEntrySchema,
)
from core.models.hexagram import Hexagram, Line
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from core.models.rag import InterpretationChunk


def test_pydantic_schemas_instantiation():
    # IntakeOutput 테스트
    intake = IntakeOutput(
        clarified_question="이직을 생각 중인데 지금이 좋은 시기인가요?",
        topic_category="커리어",
        is_duplicate_question=False,
    )
    assert intake.clarified_question == "이직을 생각 중인데 지금이 좋은 시기인가요?"
    assert intake.topic_category == "커리어"
    assert intake.is_duplicate_question is False

    # HexagramInterpretationSchema 테스트
    hex_interp = HexagramInterpretationSchema(
        original_hexagram_id=1,
        transformed_hexagram_id=44,
        changing_lines=[1],
        raw_text="건(乾): 원형이정",
        contextual_mapping="새로운 시작을 도모할 때입니다.",
    )
    assert hex_interp.original_hexagram_id == 1
    assert hex_interp.changing_lines == [1]

    # CounselTurnSchema 테스트
    turn = CounselTurnSchema(
        message="현재 상황에서 나아갈 길에 대해 생각해봅시다.",
        needs_followup=True,
        followup_question="어떤 준비를 하고 계신가요?",
    )
    assert turn.needs_followup is True
    assert turn.is_final is False

    # JournalEntrySchema 테스트
    journal = JournalEntrySchema(
        summary="이직 관련 상담 세션",
        key_insights="성급한 결정보다는 내실을 다질 때임.",
    )
    assert journal.summary == "이직 관련 상담 세션"


def test_orm_models_instantiation():
    hexagram = Hexagram(
        id=1,
        binary_code="111111",
        symbol="䷀",
        name_ko="건",
        name_hanja="乾",
        name_full="중천건",
        judgment_text="乾：元，亨，利，貞。",
    )
    assert hexagram.id == 1
    assert hexagram.name_ko == "건"
    assert hexagram.symbol == "䷀"

    line = Line(
        hexagram_id=1,
        line_number=7,  # 用九 (7번째 행)
        statement_text="用九：見群龍无首，吉。",
    )
    assert line.line_number == 7
    assert line.hexagram_id == 1

    session = CounselSession(
        raw_question="진로에 대해 고민이 있습니다.",
        clarified_question="진로 변경에 적합한 타이밍인가요?",
        status="active",
    )
    assert session.status == "active"
    assert session.raw_question == "진로에 대해 고민이 있습니다."

    chunk = InterpretationChunk(
        hexagram_id=1,
        category="modern_commentary",
        content="건괘는 창조성과 강건함을 나타냅니다.",
    )
    assert chunk.category == "modern_commentary"
