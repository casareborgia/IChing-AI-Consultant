"""[+1] 저널 에이전트 (Journal Agent) v2.0.

- 상담 세션 종료 후 ACT(수용전념치료) 전념 행동 기반 실천다짐카드 및 위기(SPI) 개입 분기 처리
- Stanley-Brown 안전계획(SPI) 하드스톱 및 임상 윤리 리프레이밍 준수
- 49개 산가지(其用四十有九) 수리·철학적 구조화(象·數·辭·義) 및 보안(EXIF 유출 방지) 결합
- JournalEntry DB 레코드 생성 및 세션 상태 'completed' 변경 (기존 인터페이스 및 테스트 100% 하위 호환)
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.action_card_generator_v2 import ActionCardGeneratorV2
from core.llm import LLMClient, get_client
from core.models.counsel import CounselSession, CounselTurn, JournalEntry
from schemas.counsel import JournalEntrySchema

logger = logging.getLogger(__name__)


async def write_journal(
    session: AsyncSession,
    counsel_session_id: str,
    *,
    client: Optional[LLMClient] = None,
) -> JournalEntry:
    """종료된 상담 세션의 대화 내용을 분석하여 ACT 행동 전념 카드 또는 SPI 안전계획 카드를 생성하고 DB에 저장합니다.

    Args:
        session: SQLAlchemy 비동기 세션
        counsel_session_id: 상담 세션 ID
        client: 주입할 LLM 클라이언트

    Returns:
        저장된 JournalEntry ORM 객체 (card_data, card_markdown 런타임 속성 포함)
    """
    # 1. 세션 및 턴 조회
    c_session = (
        await session.execute(
            select(CounselSession).where(CounselSession.id == counsel_session_id)
        )
    ).scalar_one()

    turns = (
        await session.execute(
            select(CounselTurn)
            .where(CounselTurn.session_id == counsel_session_id)
            .order_by(CounselTurn.turn_number.asc())
        )
    ).scalars().all()

    # 2. 녹취록(transcript) 및 괘 맥락(report_info) 구성
    transcript: List[Dict[str, str]] = []
    report_info: Dict[str, Any] = {
        "raw_question": c_session.raw_question,
        "clarified_question": c_session.clarified_question,
        "topic_category": c_session.topic_category or "기타",
    }

    for t in turns:
        transcript.append({"role": "user", "content": t.user_message})
        transcript.append({"role": "assistant", "content": t.agent_response})
        if t.original_hexagram_id:
            report_info["original_hex_num"] = t.original_hexagram_id
        if t.transformed_hexagram_id:
            report_info["resulting_hex_num"] = t.transformed_hexagram_id
        if t.contextual_mapping:
            report_info["target_line_text"] = t.contextual_mapping

    # 3. ActionCardGeneratorV2를 통한 위기 감지 및 동적 프롬프트 조립
    generator = ActionCardGeneratorV2()
    is_crisis = generator.check_crisis_signals(transcript)
    prompts = generator.generate_extraction_prompt(transcript, report_info)

    llm = client or get_client(role="journal")

    summary = ""
    key_insights = ""
    action_items = None
    card_payload: Dict[str, Any] = {}

    try:
        data = llm.complete_json(
            prompts["user_prompt"],
            system=prompts["system_prompt"],
            temperature=0.2,
            max_tokens=1024,
        )

        # A. 신규 Action Card 포맷 여부 확인
        if "universe_transition" in data or "crisis_warning_signs" in data or "client_action_pledge" in data:
            card_payload = data
            if data.get("is_crisis", False) or is_crisis:
                is_crisis = True
                summary = f"위기 신호 감지로 인한 Stanley-Brown 안전계획(SPI) 수립: {data.get('crisis_warning_signs', '위기 징후 감지')}"
                key_insights = f"사적 신뢰망 지침: {data.get('external_contacts_advice', '전문 기관 및 지인 연결')}"
                strategies = data.get("inner_coping_strategies", [])
                action_items = f"내적 안심 대처: {', '.join(strategies)}" if strategies else "즉각 대처 수칙 실천"
            else:
                summary = data.get("universe_transition") or f"질문: {c_session.clarified_question or c_session.raw_question}에 대한 주역 마음 전념 성찰"
                aha = data.get("client_aha_moment", "")
                reframe = data.get("counselor_reframing", "")
                key_insights = f"내려놓은 아집: {aha}. {reframe}".strip()
                action_items = data.get("client_action_pledge")
        else:
            # B. 기존 레거시 포맷 (summary, key_insights, action_items) 호환
            summary = data.get("summary", "주역 괘를 바탕으로 마음을 성찰한 상담 세션입니다.")
            key_insights = data.get("key_insights", "상황을 주체적으로 바라보는 지혜를 나눔.")
            action_items = data.get("action_items")

            if is_crisis:
                card_payload = {
                    "is_crisis": True,
                    "crisis_warning_signs": summary,
                    "inner_coping_strategies": ["복식 호흡 (4-7-8)", "감각 접지 (5-4-3-2-1)"],
                    "external_contacts_advice": "신뢰할 수 있는 친구나 가족에게 지금 나의 상태를 알리세요.",
                    "emergency_professional_agencies": [
                        "정신건강 위기상담전화: 109 (24시간 무상 운영)",
                        "보건복지상담센터: 129",
                        "긴급 구조전화: 119 또는 112"
                    ],
                    "safe_environment_steps": ["주변의 위험 물건을 즉시 치우고 안전한 장소로 이동하세요."]
                }
            else:
                card_payload = {
                    "is_crisis": False,
                    "universe_transition": summary,
                    "sacred_metaphor": "스스로 힘써 쉬지 아니함(自强不息)",
                    "client_aha_moment": key_insights,
                    "client_action_pledge": action_items or "오늘 10분간 마음을 정돈하고 작은 실천을 행한다.",
                    "is_smart_compliant": True,
                    "counselor_reframing": key_insights
                }

    except Exception as exc:
        logger.warning("저널 에이전트 LLM 처리 중 예외 발생, 폴백 적용: %s", exc)
        if is_crisis:
            summary = "긴급 안전계획(SPI) 수립: 위기 징후 감지 및 전문 기관 연계"
            key_insights = "정신건강 위기상담전화 109 및 사적 신뢰망을 통한 생명 존중 보호"
            action_items = "호흡 안정화 및 위험 요소 배제"
            card_payload = {
                "is_crisis": True,
                "crisis_warning_signs": "상담 대화 내 위기 징후 포착",
                "inner_coping_strategies": ["복식 호흡 (4-7-8)", "감각 접지 (5-4-3-2-1)"],
                "external_contacts_advice": "신뢰할 수 있는 가족이나 친구에게 도움을 청하세요.",
                "emergency_professional_agencies": [
                    "정신건강 위기상담전화: 109 (24시간)",
                    "보건복지상담센터: 129",
                    "긴급 구조전화: 119 또는 112"
                ],
                "safe_environment_steps": ["위험 요소를 주변에서 멀리 치우세요."]
            }
        else:
            summary = f"질문: {c_session.clarified_question or c_session.raw_question}에 대한 주역 성찰 상담"
            key_insights = "괘상의 흐름을 바탕으로 지행합일의 실천과 내면의 평온을 추구함."
            action_items = "오늘 10분간 호흡을 가다듬고 자신의 선택을 점검하기"
            card_payload = {
                "is_crisis": False,
                "universe_transition": summary,
                "sacred_metaphor": "변화 속에서 중심을 잃지 아니함",
                "client_aha_moment": key_insights,
                "client_action_pledge": action_items,
                "is_smart_compliant": True,
                "counselor_reframing": key_insights
            }

    # 4. 풀 스키마(주역 49산가지 수리 구조 + 보안 ops) 빌드
    full_schema = generator.build_full_schema(card_payload, report_info)
    card_markdown = full_schema["card_markdown"]

    # 5. 기존 저널이 있는지 확인 후 갱신 또는 신규 생성
    existing_journal = (
        await session.execute(
            select(JournalEntry).where(JournalEntry.session_id == counsel_session_id)
        )
    ).scalar_one_or_none()

    if existing_journal:
        existing_journal.summary = summary
        existing_journal.key_insights = key_insights
        existing_journal.action_items = action_items
        journal_entry = existing_journal
    else:
        journal_entry = JournalEntry(
            session_id=counsel_session_id,
            summary=summary,
            key_insights=key_insights,
            action_items=action_items,
        )
        session.add(journal_entry)

    c_session.status = "completed"
    await session.commit()
    await session.refresh(journal_entry)

    # 6. 런타임 확장 속성 바인딩
    setattr(journal_entry, "card_data", full_schema)
    setattr(journal_entry, "card_markdown", card_markdown)
    setattr(journal_entry, "is_crisis", is_crisis)

    return journal_entry
