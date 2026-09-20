"""판본 판별·저장/조회·상담 인계·마크다운.

리포트 본문이 바뀌는 것보다 위험한 것은 **판본이 섞인 채로 소비되는 것**이다.
v1 이름으로 v2 문서를 파면 빈 문자열이 나오고, 그 빈 값이 기본값으로 바뀌어
사실처럼 화면과 프롬프트에 들어간다.
"""

import json
from pathlib import Path

import pytest

from agents.divination_chat_engine import adapt_to_report_payload
from agents.report_handoff import counsel_prompt_block
from core.report_markdown import escape, render_markdown_from_dict
from core.report_versions import (
    CODE_REPORT_UNAVAILABLE,
    REPORT_LEGACY,
    REPORT_UNKNOWN,
    REPORT_V2,
    public_report_error_code,
    report_schema_version,
)
from agents.report_v2 import CODE_NARRATIVE_INVALID, ReportGenerationError
from tests.fixtures.report_v2_builder import legacy_report


FIXTURES = Path(__file__).parent / "fixtures" / "report_v2"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 판본 판별
# ---------------------------------------------------------------------------


def test_version_detection():
    assert report_schema_version(None) is None
    assert report_schema_version({}) is None
    assert report_schema_version(legacy_report()) == REPORT_LEGACY
    assert report_schema_version(load("v2_invariant")) == REPORT_V2


def test_unknown_explicit_version_is_not_silently_read_as_legacy():
    """모르는 판본을 legacy로 묵인하면 빈 칸이 정상처럼 보인다."""
    assert report_schema_version({"schema_version": "3.0"}) == REPORT_UNKNOWN
    assert counsel_prompt_block({"schema_version": "3.0"}) is None


def test_stored_v2_is_readable_regardless_of_the_generation_flag():
    """플래그는 **생성**에만 관여한다. 이미 저장된 v2는 그대로 읽힌다."""
    from core.config import settings

    stored = load("v2_invariant")
    original = settings.REPORT_SCHEMA_VERSION
    try:
        for flag in ("legacy", "2.0"):
            settings.REPORT_SCHEMA_VERSION = flag
            assert report_schema_version(stored) == REPORT_V2
            assert counsel_prompt_block(stored)
            assert render_markdown_from_dict(stored)
    finally:
        settings.REPORT_SCHEMA_VERSION = original


def test_fixtures_round_trip_through_the_schema():
    """저장된 원본이 스키마를 그대로 통과한다 — 읽기가 값을 바꾸지 않는다."""
    from schemas.report_v2 import PreCounselingReport

    for name in (
        "v2_invariant", "v2_single_changing", "v2_three_changing",
        "v2_multi_changing", "v2_missing_translation",
    ):
        raw = load(name)
        assert PreCounselingReport.model_validate(raw).model_dump(mode="json") == raw


# ---------------------------------------------------------------------------
# 상담 인계
# ---------------------------------------------------------------------------


def test_v2_handoff_separates_confirmed_from_unconfirmed():
    block = counsel_prompt_block(load("v2_invariant"))

    assert "[확정 원전 근거" in block
    assert "[리포트의 잠정 해석" in block
    assert "[아직 확인되지 않은 것" in block
    assert "[리포트가 제안한 행동" in block
    assert "내담자가 선택하지 않았습니다" in block


def test_v2_handoff_tells_the_counselor_to_accept_corrections():
    """사용자가 가설을 부인하면 그 정정이 이긴다. 리포트가 먼저 썼다는 이유로 굳지 않는다."""
    block = counsel_prompt_block(load("v2_invariant"))
    assert "부인하면" in block and "유지하지 마십시오" in block


def test_v2_handoff_does_not_truncate():
    """v1 어댑터는 각 절을 100자에서 잘라 `...`을 붙였다."""
    report = load("v2_invariant")
    rationale = report["narrative"]["value_direction"]["rationale"]
    assert len(rationale) > 60
    block = counsel_prompt_block(report)
    assert rationale in block
    assert "..." not in block


def test_v2_handoff_carries_translations_not_source_text():
    """상담사에게는 한글 번역만 간다. 원문은 넘기지 않는다.

    번역문 안에 남은 한자는 저본 쪽 문제라 여기서 다루지 않는다 — 괘사 번역
    45/64가 괘 이름을 한자로 달고 있다. `tests/test_reading_evidence.py`가 같은
    경계를 이미 적어 두었다.
    """
    report = load("v2_invariant")
    block = counsel_prompt_block(report)

    primary = report["academic_details"]["sources"][0]
    assert primary["classical_text"] == "噬嗑 亨 利用獄"
    assert primary["classical_text"] not in block
    assert primary["classical_translation"] in block


