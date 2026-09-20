"""리포트 에이전트 동작 검증.

예전 이름은 `test_report_agent_v4_1.py`였고, 제거된 `determine_gobyeonjeom_rule()`의
반환 dict(`target_line_idx` −1/−2/−3/−4)를 그대로 기대값으로 삼고 있었다. 그 기대값은
공통 엔진과 어긋난 판단을 고정하는 것이라 함께 교체했다 — 특히 동효 3개를
`초효 포함 여부`로 가르는 기대와, 동효 4개의 보조 효를 본괘에서 가져오는 기대다.
근거 선택의 정오는 `tests/test_report_focus_rule_parity.py`가 4,096 조합으로 본다.

이 파일은 그 위에서 **리포트가 무엇을 조립해 내보내는가**를 본다. DB를 부르지 않는다.
"""

from unittest.mock import Mock, patch

import pytest

from agents.report import ReportEvidenceError, run_report_agent
from core.hexagram_engine import cast_hexagram
from schemas.counsel import EvidenceItem
from tests.test_report_focus_rule_parity import fake_hexagram, fake_reading


DRAFT = {
    "section1_diagnosis": "진단",
    "section2_action": "행동",
    "section3_warning": "경계",
    "section4_future": "변화",
    "final_summary": "요약",
}


def mock_llm(*responses):
    llm = Mock()
    llm.complete_json.side_effect = list(responses) or [DRAFT]
    return llm


def reading_for(values):
    return fake_reading(cast_hexagram(manual_lines=values))


async def run(reading, llm, *, evidences=(), **kwargs):
    with patch("agents.report.load_system_prompt", return_value="system"):
        return await run_report_agent(
            question="명절마다 부모님과 배우자 사이에서 갈등이 생깁니다.",
            reading=reading,
            evidences=list(evidences),
            topic_category="가족/인간관계",
            client=llm,
            enable_refinement_loop=False,
            **kwargs,
        )


@pytest.mark.asyncio
async def test_primary_source_follows_focus_rule_to_the_transformed_hexagram():
    """동효 4개면 초점은 지괘의 부동효에 있다. 인용 원문도 지괘의 것이어야 한다.

    예전에는 보조 효를 본괘 동효에서 가져와, 상담사가 말하는 괘와 리포트가 인용한
    원문이 서로 다른 괘였다.
    """
    reading = reading_for([9, 9, 9, 9, 8, 7])  # 동효 1~4, 부동효 5·6
    cast = reading.cast_result
    llm = mock_llm(DRAFT)

    report = await run(reading, llm)

    trans_id = cast.transformed_hexagram_id
    assert report.section2_action.hanja_text == f"LINE-{trans_id}-5"
    assert report.section3_warning.hanja_text == f"LINE-{trans_id}-6"
    assert f"LINE-{cast.original_hexagram_id}-" not in report.section2_action.hanja_text


@pytest.mark.asyncio
async def test_three_changing_lines_expose_both_judgments():
    """동효 3개는 본괘 괘사(주)와 지괘 괘사(보조)가 둘 다 실린다."""
    reading = reading_for([9, 8, 9, 8, 9, 8])
    cast = reading.cast_result
    llm = mock_llm(DRAFT)

    report = await run(reading, llm)

    assert report.section2_action.hanja_text == f"JUDGMENT-{cast.original_hexagram_id}"
    assert report.section3_warning.hanja_text == f"JUDGMENT-{cast.transformed_hexagram_id}"
    prompt = llm.complete_json.call_args.args[0]
    assert "(위주)" in prompt and "(참작)" in prompt


@pytest.mark.asyncio
async def test_all_rag_evidences_reach_the_prompt():
    """해석 에이전트가 출처별 몫으로 고른 근거를 리포트가 다시 자르지 않는다.

    예전에는 `limit=6`으로 잘랐다. 넘어오는 목록은 초점 효 3 · 괘 단위 3 · 지괘 2로
    이미 나뉜 최대 8건이라, 6건으로 자르면 우선순위가 가장 낮은 **지괘 주석이 통째로
    사라진다.** 초점 효 주석이 손에 없으면 모델은 괘 이름의 통념으로 물러나고,
    통념은 여러 괘가 공유하므로 어느 괘를 뽑아도 같은 말이 나온다.
    """
    reading = reading_for([9, 7, 7, 7, 7, 7])  # 동효 1개 — 초점은 본괘 1효
    cast = reading.cast_result
    orig, trans = cast.original_hexagram_id, cast.transformed_hexagram_id

    evidences = [
        EvidenceItem(source_type="line_comm", source_title=f"초점효-{i}",
                     content=f"FOCUS-{i}", hexagram_id=orig, line_number=1)
        for i in range(3)
    ] + [
        EvidenceItem(source_type="hex_comm", source_title=f"괘단위-{i}",
                     content=f"HEX-{i}", hexagram_id=orig, line_number=None)
        for i in range(3)
    ] + [
        EvidenceItem(source_type="hex_comm", source_title=f"지괘-{i}",
                     content=f"TRANS-{i}", hexagram_id=trans, line_number=None)
        for i in range(2)
    ]
    assert len(evidences) == 8

    llm = mock_llm(DRAFT)
    await run(reading, llm, evidences=evidences)

    prompt = llm.complete_json.call_args.args[0]
    for i in range(3):
        assert f"FOCUS-{i}" in prompt
        assert f"HEX-{i}" in prompt
    for i in range(2):
        assert f"TRANS-{i}" in prompt, "지괘 주석이 잘려 나갔습니다"


