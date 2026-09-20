"""v2 리포트 생성·검증·실패 계약.

DB도 실제 LLM도 부르지 않는다. 확인하려는 것은 **서버가 확정한 것과 모델이 쓴 것이
섞이지 않는가**, 그리고 **검증이 무엇을 막는가**다.
"""

import copy
from unittest.mock import Mock, patch

import pytest

from agents.report_v2 import (
    CODE_EVIDENCE_INVALID,
    CODE_MODEL_FAILED,
    CODE_NARRATIVE_INVALID,
    ReportGenerationError,
    build_sources,
    build_user_facts,
    narrative_problems,
    run_report_v2_agent,
    snapshot_hash,
)
from agents.report import resolve_bases
from schemas.report_v2 import NarrativeDraft, SourceRole
from tests.fixtures.report_v2_builder import (
    FIXED_NOW,
    VALID_DRAFT,
    build_reading,
    sample_evidences,
    stub_llm,
)


QUESTION = "요즘 일이 막혀 있는 느낌입니다. 어디서부터 손을 대야 할까요?"

# 한자가 섞인 본문. 길이 제한에 먼저 걸리지 않도록 충분히 길게 둔다 —
# 그래야 막는 이유가 "짧아서"가 아니라 "한자라서"임이 드러난다.
HANJA_HEADLINE = "지금은 利用獄이 가리키는 자리에 서 계십니다."


async def run(values, *responses, question=QUESTION, translated_lines=True, client=None):
    reading = build_reading(values, translated_lines=translated_lines)
    llm = client or stub_llm(*responses)
    with patch("agents.report_v2.load_system_prompt", return_value="STUB"):
        report = await run_report_v2_agent(
            question=question,
            session_id="s-0001",
            reading=reading,
            evidences=sample_evidences(reading),
            topic_category="직장/진로",
            client=llm,
            now=FIXED_NOW,
        )
    return report, llm


def draft_with(**overrides):
    """VALID_DRAFT를 복사해 일부만 바꾼다."""
    data = copy.deepcopy(VALID_DRAFT)
    for path, value in overrides.items():
        node = data
        parts = path.split(".")
        for key in parts[:-1]:
            node = node[key]
        node[parts[-1]] = value
    return data


# ---------------------------------------------------------------------------
# 확정 사실과 서술의 분리
# ---------------------------------------------------------------------------


def test_llm_contract_has_no_slot_for_confirmed_facts():
    """모델이 괘 ID나 원문을 되돌려 보낼 칸이 아예 없다.

    프롬프트로 "고치지 마십시오"라고 부탁하는 대신 받을 자리를 두지 않는다.
    모르는 칸을 덧붙이는 것도 막는다(`extra="forbid"`) — 조용히 무시하면 모델이
    무엇을 보냈는지 알 수 없다.
    """
    assert set(NarrativeDraft.model_fields) == {"narrative", "counseling_handoff"}
    assert NarrativeDraft.model_config.get("extra") == "forbid"

    hostile = draft_with()
    hostile["academic_details"] = {"casting": {"original_hexagram_id": 1}}
    with pytest.raises(Exception):
        NarrativeDraft.model_validate(hostile)


@pytest.mark.asyncio
async def test_confirmed_facts_come_from_the_reading_not_the_model():
    report, _ = await run([7, 8, 8, 7, 8, 7])

    assert report.academic_details.casting.original_hexagram_id == 21
    assert report.academic_details.casting.original_name == "화뢰서합"
    assert report.session_id == "s-0001"
    # report_id는 서버가 만든 UUID다.
    assert len(report.report_id) == 36 and report.report_id.count("-") == 4


@pytest.mark.asyncio
async def test_invariant_report_has_no_transformed_hexagram():
    report, _ = await run([7, 8, 8, 7, 8, 7])
    casting = report.academic_details.casting
    assert casting.original_hexagram_id == 21
    assert casting.has_transformation is False
    assert casting.transformed_hexagram_id is None
    assert casting.transformed_name is None


@pytest.mark.asyncio
async def test_sources_are_server_built_and_role_tagged():
    report, _ = await run([9, 9, 9, 9, 8, 7])  # 동효 4개 — 초점은 지괘
    sources = report.academic_details.sources
    roles = [s.role for s in sources]

    assert roles[0] == SourceRole.PRIMARY
    assert SourceRole.AUXILIARY in roles
    # 효사가 주 근거이므로 본괘 괘사는 배경이다. 주 근거로 올라가지 않는다.
    assert SourceRole.BACKGROUND in roles
    trans_id = report.academic_details.casting.transformed_hexagram_id
    assert sources[0].hexagram_id == trans_id


