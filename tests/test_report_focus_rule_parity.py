"""리포트가 공통 엔진과 같은 근거를 고르는지 — 4,096 조합 전수 대조.

리포트에는 한때 `determine_gobyeonjeom_rule()`이라는 두 번째 점법 엔진이 있었고,
공통 엔진과 판단이 갈렸다(동효 3개·4개·6개). 그 함수는 제거했다. 이 테스트는
**제거가 유지되는지**를 지킨다.

DB도 LLM도 부르지 않는다. 효 수치 6·7·8·9의 전체 조합 4^6 = 4,096건을 순수 계산으로
돌린다. DB 원문 조회의 정확성은 `tests/test_reading_evidence.py`가 대표 fixture로 본다.

`core/hexagram_engine.py` 주석의 **4,032**는 다른 수를 센 것이다 — 지괘가 존재하는
조합(4,096 − 불변괘 64)이며, 체용 규칙이 초점과 어긋나는 자리를 셀 때 쓴 모수다.
"""

from itertools import product
from typing import List, Optional, Tuple

import pytest

from agents.report import (
    Basis,
    ReportEvidenceError,
    resolve_bases,
    validate_reading,
)
from core.hexagram_engine import cast_hexagram
from core.reading import HexagramEvidence, LineEvidence, ReadingEvidence
from schemas.hexagram_engine import HexagramCastResult


# ---------------------------------------------------------------------------
# 독립 기대값 — 《역학계몽》 고변점을 테스트가 직접 기술한다.
#
# 구현을 호출해 얻은 값끼리 비교하면 두 구현이 같이 틀렸을 때 통과한다.
# 그래서 규칙을 여기 한 번 더 적는다. 아래 함수는 `core.hexagram_engine`을
# 참조하지 않는다.
# ---------------------------------------------------------------------------

Expect = Tuple[str, int, Optional[int]]  # (종류, 괘 ID, 효 번호)


def expected_bases(
    original_id: int,
    changing: List[int],
    transformed_id: Optional[int],
) -> Tuple[Expect, Optional[Expect]]:
    """동효 수에 따른 주 근거·보조 근거의 기대값."""
    n = len(changing)
    unchanged = sorted(set(range(1, 7)) - set(changing))

    if n == 0:
        # 변효가 없으면 본괘 괘사.
        return ("judgment", original_id, None), None
    if n == 1:
        # 그 한 효의 효사.
        return ("line", original_id, changing[0]), None
    if n == 2:
        # 본괘 두 효사. 상위 효를 우선한다.
        return ("line", original_id, max(changing)), ("line", original_id, min(changing))
    if n == 3:
        # 본괘·지괘 괘사를 함께 보되 본괘를 위주로 한다.
        assert transformed_id is not None
        return ("judgment", original_id, None), ("judgment", transformed_id, None)
    if n == 4:
        # 지괘에서 변하지 않은 두 효사. 아래쪽 효를 우선한다.
        assert transformed_id is not None
        return ("line", transformed_id, unchanged[0]), ("line", transformed_id, unchanged[1])
    if n == 5:
        # 지괘에서 변하지 않은 하나의 효사.
        assert transformed_id is not None
        return ("line", transformed_id, unchanged[0]), None
    # n == 6 — 건은 용구, 곤은 용육. 나머지는 지괘 괘사.
    if original_id in (1, 2):
        return ("line", original_id, 7), None
    assert transformed_id is not None
    return ("judgment", transformed_id, None), None


def as_expect(basis: Optional[Basis]) -> Optional[Expect]:
    if basis is None:
        return None
    kind = "line" if basis.line_number is not None else "judgment"
    return (kind, basis.hexagram_id, basis.line_number)


# ---------------------------------------------------------------------------
# DB 없이 확정 근거를 조립한다.
#
# `core.reading.build_evidence`가 DB에서 하는 일과 같은 모양을 만들되 원문은
# 합성 문자열이다. 검증 대상은 "무엇을 골랐는가"이지 "원문이 맞는가"가 아니다.
# ---------------------------------------------------------------------------


def fake_hexagram(hex_id: int) -> HexagramEvidence:
    return HexagramEvidence(
        hexagram_id=hex_id,
        name_full=f"제{hex_id}괘",
        name_hanja=f"H{hex_id}",
        judgment_text=f"JUDGMENT-{hex_id}",
        judgment_ko=f"괘사번역-{hex_id}",
    )


def fake_line(hex_id: int, line_number: int) -> LineEvidence:
    return LineEvidence(
        hexagram_id=hex_id,
        line_number=line_number,
        position_name="용구/용육" if line_number == 7 else f"{line_number}효",
        statement_text=f"LINE-{hex_id}-{line_number}",
        statement_ko=f"효사번역-{hex_id}-{line_number}",
    )


