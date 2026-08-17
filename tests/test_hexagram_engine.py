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
from schemas.hexagram_engine import BodyUseType, FocusType


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

    # 3개 (1, 2, 3효 변효 — 초효 포함) -> 주희 고변점: 본괘 괘사 주 해석
    rule3_with_1 = calculate_focus_rule(1, [1, 2, 3])
    assert rule3_with_1.focus_type == FocusType.ORIGINAL_JUDGMENT
    assert rule3_with_1.target_hexagram_type == "ORIGINAL"

    # 3개 (2, 3, 4효 변효 — 초효 미포함) -> 주희 고변점: 지괘 괘사 주 해석
    rule3_without_1 = calculate_focus_rule(1, [2, 3, 4])
    assert rule3_without_1.focus_type == FocusType.TRANSFORMED_JUDGMENT
    assert rule3_without_1.target_hexagram_type == "TRANSFORMED"

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

    # 6개 (일반 괘: 예를 들어 3번 준괘) -> 지괘 괘사
    rule6_general = calculate_focus_rule(3, [1, 2, 3, 4, 5, 6])
    assert rule6_general.focus_type == FocusType.TRANSFORMED_JUDGMENT
    assert rule6_general.target_hexagram_type == "TRANSFORMED"


def test_body_use_rules():
    """지괘 18괘 체용(體用) 보완 규칙 판정 검증"""
    # 1. 한계/쇠퇴성 9괘 (예: 12 비, 53 점, 64 미제) -> EMPHASIZE_ORIGINAL
    rule_orig = calculate_focus_rule(1, [1], transformed_hex_id=12)
    assert rule_orig.body_use_type == BodyUseType.EMPHASIZE_ORIGINAL
    assert rule_orig.body_use_note_ko is not None
    assert "본괘(體)" in rule_orig.body_use_note_ko

    # 2. 성장/완결성 9괘 (예: 42 익, 21 서합, 11 태) -> EMPHASIZE_TRANSFORMED
    rule_trans = calculate_focus_rule(1, [1], transformed_hex_id=42)
    assert rule_trans.body_use_type == BodyUseType.EMPHASIZE_TRANSFORMED
    assert rule_trans.body_use_note_ko is not None
    assert "지괘(用)" in rule_trans.body_use_note_ko

    # 3. 일반 46괘 (예: 1 건, 2 곤) -> STANDARD
    rule_std = calculate_focus_rule(1, [1], transformed_hex_id=1)
    assert rule_std.body_use_type == BodyUseType.STANDARD
    assert rule_std.body_use_note_ko is None

    # 4. 지괘 없음 (동효 0개) -> STANDARD
    rule_none = calculate_focus_rule(1, [], transformed_hex_id=None)
    assert rule_none.body_use_type == BodyUseType.STANDARD
    assert rule_none.body_use_note_ko is None


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


def test_체용은_초점을_뒤집지_않는다():
    """초점 규칙과 체용 규칙은 같은 층이 아니다.

    초점(고변점)이 어느 근거를 꺼낼지 정하고, 체용은 그 근거를 어느 쪽으로
    기울여 읽을지만 보탠다. 둘은 4,032 조합 중 567개(14%)에서 서로 다른 괘를
    가리키므로, 어긋날 때 무엇이 이기는지가 문구에 드러나야 한다.

    예전에는 두 문구가 대등하게 나란히 붙어 "본괘의 괘사를 주 해석으로 삼습니다"와
    "지괘를 중심으로 무게를 둡니다"가 동시에 나갔다.
    """
    from itertools import combinations

    from core.hexagram_engine import (
        BODY_USE_SUBORDINATE_PREFIX,
        HEXAGRAM_ID_TO_BINARY,
        cast_hexagram,
    )

    검사 = 어긋남 = 같은방향 = 0
    for hid, binary in HEXAGRAM_ID_TO_BINARY.items():
        for n in range(1, 7):
            for lines in combinations(range(1, 7), n):
                vals = [
                    (9 if binary[p - 1] == "1" else 6) if p in lines
                    else (7 if binary[p - 1] == "1" else 8)
                    for p in range(1, 7)
                ]
                fr = cast_hexagram(manual_lines=vals).focus_rule
                if fr.body_use_type == BodyUseType.STANDARD:
                    assert fr.body_use_note_ko is None
                    continue

                검사 += 1
                note = fr.body_use_note_ko
                assert note, "체용 판정이 났는데 문구가 없다"

                강조 = ("ORIGINAL" if fr.body_use_type == BodyUseType.EMPHASIZE_ORIGINAL
                        else "TRANSFORMED")
                if fr.target_hexagram_type in (강조, "BOTH"):
                    같은방향 += 1
                    assert "같은 방향" in note
                    assert BODY_USE_SUBORDINATE_PREFIX not in note
                else:
                    어긋남 += 1
                    # 어긋날 때는 근거가 초점을 따른다고 문구가 먼저 밝힌다
                    assert note.startswith(BODY_USE_SUBORDINATE_PREFIX), note
                    # "~를 중심으로"처럼 초점을 밀어내는 표현이 없어야 한다
                    assert "중심으로" not in note, note

    assert 어긋남 == 567, f"어긋나는 조합 수가 달라졌다: {어긋남}"
    assert 같은방향 > 0 and 검사 == 어긋남 + 같은방향


def test_체용_판정은_지괘만_보고_초점_계산과_독립이다():
    """같은 지괘면 동효 수가 달라도 체용 판정은 같다."""
    for lines in ([1], [1, 2], [1, 2, 3], [2, 3, 4]):
        rule = calculate_focus_rule(1, lines, transformed_hex_id=12)
        assert rule.body_use_type == BodyUseType.EMPHASIZE_ORIGINAL

    # 지괘를 안 넘기면 체용은 서지 않는다 — 부르는 쪽이 빠뜨리면 조용히 STANDARD다
    누락 = calculate_focus_rule(1, [1])
    assert 누락.body_use_type == BodyUseType.STANDARD
    assert 누락.body_use_note_ko is None