@pytest.mark.asyncio
async def test_daesang_is_supplement_not_primary():
    """0변효에서도 대상전은 보충이다. 괘사 자리를 대신하지 않는다."""
    report, _ = await run([7, 8, 8, 7, 8, 7])
    by_role = {s.role: s for s in report.academic_details.sources}

    assert by_role[SourceRole.PRIMARY].classical_text == "噬嗑 亨 利用獄"
    assert SourceRole.SUPPLEMENT in by_role
    assert "象曰" in by_role[SourceRole.SUPPLEMENT].classical_text


@pytest.mark.asyncio
async def test_missing_translation_stays_missing():
    """번역이 없으면 null로 둔다. 원문을 보고 지어내지 않는다."""
    report, _ = await run([9, 7, 7, 7, 7, 7], translated_lines=False)
    primary = report.academic_details.sources[0]
    assert primary.classical_text
    assert primary.classical_translation is None


@pytest.mark.asyncio
async def test_locator_is_null_when_unverified():
    """원전 위치를 확인할 수 없으면 비운다. 편명·페이지를 추측하지 않는다."""
    report, _ = await run([7, 8, 8, 7, 8, 7])
    assert all(s.locator is None for s in report.academic_details.sources)


def test_user_facts_are_real_excerpts():
    facts = build_user_facts("첫 문장입니다. 둘째 문장입니다!\n셋째 줄입니다")
    assert [f.id for f in facts] == ["U1", "U2", "U3"]
    assert facts[0].text == "첫 문장입니다."
    assert facts[2].text == "셋째 줄입니다"


# ---------------------------------------------------------------------------
# 검증
# ---------------------------------------------------------------------------


def _problems(draft_dict, source_ids=("E1", "E2"), fact_ids=("U1",)):
    return narrative_problems(
        NarrativeDraft.model_validate(draft_dict), list(source_ids), list(fact_ids)
    )


def test_unknown_evidence_ref_is_rejected():
    problems = _problems(draft_with(**{"narrative.perspective": {
        **VALID_DRAFT["narrative"]["perspective"], "evidence_refs": ["E99"]}}))
    assert any("evidence_refs" in p for p in problems)


def test_unknown_user_fact_ref_is_rejected():
    ec = {**VALID_DRAFT["narrative"]["emotional_context"], "user_fact_refs": ["U9"]}
    problems = _problems(draft_with(**{"narrative.emotional_context": ec}))
    assert any("user_fact_refs" in p for p in problems)


def test_suggested_action_must_match_the_proposed_task():
    """제안한 행동은 하나다. 상담 인계가 다른 행동을 말하면 사용자는 둘을 받는다."""
    problems = _problems(
        draft_with(**{"counseling_handoff.suggested_action_title": "다른 행동"})
    )
    assert any("suggested_action_title" in p for p in problems)


def test_hanja_in_narrative_is_rejected():
    """본문에 한자를 쓰지 않는다. 원문은 근거 패널에 따로 실린다."""
    problems = _problems(
        draft_with(**{"narrative.headline_metaphor": "利用獄이 가리키는 자리입니다."})
    )
    assert any("한자" in p for p in problems)


def test_blame_shifting_headline_is_rejected():
    """'…이 아니라 당신의 … 때문입니다' 구조는 원인 단정이다."""
    problems = _problems(draft_with(**{
        "narrative.headline_metaphor":
            "지금 당신을 지치게 한 건 일이 아니라, 당신의 경계선이 없어서입니다."
    }))
    assert any("원인을 단정" in p for p in problems)


def test_diagnosis_assertion_is_rejected():
    problems = _problems(draft_with(**{
        "narrative.emotional_context": {
            **VALID_DRAFT["narrative"]["emotional_context"],
            "validation": "말씀을 들어보니 우울증입니다. 쉬셔야 합니다.",
        }
    }))
    assert any("병명" in p for p in problems)


def test_mentioning_a_condition_without_asserting_it_is_allowed():
    """단어가 있다는 이유만으로 막지 않는다. 확정 서술만 잡는다."""
    problems = _problems(draft_with(**{
        "narrative.emotional_context": {
            **VALID_DRAFT["narrative"]["emotional_context"],
            "validation": "혹시 우울증이 아닐까 걱정된다고 하셨지요. 그 마음이 이해됩니다.",
        }
    }))
    assert problems == []


def test_certain_future_is_rejected_but_hedged_sentence_is_not():
    certain = _problems(draft_with(**{
        "narrative.value_direction": {
            **VALID_DRAFT["narrative"]["value_direction"],
            "rationale": "이대로 두면 반드시 무너집니다. 지금 바꾸셔야 합니다.",
        }
    }))
    assert any("확정적" in p for p in certain)

    hedged = _problems(draft_with(**{
        "narrative.value_direction": {
            **VALID_DRAFT["narrative"]["value_direction"],
            "rationale": "이대로 두면 반드시 어려워진다고 말할 수는 없고, "
                         "어떤 조건에서 그렇게 되는지 살펴볼 가능성이 있습니다.",
        }
    }))
    assert hedged == []