def fake_reading(cast: HexagramCastResult) -> ReadingEvidence:
    rule = cast.focus_rule
    target_hex_id = (
        cast.transformed_hexagram_id
        if rule.target_hexagram_type == "TRANSFORMED" and cast.transformed_hexagram_id
        else cast.original_hexagram_id
    )
    return ReadingEvidence(
        cast_result=cast,
        original=fake_hexagram(cast.original_hexagram_id),
        transformed=(
            fake_hexagram(cast.transformed_hexagram_id)
            if cast.transformed_hexagram_id
            else None
        ),
        focus_rule=rule,
        target_lines=[fake_line(target_hex_id, n) for n in rule.target_line_numbers],
        target_hexagram_id=target_hex_id,
    )


# ---------------------------------------------------------------------------
# 전수 대조
# ---------------------------------------------------------------------------


def test_4096_combinations_agree_with_focus_rule():
    """효 수치 전체 조합에서 주/보조 근거와 우선순위가 기대값과 일치한다."""
    checked = 0
    invariant = 0

    for values in product((6, 7, 8, 9), repeat=6):
        cast = cast_hexagram(manual_lines=list(values))
        reading = fake_reading(cast)

        # 스스로 모순되지 않아야 한다.
        validate_reading(reading)

        if not cast.changing_lines:
            invariant += 1
            assert cast.transformed_hexagram_id is None, (
                f"불변괘인데 지괘가 있습니다: {values}"
            )
            assert reading.transformed is None

        want_primary, want_aux = expected_bases(
            cast.original_hexagram_id,
            cast.changing_lines,
            cast.transformed_hexagram_id,
        )
        got_primary, got_aux = resolve_bases(reading)

        assert as_expect(got_primary) == want_primary, (
            f"주 근거 불일치: 효={values} 동효={cast.changing_lines} "
            f"기대={want_primary} 실제={as_expect(got_primary)}"
        )
        assert as_expect(got_aux) == want_aux, (
            f"보조 근거 불일치: 효={values} 동효={cast.changing_lines} "
            f"기대={want_aux} 실제={as_expect(got_aux)}"
        )
        checked += 1

    assert checked == 4096, f"4,096 조합을 다 돌지 않았습니다: {checked}"
    assert invariant == 64, f"불변괘는 64건이어야 합니다: {invariant}"


# ---------------------------------------------------------------------------
# 대표값 — 예전 리포트 엔진이 공통 엔진과 갈렸던 자리
# ---------------------------------------------------------------------------


def bases_for(values: List[int]) -> Tuple[Basis, Optional[Basis]]:
    return resolve_bases(fake_reading(cast_hexagram(manual_lines=values)))


def test_three_changing_lines_carry_both_judgments():
    """동효 3개는 본괘·지괘 괘사를 **함께** 싣고 본괘를 위주로 한다.

    예전 리포트는 초효가 동효에 포함되는지로 본괘/지괘 **하나만** 골랐다.
    그래서 같은 3동효에서도 한쪽 괘사가 통째로 빠졌다.
    """
    # 초효가 동효에 포함되는 경우와 아닌 경우 — 둘 다 같은 규칙이어야 한다.
    for values in ([9, 8, 9, 8, 9, 8], [7, 9, 9, 8, 9, 8]):
        cast = cast_hexagram(manual_lines=values)
        assert len(cast.changing_lines) == 3
        primary, aux = bases_for(values)

        assert primary.line_number is None, "괘사여야 합니다"
        assert primary.hexagram_id == cast.original_hexagram_id, "본괘가 위주다"
        assert aux is not None, "지괘 괘사가 참작으로 함께 실려야 한다"
        assert aux.line_number is None
        assert aux.hexagram_id == cast.transformed_hexagram_id


def test_four_changing_lines_read_transformed_unchanged_lines():
    """동효 4개는 **지괘**의 부동효 둘을 읽고 아래쪽을 우선한다.

    예전 리포트는 보조 효를 본괘의 동효에서 가져왔다. 초점이 지괘에 있는데
    인용 원문은 본괘의 것이었다.
    """
    values = [9, 9, 9, 9, 8, 7]  # 동효 1,2,3,4 / 부동효 5,6
    cast = cast_hexagram(manual_lines=values)
    assert cast.changing_lines == [1, 2, 3, 4]

    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (cast.transformed_hexagram_id, 5)
    assert aux is not None
    assert (aux.hexagram_id, aux.line_number) == (cast.transformed_hexagram_id, 6)
    assert primary.hexagram_id != cast.original_hexagram_id


def test_two_changing_lines_prefer_upper():
    values = [9, 7, 7, 7, 9, 7]  # 동효 1, 5
    cast = cast_hexagram(manual_lines=values)
    assert cast.changing_lines == [1, 5]

    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (cast.original_hexagram_id, 5)
    assert aux is not None
    assert (aux.hexagram_id, aux.line_number) == (cast.original_hexagram_id, 1)


