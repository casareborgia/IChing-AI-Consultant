# -*- coding: utf-8 -*-
"""행동 전념 카드(Action Commitment Card) 및 SPI 통합 엔진 v2.0 단위 테스트."""

import pytest
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from agents.action_card_generator_v2 import ActionCardGeneratorV2
from agents.journal import write_journal
from core.models.counsel import CounselSession, CounselTurn, JournalEntry


def test_check_crisis_signals():
    generator = ActionCardGeneratorV2()

    # 1. 위기 신호 감지 케이스
    crisis_transcript = [
        {"role": "user", "content": "선생님, 모든 게 너무 힘들고 그냥 다 끝내고 싶어요. 죽고 싶다는 생각만 듭니다."},
        {"role": "assistant", "content": "많이 지치고 힘드셨군요."},
    ]
    assert generator.check_crisis_signals(crisis_transcript) is True
    assert generator.evaluate_risk_level(crisis_transcript) == "CRISIS"

    # 2. 일반 성찰 케이스
    normal_transcript = [
        {"role": "user", "content": "새로운 직장으로 이직을 고민 중인데 어떻게 마음을 먹어야 할까요?"},
        {"role": "assistant", "content": "새로운 시작의 문턱에서 신중함이 필요합니다."},
    ]
    assert generator.check_crisis_signals(normal_transcript) is False
    assert generator.evaluate_risk_level(normal_transcript) == "NORMAL"


def test_simulate_yarrow_math():
    generator = ActionCardGeneratorV2()
    rem_list, val, result_code = generator.simulate_yarrow_line()

    assert len(rem_list) == 3
    assert rem_list[0] in (5, 9)
    assert rem_list[1] in (4, 8)
    assert rem_list[2] in (4, 8)
    assert val in (6, 7, 8, 9)
    assert result_code in ("6_Old_Yin", "7_Young_Yang", "8_Young_Yin", "9_Old_Yang")


def test_generate_extraction_prompt_branching():
    generator = ActionCardGeneratorV2()

    # A. 위기 상황
    crisis_transcript = [{"role": "user", "content": "자해 충동이 들고 죽고 싶어요"}]
    crisis_prompts = generator.generate_extraction_prompt(crisis_transcript)
    assert "Stanley-Brown Safety Planning Intervention" in crisis_prompts["system_prompt"]
    assert "109" in crisis_prompts["user_prompt"]
    assert "inner_coping_strategies" in crisis_prompts["user_prompt"]

    # B. 일반 상황
    normal_transcript = [{"role": "user", "content": "이직 준비에 박차를 가하고 싶습니다"}]
    normal_prompts = generator.generate_extraction_prompt(normal_transcript, {"original_hex_name": "건괘"})
    assert "Acceptance and Commitment Therapy (ACT)" in normal_prompts["system_prompt"]
    assert "SMART" in normal_prompts["system_prompt"]
    assert "client_action_pledge" in normal_prompts["user_prompt"]


def test_format_card_markdown_spi_and_act():
    generator = ActionCardGeneratorV2()

    # 1. SPI 카드 렌더링 검증
    spi_data = {
        "is_crisis": True,
        "crisis_warning_signs": "극심한 고립감과 자해 충동",
        "inner_coping_strategies": ["4-7-8 복식 호흡 5분", "얼음 쥐기 감각 접지"],
        "external_contacts_advice": "가장 아끼는 친구 지은이에게 전화하기",
        "emergency_professional_agencies": ["109", "1577-0199", "119"],
        "safe_environment_steps": ["주변 날카로운 물건 치우기", "거실로 나가기"],
    }
    spi_md = generator.format_card_markdown(spi_data)
    assert "마음 안전 안심 카드" in spi_md
    assert "109" in spi_md
    assert "4-7-8 복식 호흡" in spi_md
    assert "얼음 쥐기 감각 접지" in spi_md

    # 2. ACT 마음 전념 카드 렌더링 검증
    act_data = {
        "is_crisis": False,
        "universe_transition": "건(乾)에서 동인(同人)으로 흐르는 연대의 기운",
        "sacred_metaphor": "군자는 날이 저물도록 힘써 힘쓰고 밤에도 경계한다",
        "client_aha_moment": "모든 일을 혼자 통제해야 한다는 완벽주의 아집",
        "client_action_pledge": "나는 오늘 밤 8시에 동료에게 협업 요청 메일을 보낸다",
        "is_smart_compliant": True,
        "counselor_reframing": "혼자의 힘보다 함께하는 지혜가 더 큰 도약을 만듭니다.",
    }
    act_md = generator.format_card_markdown(act_data)
    assert "마음 전념 카드" in act_md
    assert "지행합일" in act_md
    assert "동료에게 협업 요청 메일" in act_md
    assert "완벽주의 아집" in act_md