def test_legacy_handoff_still_works_and_is_not_called_a_conclusion():
    block = counsel_prompt_block(legacy_report())
    assert "걸려 있는 것을 하나씩 떼어내십시오." in block
    assert "합의된 결론이 아닙니다" in block


def test_chat_payload_adapter_reads_v2_without_inventing_a_transformed_hexagram():
    payload = adapt_to_report_payload(report_data=load("v2_invariant"))
    derivation = payload["derivation_data"]

    assert derivation["original_hexagram"]["name"] == "화뢰서합"
    # 불변괘다. 예전 경로는 지괘 자리에 본괘 이름을 되풀이해 넣었다.
    assert derivation["resulting_hexagram"]["name"] == ""
    assert payload["judgment_rules"]["local_target_text"] == "서합은 형통하니, 옥사를 씀이 이롭다."
    assert "噬嗑" not in json.dumps(payload, ensure_ascii=False)


def test_legacy_chat_payload_no_longer_leaks_hanja():
    """상담 에이전트는 '한문 원문 노출 차단'을 첫 줄에 적어 두고 있다."""
    payload = adapt_to_report_payload(report_data=legacy_report())
    assert payload["judgment_rules"]["local_target_text"] == "걸려 있는 것을 하나씩 떼어내십시오."


# ---------------------------------------------------------------------------
# 마크다운
# ---------------------------------------------------------------------------


def test_markdown_is_deterministic():
    data = load("v2_invariant")
    assert render_markdown_from_dict(data) == render_markdown_from_dict(data)


def test_markdown_has_no_hanja_outside_the_evidence_panel():
    md = render_markdown_from_dict(load("v2_invariant"))
    body, _, panel = md.partition("<details>")

    assert "噬嗑" not in body and "象曰" not in body
    assert "噬嗑 亨 利用獄" in panel


def test_markdown_shows_missing_translation_as_missing():
    md = render_markdown_from_dict(load("v2_missing_translation"))
    assert "(확인된 번역 없음)" in md


def test_markdown_marks_the_action_as_a_proposal():
    md = render_markdown_from_dict(load("v2_invariant"))
    assert "제안입니다" in md
    assert "다짐" not in md and "서약" not in md


def test_markdown_marks_hypothesis_as_hypothesis():
    md = render_markdown_from_dict(load("v2_invariant"))
    assert "함께 살펴볼 가설입니다" in md


def test_invariant_markdown_does_not_claim_a_transformed_hexagram():
    md = render_markdown_from_dict(load("v2_invariant"))
    assert "**지괘**: 없음 (동효가 없는 불변괘입니다)" in md


def test_markdown_does_not_record_the_users_state_of_mind():
    md = render_markdown_from_dict(load("v2_invariant"))
    assert "무념무상" not in md and "경건" not in md
    assert "재삼독" in md


@pytest.mark.parametrize(
    "raw, must_not_contain",
    [
        ("<script>alert(1)</script>", "<script>"),
        ("### 가짜 제목", "\n### "),
        ("| 표 | 주입 |", "| 표 |"),
        ("**굵게**", "**굵게**"),
    ],
)
def test_escape_blocks_structure_injection(raw, must_not_contain):
    assert must_not_contain not in escape(raw)


def test_escape_collapses_newlines():
    """값 하나가 새 블록을 열지 못하게 줄바꿈을 접는다."""
    assert "\n" not in escape("첫 줄\n\n# 두 번째 줄")


def test_escape_handles_ampersand_first():
    assert escape("A & <b>") == "A &amp; &lt;b&gt;"


# ---------------------------------------------------------------------------
# 실패 계약
# ---------------------------------------------------------------------------


def test_public_error_code_hides_internal_exception_names():
    """예전에는 `type(exc).__name__`이 그대로 응답에 실렸다."""
    assert public_report_error_code(TimeoutError("upstream host x.y.z")) == CODE_REPORT_UNAVAILABLE
    assert public_report_error_code(KeyError("section2_action")) == CODE_REPORT_UNAVAILABLE


def test_public_error_code_keeps_declared_report_codes():
    exc = ReportGenerationError(CODE_NARRATIVE_INVALID, "3건")
    assert public_report_error_code(exc) == CODE_NARRATIVE_INVALID


def test_public_error_code_never_leaks_the_detail():
    exc = ReportGenerationError(CODE_NARRATIVE_INVALID, "사용자 고민 원문이 들어간 상세")
    assert "사용자" not in public_report_error_code(exc)