def test_valid_draft_has_no_problems():
    assert _problems(VALID_DRAFT) == []


# ---------------------------------------------------------------------------
# 생성 / 수정 / 실패
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_uses_one_call_and_no_refinement():
    """v1의 무조건 정제 호출을 없앴다. 정상이면 1회다."""
    report, llm = await run([7, 8, 8, 7, 8, 7])
    assert llm.complete_json.call_count == 1
    assert report.generation_metadata.repair_count == 0


@pytest.mark.asyncio
async def test_failed_validation_triggers_one_repair_with_the_same_evidence():
    bad = draft_with(**{"narrative.headline_metaphor": HANJA_HEADLINE})
    report, llm = await run([7, 8, 8, 7, 8, 7], bad, VALID_DRAFT)

    assert llm.complete_json.call_count == 2
    assert report.generation_metadata.repair_count == 1

    first, second = [c.args[0] for c in llm.complete_json.call_args_list]
    # 수정 요청에 초안과 같은 근거가 그대로 들어간다.
    assert first in second
    assert "[검증 실패]" in second
    assert "한자" in second


@pytest.mark.asyncio
async def test_second_failure_stops_and_does_not_disguise_as_ready():
    bad = draft_with(**{"narrative.headline_metaphor": HANJA_HEADLINE})

    with pytest.raises(ReportGenerationError) as excinfo:
        await run([7, 8, 8, 7, 8, 7], bad, bad)

    assert excinfo.value.code == CODE_NARRATIVE_INVALID


@pytest.mark.asyncio
async def test_at_most_two_logical_calls():
    bad = draft_with(**{"narrative.headline_metaphor": HANJA_HEADLINE})
    llm = stub_llm(bad, bad)
    with pytest.raises(ReportGenerationError):
        await run([7, 8, 8, 7, 8, 7], client=llm)
    assert llm.complete_json.call_count == 2


@pytest.mark.asyncio
async def test_model_exception_maps_to_a_stable_code():
    llm = Mock()
    llm.model_name = "stub"
    llm.complete_json.side_effect = TimeoutError("upstream detail")

    with pytest.raises(ReportGenerationError) as excinfo:
        await run([7, 8, 8, 7, 8, 7], client=llm)

    assert excinfo.value.code == CODE_MODEL_FAILED


@pytest.mark.asyncio
async def test_inconsistent_cast_fails_before_any_model_call():
    reading = build_reading([7, 8, 8, 7, 8, 7])
    reading.cast_result = reading.cast_result.model_copy(
        update={"original_hexagram_id": 1}
    )
    llm = stub_llm(VALID_DRAFT)

    with patch("agents.report_v2.load_system_prompt", return_value="STUB"):
        with pytest.raises(ReportGenerationError) as excinfo:
            await run_report_v2_agent(
                question=QUESTION,
                session_id="s-0001",
                reading=reading,
                evidences=[],
                client=llm,
            )

    assert excinfo.value.code == CODE_EVIDENCE_INVALID
    llm.complete_json.assert_not_called()


# ---------------------------------------------------------------------------
# 메타데이터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metadata_does_not_invent_provider_or_model():
    """클라이언트를 주입받으면 provider를 모른다. 지어내지 않는다."""
    report, _ = await run([7, 8, 8, 7, 8, 7])
    meta = report.generation_metadata
    assert meta.provider is None
    assert meta.model == "stub-model"
    assert meta.rule_version == report.academic_details.focus_rule.rule_version
    assert meta.prompt_version.startswith("v2.0.0+")


@pytest.mark.asyncio
async def test_snapshot_hash_tracks_the_evidence_not_the_narrative():
    """같은 근거면 같은 지문이다. 서술이 달라져도 바뀌지 않는다."""
    a, _ = await run([7, 8, 8, 7, 8, 7])
    other = draft_with(**{"narrative.headline_metaphor": "완전히 다른 한 줄입니다."})
    b, _ = await run([7, 8, 8, 7, 8, 7], other)

    assert a.generation_metadata.evidence_snapshot_hash == b.generation_metadata.evidence_snapshot_hash
    assert a.narrative.headline_metaphor != b.narrative.headline_metaphor

    c, _ = await run([9, 7, 7, 7, 7, 7])
    assert c.generation_metadata.evidence_snapshot_hash != a.generation_metadata.evidence_snapshot_hash


@pytest.mark.asyncio
async def test_rag_annotations_are_not_truncated_into_the_sources():
    reading = build_reading([9, 7, 7, 7, 7, 7])
    evidences = sample_evidences(reading)
    primary, auxiliary = resolve_bases(reading)
    sources = build_sources(reading, evidences, primary, auxiliary)

    annotations = [s for s in sources if s.role == SourceRole.ANNOTATION]
    assert len(annotations) == len(evidences)
