"""v4.1 Report Agent 및 정밀 고변점 계산 엔진 단위 테스트."""

import pytest
from agents.report import determine_gobyeonjeom_rule, run_report_agent
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
    assert "용육" in r6_geon["target_focus"]


@pytest.mark.asyncio
async def test_run_report_agent_fallback_structure():
    from core.db import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        report = await run_report_agent(
            session,
            question="신규 사업 프로젝트를 조급하게 확장해야 하는가?",
            original_hex_id=15,
            transformed_hex_id=11,
            changing_lines=[3],
            lines_val=[7, 8, 9, 8, 8, 8],
            focus_rule={"target_line_numbers": [3], "description_ko": "3효 고변점"},
            evidences=[],
            enable_refinement_loop=False,
        )
        assert isinstance(report, HexagramReportSchema)
        assert report.hexagram_casting.original_hex_id == 15
        assert report.focus_and_body_use.changing_count == 1
        assert "①" in report.section1_diagnosis.title
        assert "②" in report.section2_action.title
