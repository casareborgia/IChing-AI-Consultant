"""확정 근거 조립(core.reading) 검증.

상담 에이전트에게 무엇이 건네지는가를 지키는 테스트다. 두 가지가 핵심이다 —
한문이 새지 않을 것, 그리고 초점 규칙이 가리키는 것만 주 근거로 삼을 것.
"""

import pytest

from core.db import AsyncSessionLocal
from core.hexagram_engine import cast_hexagram
from core.reading import build_evidence
from schemas.hexagram_engine import FocusType


@pytest.mark.asyncio
async def test_요약에_소상전_한문이_섞이지_않는다():
    """소상전은 한글 번역으로만 들어간다.

    예전에는 `(상전 원문: 象曰 潛龍勿用 陽在下也)` 형태로 한문이 그대로 들어가,
    '한글 요약'이라는 이름표를 달고 상담 프롬프트까지 갔다.
    """
    async with AsyncSessionLocal() as session:
        # 건괘 1효 동효 -> 초점이 효사로 잡힌다
        cast = cast_hexagram(manual_lines=[9, 7, 7, 7, 7, 7])
        evidence = await build_evidence(session, cast)

        assert evidence.target_lines, "동효 1개면 대상 효사가 있어야 한다"
        summary = evidence.summary_korean

        for line in evidence.target_lines:
            if line.small_xiang_text:
                assert line.small_xiang_text not in summary
            # 한글 소상전은 들어가야 한다 (근거를 통째로 버리는 게 아니다)
            if line.small_xiang_ko:
                assert line.small_xiang_ko in summary

        # 괘 이름을 한자로 병기하지 않는다 (첫 줄이 괘 식별 줄이다).
        # 번역문 안에 남은 한자("건(乾)은 …")는 번역 데이터 쪽 문제라 여기서 다루지 않는다.
        identity_line = summary.split("\n")[0]
        assert evidence.original.name_hanja not in identity_line
        assert evidence.original.name_full in identity_line
        # 원문 필드 자체는 보존된다 — "왜 이 해석인지" 물었을 때 대야 하기 때문
        assert evidence.original.judgment_text


@pytest.mark.asyncio
async def test_6효_모두_변한_일반괘는_본괘_괘사를_주근거로_삼지_않는다():
    """엔진이 3변효(BOTH_JUDGMENTS)와 구분해 둔 자리를 요약에서 다시 뭉개지 않는다."""
    async with AsyncSessionLocal() as session:
        # 준괘(3) 6효 모두 변함 -> TRANSFORMED_JUDGMENT
        cast = cast_hexagram(manual_lines=[9, 6, 6, 6, 9, 6])
        assert cast.focus_rule.focus_type == FocusType.TRANSFORMED_JUDGMENT

        evidence = await build_evidence(session, cast)
        summary = evidence.summary_korean
        주근거 = summary.split("주 해석 근거:")[1]

        assert evidence.transformed is not None
        assert evidence.transformed.judgment_ko in 주근거
        assert evidence.original.judgment_ko not in 주근거

        # 반면 3변효는 본괘 괘사를 위주로 함께 본다
        cast3 = cast_hexagram(manual_lines=[9, 9, 9, 7, 7, 7])
        assert cast3.focus_rule.focus_type == FocusType.BOTH_JUDGMENTS
        ev3 = await build_evidence(session, cast3)
        주근거3 = ev3.summary_korean.split("주 해석 근거:")[1]
        assert ev3.original.judgment_ko in 주근거3


@pytest.mark.asyncio
async def test_초점이_지괘일_때_대상_괘_ID가_지괘를_가리킨다():
    """동효 5개면 볼 효사는 지괘의 효다. RAG도 이 ID로 좁혀야 한다."""
    async with AsyncSessionLocal() as session:
        cast = cast_hexagram(manual_lines=[9, 9, 9, 9, 9, 7])
        assert cast.focus_rule.target_hexagram_type == "TRANSFORMED"

        evidence = await build_evidence(session, cast)
        assert evidence.target_hexagram_id == cast.transformed_hexagram_id
        assert evidence.target_hexagram_id != cast.original_hexagram_id
        for line in evidence.target_lines:
            assert line.hexagram_id == cast.transformed_hexagram_id
