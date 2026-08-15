import itertools

import pytest
from core.hexagram_engine import (
    HEXAGRAM_BINARY_TO_ID,
    binary_to_hexagram_id,
    calculate_focus_rule,
    cast_hexagram,
    hexagram_id_to_binary,
    rebuild_cast,
)
from schemas.hexagram_engine import FocusType


def test_binary_mapping():
    """64괘 이진 코드 양방향 매핑 검증"""
    assert len(HEXAGRAM_BINARY_TO_ID) == 64
    assert binary_to_hexagram_id("111111") == 1   # 건괘
    assert binary_to_hexagram_id("000000") == 2   # 곤괘
    assert binary_to_hexagram_id("101010") == 63  # 기제괘
    assert binary_to_hexagram_id("010101") == 64  # 미제괘

    for hex_id in range(1, 65):
        binary = hexagram_id_to_binary(hex_id)
        assert len(binary) == 6
        assert binary_to_hexagram_id(binary) == hex_id


def test_cast_hexagram_manual_all_changing_qian_and_kun():
    """건괘 6동효 (용구) 및 곤괘 6동효 (용육) 수동 도출 검증"""
    # 건괘 6노양 -> 지괘 곤괘
    res_qian = cast_hexagram(manual_lines=[9, 9, 9, 9, 9, 9])
    assert res_qian.original_hexagram_id == 1
    assert res_qian.original_binary == "111111"
    assert res_qian.transformed_hexagram_id == 2
    assert res_qian.transformed_binary == "000000"
    assert res_qian.changing_lines == [1, 2, 3, 4, 5, 6]
    assert res_qian.focus_rule.focus_type == FocusType.SPECIAL_USE_LINE
    assert res_qian.focus_rule.target_line_numbers == [7]

    # 곤괘 6노음 -> 지괘 건괘
    res_kun = cast_hexagram(manual_lines=[6, 6, 6, 6, 6, 6])
    assert res_kun.original_hexagram_id == 2
    assert res_kun.original_binary == "000000"
    assert res_kun.transformed_hexagram_id == 1
    assert res_kun.transformed_binary == "111111"
    assert res_kun.changing_lines == [1, 2, 3, 4, 5, 6]
    assert res_kun.focus_rule.focus_type == FocusType.SPECIAL_USE_LINE
    assert res_kun.focus_rule.target_line_numbers == [7]


def test_cast_hexagram_manual_no_changing():
    """동효 0개 시 본괘사 중심 검증"""
    res = cast_hexagram(manual_lines=[7, 8, 7, 8, 7, 8])  # 기제괘 (101010 -> 63번)
    assert res.original_hexagram_id == 63
    assert res.transformed_hexagram_id is None
    assert res.changing_lines == []
    assert res.focus_rule.focus_type == FocusType.ORIGINAL_JUDGMENT
    assert res.focus_rule.target_hexagram_type == "ORIGINAL"



def test_focus_rules_0_to_6_lines():
    """동효 개수별(0~6개) 해석 포커스 규칙 정확성 검증"""
    # 0개
    rule0 = calculate_focus_rule(1, [])
    assert rule0.focus_type == FocusType.ORIGINAL_JUDGMENT
    assert rule0.target_hexagram_type == "ORIGINAL"

    # 1개 (초효 변효)
    rule1 = calculate_focus_rule(1, [1])
    assert rule1.focus_type == FocusType.SINGLE_LINE_STATEMENT
    assert rule1.target_hexagram_type == "ORIGINAL"
    assert rule1.target_line_numbers == [1]

    # 2개 (초효, 4효 변효) -> 상위 4효 우선
    rule2 = calculate_focus_rule(1, [1, 4])
    assert rule2.focus_type == FocusType.MULTIPLE_LINE_STATEMENTS
    assert rule2.target_hexagram_type == "ORIGINAL"
    assert rule2.target_line_numbers == [4, 1]

    # 3개 (1, 2, 3효 변효) -> 본괘/지괘 괘사 모두 참작
    rule3 = calculate_focus_rule(1, [1, 2, 3])
    assert rule3.focus_type == FocusType.BOTH_JUDGMENTS
    assert rule3.target_hexagram_type == "BOTH"

    # 4개 (1, 2, 3, 4효 변효) -> 지괘 안 변한 5, 6효 중 아래쪽(5효) 우선
    rule4 = calculate_focus_rule(1, [1, 2, 3, 4])
    assert rule4.focus_type == FocusType.MULTIPLE_LINE_STATEMENTS
    assert rule4.target_hexagram_type == "TRANSFORMED"
    assert rule4.target_line_numbers == [5, 6]

    # 5개 (1, 2, 3, 4, 5효 변효) -> 지괘 안 변한 6효
    rule5 = calculate_focus_rule(1, [1, 2, 3, 4, 5])
    assert rule5.focus_type == FocusType.SINGLE_LINE_STATEMENT
    assert rule5.target_hexagram_type == "TRANSFORMED"
    assert rule5.target_line_numbers == [6]

    # 6개 (일반 괘: 예를 들어 3번 준괘) -> 지괘 괘사만. 본괘 괘사를 함께 보는
    # 3변효(BOTH_JUDGMENTS)와 focus_type만으로 구분되어야 한다.
    rule6_general = calculate_focus_rule(3, [1, 2, 3, 4, 5, 6])
    assert rule6_general.focus_type == FocusType.TRANSFORMED_JUDGMENT
    assert rule6_general.target_hexagram_type == "TRANSFORMED"
    assert rule6_general.focus_type != rule3.focus_type


def test_cast_hexagram_random():
    """무작위 괘 산출 (동전점/시초점) 100회 난수 시뮬레이션"""
    for method in ["coin", "yarrow"]:
        for _ in range(50):
            res = cast_hexagram(method=method)
            assert 1 <= res.original_hexagram_id <= 64
            assert len(res.lines) == 6
            if res.changing_lines:
                assert res.transformed_hexagram_id is not None
                assert 1 <= res.transformed_hexagram_id <= 64
            else:
                assert res.transformed_hexagram_id is None


def test_rebuild_cast_왕복_전수():
    """본괘 ID와 동효만으로 원래 괘가 하나로 복원되는지 64괘 × 모든 동효 조합 전수 검증.

    상담이 여러 턴 이어져도 괘를 다시 뽑지 않으려면 이 복원이 정확해야 한다.
    """
    count = 0
    for hex_id in range(1, 65):
        for r in range(7):
            for combo in itertools.combinations(range(1, 7), r):
                rebuilt = rebuild_cast(hex_id, list(combo))
                assert rebuilt.original_hexagram_id == hex_id
                assert rebuilt.changing_lines == list(combo)
                # 같은 효 값으로 다시 뽑으면 지괘·포커스까지 동일해야 한다
                same = cast_hexagram(manual_lines=[l.value for l in rebuilt.lines])
                assert same.transformed_hexagram_id == rebuilt.transformed_hexagram_id
                assert same.focus_rule.focus_type == rebuilt.focus_rule.focus_type
                assert same.focus_rule.target_line_numbers == rebuilt.focus_rule.target_line_numbers
                count += 1
    assert count == 64 * 64  # 64괘 × 동효 조합 2^6


def test_rebuild_cast_잘못된_동효_위치():
    with pytest.raises(ValueError):
        rebuild_cast(1, [0])
    with pytest.raises(ValueError):
        rebuild_cast(1, [7])  # 7은 용구/용육 자리이지 동효 위치가 아니다
