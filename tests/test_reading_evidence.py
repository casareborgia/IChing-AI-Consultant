"""확정 근거 조립(core.reading) 검증.

상담 에이전트에게 무엇이 건네지는가를 지키는 테스트다. 두 가지가 핵심이다 —
한문이 새지 않을 것, 그리고 초점 규칙이 가리키는 것만 주 근거로 삼을 것.
"""

import pytest

from core.db import AsyncSessionLocal
from core.hexagram_engine import cast_hexagram
from core.reading import BODY_USE_SUPPLEMENT_HEADER, build_evidence
from schemas.hexagram_engine import BodyUseType, FocusType


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

        # 반면 3변효(초효 포함 시)는 본괘 괘사를 주근거로 삼는다
        cast3 = cast_hexagram(manual_lines=[9, 9, 9, 7, 7, 7])
        assert cast3.focus_rule.focus_type == FocusType.ORIGINAL_JUDGMENT
        ev3 = await build_evidence(session, cast3)
        주근거3 = ev3.summary_korean.split("주 해석 근거:")[1]
        assert ev3.original.judgment_ko in 주근거3

        # 3변효(초효 미포함 시)는 지괘 괘사를 주근거로 삼는다
        cast3_no1 = cast_hexagram(manual_lines=[7, 9, 9, 9, 7, 7])
        assert cast3_no1.focus_rule.focus_type == FocusType.TRANSFORMED_JUDGMENT
        ev3_no1 = await build_evidence(session, cast3_no1)
        주근거3_no1 = ev3_no1.summary_korean.split("주 해석 근거:")[1]
        assert ev3_no1.transformed is not None
        assert ev3_no1.transformed.judgment_ko in 주근거3_no1


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


def _주근거(summary: str) -> str:
    """'주 해석 근거' 절만 잘라낸다. 체용 참작 절은 뺀다.

    문자열 뒤쪽을 통째로 보면 참작 절까지 섞여, 주 근거에 무엇이 들었는지를
    셀 수 없다.
    """
    본문 = summary.split("주 해석 근거:")[1]
    return 본문.split(BODY_USE_SUPPLEMENT_HEADER)[0]


@pytest.mark.asyncio
async def test_체용이_초점과_어긋나도_주근거는_초점이_정한다():
    """체용이 지괘를 가리켜도 초점이 본괘면 주 근거는 본괘 괘사다.

    바꿔치기하면 "확정 근거"라는 말이 무의미해진다. 근거를 고르는 권한은
    초점 규칙에만 있다.
    """
    async with AsyncSessionLocal() as session:
        # 곤(2) 1·2·3효 동 -> 지괘 태(11). 초점은 본괘, 체용은 지괘를 가리킨다
        cast = cast_hexagram(manual_lines=[6, 6, 6, 8, 8, 8])
        assert cast.focus_rule.target_hexagram_type == "ORIGINAL"
        assert cast.focus_rule.body_use_type == BodyUseType.EMPHASIZE_TRANSFORMED

        ev = await build_evidence(session, cast)
        주근거 = _주근거(ev.summary_korean)

        assert ev.original.judgment_ko in 주근거
        assert ev.transformed is not None
        assert ev.transformed.judgment_ko not in 주근거, "체용이 주 근거를 바꿔치기했다"

        # 무게를 실으라고 한 쪽 괘사는 참작 절에 따로 온다 —
        # 주지 않으면 모델이 없는 근거를 지어낼 자리가 된다
        참작 = ev.summary_korean.split(BODY_USE_SUPPLEMENT_HEADER)[1]
        assert ev.transformed.judgment_ko in 참작


@pytest.mark.asyncio
async def test_반대_방향_어긋남도_같은_규칙으로_처리된다():
    """초점이 지괘, 체용이 본괘인 경우."""
    async with AsyncSessionLocal() as session:
        # 태(11) 6효 전변 -> 지괘 비(12). 초점은 지괘, 체용은 본괘
        cast = cast_hexagram(manual_lines=[9, 9, 9, 6, 6, 6])
        assert cast.focus_rule.target_hexagram_type == "TRANSFORMED"
        assert cast.focus_rule.body_use_type == BodyUseType.EMPHASIZE_ORIGINAL

        ev = await build_evidence(session, cast)
        주근거 = _주근거(ev.summary_korean)

        assert ev.transformed is not None
        assert ev.transformed.judgment_ko in 주근거
        assert ev.original.judgment_ko not in 주근거

        참작 = ev.summary_korean.split(BODY_USE_SUPPLEMENT_HEADER)[1]
        assert ev.original.judgment_ko in 참작


@pytest.mark.asyncio
async def test_체용과_초점이_같은_방향이면_참작을_덧붙이지_않는다():
    """이미 주 근거에 있는 괘사를 참작으로 한 번 더 싣지 않는다."""
    async with AsyncSessionLocal() as session:
        # 건(1) 2·3·4효 동 -> 지괘 익(42). 초점도 지괘, 체용도 지괘
        cast = cast_hexagram(manual_lines=[7, 9, 9, 9, 7, 7])
        assert cast.focus_rule.target_hexagram_type == "TRANSFORMED"
        assert cast.focus_rule.body_use_type == BodyUseType.EMPHASIZE_TRANSFORMED

        ev = await build_evidence(session, cast)
        assert BODY_USE_SUPPLEMENT_HEADER not in ev.summary_korean
        assert "같은 방향" in (cast.focus_rule.body_use_note_ko or "")


@pytest.mark.asyncio
async def test_효사가_주근거일_때는_본괘_괘사를_참작으로_중복하지_않는다():
    """효사 초점에서는 본괘 괘사가 이미 '배경'으로 실려 있다."""
    async with AsyncSessionLocal() as session:
        # 지괘가 체용 본괘 강조(12 비)가 되도록: 동인(13) 1효 동 -> ?
        # 확정적으로 만들기 위해 체용 대상 지괘를 갖는 1변효 조합을 찾는다
        from core.hexagram_engine import HEXAGRAM_ID_TO_BINARY

        찾음 = None
        for hid, binary in HEXAGRAM_ID_TO_BINARY.items():
            for pos in range(1, 7):
                vals = [
                    (9 if binary[p - 1] == "1" else 6) if p == pos
                    else (7 if binary[p - 1] == "1" else 8)
                    for p in range(1, 7)
                ]
                c = cast_hexagram(manual_lines=vals)
                if c.focus_rule.body_use_type == BodyUseType.EMPHASIZE_ORIGINAL:
                    찾음 = c
                    break
            if 찾음:
                break

        assert 찾음 is not None, "1변효 + 체용 본괘 강조 조합이 없다"
        ev = await build_evidence(session, 찾음)
        # 효사가 주 근거이고 본괘 괘사는 배경으로 이미 있으므로 참작 절이 없다
        assert BODY_USE_SUPPLEMENT_HEADER not in ev.summary_korean
        assert "배경 — 본괘 괘사" in ev.summary_korean
