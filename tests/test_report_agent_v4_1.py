"""v4.1 Report Agent 및 정밀 고변점 계산 엔진 단위 테스트."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from agents.report import (
    _resolve_primary_source,
    determine_gobyeonjeom_rule,
    run_report_agent,
)
from schemas.counsel import EvidenceItem
from schemas.report import HexagramReportSchema


def test_determine_gobyeonjeom_rule_all_cases():
    # 0개 변효
    r0 = determine_gobyeonjeom_rule([], "지산겸", "지산겸")
    assert r0["changing_count"] == 0
    assert r0["target_line_idx"] == -1
    assert "본괘" in r0["target_focus"]

    # 1개 변효 (3효)
    r1 = determine_gobyeonjeom_rule([3], "지산겸", "지천태")
    assert r1["changing_count"] == 1
    assert r1["target_line_idx"] == 3

    # 2개 변효 (2효, 5효 -> 상층부 5효)
    r2 = determine_gobyeonjeom_rule([2, 5], "지산겸", "수천수")
    assert r2["changing_count"] == 2
    assert r2["target_line_idx"] == 5

    # 3개 변효 (1효 포함)
    r3_with_1 = determine_gobyeonjeom_rule([1, 4, 6], "지산겸", "수화기제")
    assert r3_with_1["changing_count"] == 3
    assert r3_with_1["target_line_idx"] == -1  # 본괘 괘사

    # 3개 변효 (1효 미포함)
    r3_no_1 = determine_gobyeonjeom_rule([2, 4, 6], "지산겸", "수화기제")
    assert r3_no_1["changing_count"] == 3
    assert r3_no_1["target_line_idx"] == -2  # 지괘 괘사

    # 4개 변효 (1,2,3,4 변효 -> 부동효 5, 6중 아래 5효)
    r4 = determine_gobyeonjeom_rule([1, 2, 3, 4], "지산겸", "수화기제")
    assert r4["changing_count"] == 4
    assert r4["target_line_idx"] == -3

    # 5개 변효 (1,2,3,4,5 변효 -> 유일 부동효 6효)
    r5 = determine_gobyeonjeom_rule([1, 2, 3, 4, 5], "지산겸", "수화기제")
    assert r5["changing_count"] == 5
    assert r5["target_line_idx"] == -4

    # 6개 변효
    r6_geon = determine_gobyeonjeom_rule([1, 2, 3, 4, 5, 6], "중천건", "중지곤")
    assert r6_geon["changing_count"] == 6
    assert "용구" in r6_geon["target_focus"]


@pytest.mark.parametrize(
    ("changing_lines", "expected_hex", "expected_line"),
    [
        ([], 15, None),
        ([3], 15, 3),
        ([2, 5], 15, 5),
        ([1, 4, 6], 15, None),
        ([2, 4, 6], 11, None),
        ([1, 2, 3, 4], 11, 5),
        ([1, 2, 3, 4, 5], 11, 6),
        ([1, 2, 3, 4, 5, 6], 11, None),
    ],
)
def test_primary_source_matches_gobyeonjeom(changing_lines, expected_hex, expected_line):
    rule = determine_gobyeonjeom_rule(changing_lines, "지산겸", "지천태")
    assert _resolve_primary_source(rule, 15, 11, changing_lines) == (expected_hex, expected_line)


@pytest.mark.parametrize(
    ("original_name", "transformed_name", "original_hex", "transformed_hex", "term"),
    [
        ("중천건", "중지곤", 1, 2, "용구"),
        ("중지곤", "중천건", 2, 1, "용육"),
    ],
)
def test_all_changing_geon_gon_reads_original_use_line(
    original_name, transformed_name, original_hex, transformed_hex, term
):
    changing_lines = [1, 2, 3, 4, 5, 6]
    rule = determine_gobyeonjeom_rule(changing_lines, original_name, transformed_name)
    assert term in rule["target_focus"]
    assert _resolve_primary_source(
        rule, original_hex, transformed_hex, changing_lines
    ) == (original_hex, 7)


@pytest.mark.asyncio
async def test_report_accepts_evidence_models_and_reads_transformed_line():
    llm = Mock()
    llm.complete_json.return_value = {
        "section1_diagnosis": "진단",
        "section2_action": "행동",
        "section3_warning": "경계",
        "section4_future": "변화",
        "final_summary": "요약",
    }
    meta = {
        "fullNameHangul": "테스트괘",
        "nameHanja": "試",
        "upperTrigram": "상괘",
        "lowerTrigram": "하괘",
        "natureSummary": "성질",
        "coreTheme": "주제",
    }
    evidence = EvidenceItem(
        source_type="line_comm",
        source_title="효사 주석(5효)",
        content="지괘의 핵심 근거",
        hexagram_id=11,
        line_number=5,
    )

    with (
        patch("agents.report._fetch_hex_meta", new=AsyncMock(return_value=meta)),
        patch("agents.report._fetch_line_hanja", new=AsyncMock(return_value="지괘 오효 원문")) as fetch_line,
        patch("agents.report._fetch_hex_statement_hanja", new=AsyncMock(return_value="지괘 괘사")),
        patch("agents.report.load_system_prompt", return_value="system"),
    ):
        report = await run_report_agent(
            None,
            question="명절 가족 갈등을 어떻게 풀까요?",
            original_hex_id=15,
            transformed_hex_id=11,
            changing_lines=[1, 2, 3, 4],
            lines_val=[6, 9, 6, 9, 8, 7],
            focus_rule={"target_line_numbers": [5]},
            evidences=[evidence],
            topic_category="가족/인간관계",
            client=llm,
            enable_refinement_loop=False,
        )

    fetch_line.assert_any_await(None, 11, 5)
    prompt = llm.complete_json.call_args.args[0]
    assert "Topic Category: 가족/인간관계" in prompt
    assert "지괘의 핵심 근거" in prompt
    assert report.section2_action.hanja_text == "지괘 오효 원문"


@pytest.mark.asyncio
async def test_incomplete_llm_report_is_not_disguised_as_custom_report():
    llm = Mock()
    llm.complete_json.return_value = {"section1_diagnosis": "진단만 있음"}
    meta = {
        "fullNameHangul": "테스트괘", "nameHanja": "試",
        "upperTrigram": "상괘", "lowerTrigram": "하괘",
        "natureSummary": "성질", "coreTheme": "주제",
    }
    with (
        patch("agents.report._fetch_hex_meta", new=AsyncMock(return_value=meta)),
        patch("agents.report._fetch_line_hanja", new=AsyncMock(return_value="원문")),
        patch("agents.report._fetch_hex_statement_hanja", new=AsyncMock(return_value="괘사")),
        patch("agents.report.load_system_prompt", return_value="system"),
    ):
        with pytest.raises(RuntimeError, match="맞춤 해석 리포트 생성에 실패"):
            await run_report_agent(
                None,
                question="가족 갈등을 어떻게 풀까요?",
                original_hex_id=15,
                transformed_hex_id=11,
                changing_lines=[3],
                lines_val=[7, 8, 9, 8, 8, 8],
                focus_rule={"target_line_numbers": [3]},
                evidences=[],
                client=llm,
                enable_refinement_loop=False,
            )