def test_five_changing_lines_read_sole_unchanged_transformed_line():
    values = [9, 9, 9, 9, 9, 7]  # 동효 1~5 / 부동효 6
    cast = cast_hexagram(manual_lines=values)
    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (cast.transformed_hexagram_id, 6)
    assert aux is None


def test_zero_changing_lines_read_original_judgment():
    values = [7, 8, 8, 7, 8, 7]  # 화뢰서합(21) 불변괘
    cast = cast_hexagram(manual_lines=values)
    assert cast.original_hexagram_id == 21
    assert cast.changing_lines == []
    assert cast.transformed_hexagram_id is None

    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (21, None)
    assert aux is None


def test_one_changing_line_reads_that_line():
    values = [7, 7, 9, 7, 7, 7]
    cast = cast_hexagram(manual_lines=values)
    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (cast.original_hexagram_id, 3)
    assert aux is None


@pytest.mark.parametrize(
    "values, original_id, term",
    [
        ([9, 9, 9, 9, 9, 9], 1, "용구"),   # 건 6효 모두 변 -> 용구
        ([6, 6, 6, 6, 6, 6], 2, "용육"),   # 곤 6효 모두 변 -> 용육
    ],
)
def test_all_changing_geon_gon_use_special_line(values, original_id, term):
    """건·곤 전효 변은 **괘 ID**로 판정한다.

    예전에는 `"중천건" in original_name`처럼 이름 문자열로 봤다. 이름 표기가
    바뀌거나 DB의 `name_full`이 비면 조용히 일반괘 경로로 떨어진다.
    """
    cast = cast_hexagram(manual_lines=values)
    assert cast.original_hexagram_id == original_id
    assert term in cast.focus_rule.description_ko

    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (original_id, 7)
    assert aux is None


def test_all_changing_general_hexagram_reads_transformed_judgment():
    """건·곤이 아닌 6효 전변은 지괘 괘사만 본다. 본괘 괘사는 참작 대상이 아니다."""
    values = [9, 6, 9, 6, 9, 6]
    cast = cast_hexagram(manual_lines=values)
    assert len(cast.changing_lines) == 6
    assert cast.original_hexagram_id not in (1, 2)

    primary, aux = bases_for(values)
    assert (primary.hexagram_id, primary.line_number) == (cast.transformed_hexagram_id, None)
    assert aux is None, "3동효(BOTH)와 달리 본괘 괘사를 보조로 싣지 않는다"


# ---------------------------------------------------------------------------
# 잘못된 입력 — 임의 데이터로 메우지 않는다
# ---------------------------------------------------------------------------


def reading_with(**overrides) -> ReadingEvidence:
    cast = cast_hexagram(manual_lines=[7, 8, 9, 8, 9, 7])
    reading = fake_reading(cast)
    for key, value in overrides.items():
        setattr(reading, key, value)
    return reading


def test_wrong_line_count_is_rejected():
    reading = reading_with()
    reading.cast_result = reading.cast_result.model_copy(
        update={"lines": reading.cast_result.lines[:5]}
    )
    with pytest.raises(ReportEvidenceError, match="6효가 아닙니다"):
        validate_reading(reading)


def test_changing_lines_must_match_line_values():
    reading = reading_with()
    reading.cast_result = reading.cast_result.model_copy(
        update={"changing_lines": [1, 2]}
    )
    with pytest.raises(ReportEvidenceError, match="동효 목록이 효 수치와 어긋납니다"):
        validate_reading(reading)


def test_line_values_must_match_original_hexagram_id():
    """6효 수치가 곧 괘다. 둘이 어긋나면 화면의 수리 표가 거짓이 된다."""
    reading = reading_with()
    wrong = 1 if reading.cast_result.original_hexagram_id != 1 else 2
    reading.cast_result = reading.cast_result.model_copy(
        update={"original_hexagram_id": wrong}
    )
    with pytest.raises(ReportEvidenceError, match="맞지 않습니다"):
        validate_reading(reading)


def test_invariant_cast_must_not_carry_transformed():
    cast = cast_hexagram(manual_lines=[7, 8, 8, 7, 8, 7])
    reading = fake_reading(cast)
    reading.transformed = fake_hexagram(11)
    with pytest.raises(ReportEvidenceError, match="불변괘인데 지괘 원문"):
        validate_reading(reading)


def test_evidence_hexagram_must_match_cast():
    reading = reading_with()
    reading.original = fake_hexagram(
        1 if reading.cast_result.original_hexagram_id != 1 else 2
    )
    with pytest.raises(ReportEvidenceError, match="본괘 원문이 다른 괘입니다"):
        validate_reading(reading)


def test_missing_target_lines_is_an_evidence_error():
    """효사가 초점인데 효사가 없으면 괘사로 대신하지 않는다."""
    reading = reading_with()
    reading.target_lines = []
    with pytest.raises(ReportEvidenceError, match="대상 효사가 조립되지 않았습니다"):
        resolve_bases(reading)