def test_build_full_schema():
    generator = ActionCardGeneratorV2()
    act_payload = {
        "is_crisis": False,
        "universe_transition": "손(損)에서 익(益)으로의 전환",
        "sacred_metaphor": "덜어냄으로써 비로소 더해진다",
        "client_aha_moment": "불안을 억누르려던 충동",
        "client_action_pledge": "나는 오늘 퇴근 후 10분간 산책하며 생각을 비운다",
        "is_smart_compliant": True,
        "counselor_reframing": "작은 비움이 곧 새로운 채움의 시작입니다.",
    }
    schema = generator.build_full_schema(act_payload, {"original_hex_name": "산택손"})

    assert schema["card_metadata"]["stalks_count"] == 49
    assert schema["juyeok_structure"]["generation_order"] == "Bottom_to_Top_Apartment_Principle"
    assert "su_mathematics" in schema["juyeok_structure"]
    assert schema["psychological_engine"]["smart_goal_validation"] == "Checked"
    assert schema["security_ops"]["encryption"] == "AES-256"
    assert schema["security_ops"]["exif_purged"] is True


from core.db import AsyncSessionLocal


@pytest.mark.asyncio
async def test_write_journal_act_flow():
    async with AsyncSessionLocal() as db_session:
        # 세션 및 턴 생성
        c_session = CounselSession(
            raw_question="진로를 바꾸고 싶은데 두렵습니다.",
            clarified_question="진로 전환의 두려움을 극복하고 첫걸음을 떼는 방안",
            topic_category="커리어",
        )
        db_session.add(c_session)
        await db_session.commit()

        turn = CounselTurn(
            session_id=c_session.id,
            turn_number=1,
            user_message="실패할까 봐 계속 미루게 돼요.",
            agent_response="두려움은 자연스러운 마음입니다. 작은 한 걸음이 변화를 만듭니다.",
            original_hexagram_id=1,
            transformed_hexagram_id=14,
            contextual_mapping="초구 잠룡물용: 지금은 차분히 실력을 기를 때",
        )
        db_session.add(turn)
        await db_session.commit()

        # Mock LLM이 ACT JSON 반환
        mock_client = MagicMock()
        mock_client.complete_json.return_value = {
            "is_crisis": False,
            "universe_transition": "건에서 대유로 흐르는 밝은 조망",
            "sacred_metaphor": "잠룡물용",
            "client_aha_moment": "완벽하지 않으면 시작조차 못한다는 두려움",
            "client_action_pledge": "나는 오늘 저녁 8시에 15분간 희망 분야 채용공고 1개를 분석하겠다",
            "is_smart_compliant": True,
            "counselor_reframing": "내실을 다지는 한 걸음이 곧 큰 소유(大有)로 이어집니다.",
        }

        journal = await write_journal(db_session, c_session.id, client=mock_client)

        assert journal.session_id == c_session.id
        assert "건에서 대유" in journal.summary
        assert "채용공고" in journal.action_items
        assert hasattr(journal, "card_data")
        assert journal.card_data["card_metadata"]["stalks_count"] == 49
        assert "마음 전념 카드" in journal.card_markdown
        assert journal.is_crisis is False


@pytest.mark.asyncio
async def test_write_journal_crisis_spi_flow():
    async with AsyncSessionLocal() as db_session:
        # 위기 상황 대화 세션
        c_session = CounselSession(
            raw_question="너무 힘들어서 쉬고 싶어요.",
            clarified_question="극심한 고통에 대한 호소",
            topic_category="심리위기",
        )
        db_session.add(c_session)
        await db_session.commit()

        turn = CounselTurn(
            session_id=c_session.id,
            turn_number=1,
            user_message="다 끝내고 싶고 죽고 싶어요. 약 먹고 잠들고 싶네요.",
            agent_response="지금 많이 힘드신 상태이시군요. 당신의 안전이 가장 중요합니다.",
        )
        db_session.add(turn)
        await db_session.commit()

        mock_client = MagicMock()
        mock_client.complete_json.return_value = {
            "is_crisis": True,
            "crisis_warning_signs": "극단적 선택 언급 및 무력감",
            "inner_coping_strategies": ["4-7-8 심호흡", "찬물 세안"],
            "external_contacts_advice": "친한 친구에게 전화해 곁에 있어달라고 부탁하기",
            "emergency_professional_agencies": ["109", "119"],
            "safe_environment_steps": ["약물 및 위험 수단 즉시 치우기"],
        }

        journal = await write_journal(db_session, c_session.id, client=mock_client)

        assert "안전계획" in journal.summary
        assert "4-7-8" in journal.action_items
        assert journal.is_crisis is True
        assert "마음 안전 안심 카드" in journal.card_markdown
        assert "109" in journal.card_markdown