@pytest.mark.asyncio
async def test_focus_line_evidence_comes_first():
    """초점 효의 주석을 앞으로 당긴다 — 순서는 유지하되 버리지는 않는다."""
    reading = reading_for([9, 7, 7, 7, 7, 7])
    orig = reading.cast_result.original_hexagram_id
    evidences = [
        EvidenceItem(source_type="hex_comm", source_title="괘단위",
                     content="HEX-FIRST", hexagram_id=orig, line_number=None),
        EvidenceItem(source_type="line_comm", source_title="초점효",
                     content="FOCUS-LINE", hexagram_id=orig, line_number=1),
    ]
    llm = mock_llm(DRAFT)
    await run(reading, llm, evidences=evidences)

    prompt = llm.complete_json.call_args.args[0]
    assert prompt.index("FOCUS-LINE") < prompt.index("HEX-FIRST")


@pytest.mark.asyncio
async def test_trigrams_are_derived_not_placeholders():
    """상·하괘 이름 자리에 '상괘'라는 글자가 나가지 않는다.

    `hexagrams` 테이블에는 상·하괘 칼럼이 없다. 예전 코드의
    `getattr(hex_obj, "upper_trigram", "") or "상괘"`는 **항상** 기본값을 돌려줬다.
    """
    reading = reading_for([7, 8, 8, 7, 8, 7])  # 화뢰서합(21) — 하괘 진(우레), 상괘 리(불)
    assert reading.cast_result.original_hexagram_id == 21

    report = await run(reading, mock_llm(DRAFT))

    assert report.hexagram_casting.original_lower_trigram == "진(우레)"
    assert report.hexagram_casting.original_upper_trigram == "리(불)"


@pytest.mark.asyncio
async def test_casting_table_mirrors_the_actual_cast():
    """화면의 수리 표는 실제 뽑힌 6효다. 기본값으로 채우지 않는다."""
    values = [6, 7, 8, 9, 7, 8]
    reading = reading_for(values)

    report = await run(reading, mock_llm(DRAFT))

    assert [item.value for item in report.hexagram_casting.lines] == values
    assert [item.position for item in report.hexagram_casting.lines] == [1, 2, 3, 4, 5, 6]
    changing = [item.position for item in report.hexagram_casting.lines if item.is_changing]
    assert changing == reading.cast_result.changing_lines == [1, 4]


@pytest.mark.asyncio
async def test_mindset_rule_claims_nothing_about_the_user():
    """서버가 확인할 수 없는 사용자 마음가짐을 기록하지 않는다."""
    report = await run(reading_for([7, 8, 8, 7, 8, 7]), mock_llm(DRAFT))

    rule = report.question_setting.mindset_rule
    assert "무념무상" not in rule
    assert "경건" not in rule
    assert "재삼독" in rule, "서버가 실제로 보장하는 재뽑기 금지는 남는다"


@pytest.mark.asyncio
async def test_invariant_report_does_not_invent_a_transformed_flow():
    """불변괘에 지괘의 흐름을 말하지 않는다.

    예전에는 `trans_meta`가 `orig_meta`로 폴백해 "본괘(X)에서 지괘(X)로 나아가는
    흐름"이라고 썼다. 지괘가 없는 괘에 지괘를 말한 것이다.
    """
    reading = reading_for([7, 8, 8, 7, 8, 7])
    report = await run(reading, mock_llm(DRAFT))

    casting = report.hexagram_casting
    assert casting.has_transformation is False
    assert casting.transformed_hex_id is None
    assert casting.transformed_name_full is None
    assert "지괘가 없습니다" in report.focus_and_body_use.body_use_flow
    assert report.section4_future.hanja_text is None


@pytest.mark.asyncio
async def test_missing_source_text_is_an_evidence_error():
    """원문이 없으면 번역이나 LLM으로 메우지 않고 근거 오류로 끊는다."""
    reading = reading_for([7, 8, 8, 7, 8, 7])
    reading.original = fake_hexagram(21)
    reading.original.judgment_text = ""

    with pytest.raises(ReportEvidenceError, match="주 근거 원문이 없습니다"):
        await run(reading, mock_llm(DRAFT))


@pytest.mark.asyncio
async def test_inconsistent_cast_is_rejected_before_calling_the_model():
    """모순된 괘로는 LLM을 부르지 않는다 — 비용과 오답을 둘 다 막는다."""
    reading = reading_for([7, 8, 8, 7, 8, 7])
    reading.cast_result = reading.cast_result.model_copy(
        update={"original_hexagram_id": 1}
    )
    llm = mock_llm(DRAFT)

    with pytest.raises(ReportEvidenceError):
        await run(reading, llm)

    llm.complete_json.assert_not_called()


@pytest.mark.asyncio
async def test_incomplete_llm_report_is_not_disguised_as_custom_report():
    llm = mock_llm({"section1_diagnosis": "진단만 있음"})

    with pytest.raises(RuntimeError, match="맞춤 해석 리포트 생성에 실패"):
        await run(reading_for([7, 8, 9, 8, 8, 8]), llm)


@pytest.mark.asyncio
async def test_refinement_loop_disabled_makes_one_call():
    llm = mock_llm(DRAFT)
    await run(reading_for([7, 8, 8, 7, 8, 7]), llm)
    assert llm.complete_json.call_count == 1
