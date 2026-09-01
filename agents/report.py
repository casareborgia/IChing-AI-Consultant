"""[4] 괘해석 리포트 생성 에이전트 (Report Agent).

- 내담자 질문, 도출된 괘상, 수리 배열, 주자 고변점 룰, 효사 한문 원문, RAG 주석 수집
- Gemini LLM을 통해 4단계 고품격 주역 컨설팅 보고서 구조화 JSON 생성
"""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.llm import LLMClient, get_client
from core.models.hexagram import Hexagram, Line
from core.prompts import load_system_prompt
from schemas.report import (
    HexagramReportSchema,
    QuestionSettingSchema,
    HexagramCastingSchema,
    LineCastingItem,
    FocusAndBodyUseSchema,
    SectionItemSchema,
)


def _get_line_name(pos: int) -> str:
    names = ["1효 (초효)", "2효 (이효)", "3효 (삼효)", "4효 (사효)", "5효 (오효)", "6효 (상효)"]
    return names[pos - 1] if 1 <= pos <= 6 else f"{pos}효"


async def _fetch_line_hanja(session: AsyncSession, hex_id: int, pos: int) -> str:
    """DB에서 괘의 해당 효사 한자 원문을 조회합니다."""
    line = (
        await session.execute(
            select(Line).where(
                Line.hexagram_id == hex_id,
                Line.line_number == pos,
            )
        )
    ).scalar_one_or_none()
    if line:
        return line.statement_text or line.statement_ko or ""
    return ""


async def _fetch_hex_statement_hanja(session: AsyncSession, hex_id: int) -> str:
    """DB에서 괘의 괘사 한자 원문 및 대상전을 조회합니다."""
    hex_obj = (
        await session.execute(select(Hexagram).where(Hexagram.id == hex_id))
    ).scalar_one_or_none()
    if hex_obj:
        text = hex_obj.judgment_text or ""
        if hex_obj.xiang_text:
            text += f" (대象: {hex_obj.xiang_text})"
        return text
    return ""


async def _fetch_hex_meta(session: AsyncSession, hex_id: int) -> Dict[str, str]:
    """DB에서 괘의 풀네임, 한자명, 괘사 풀이를 조회합니다."""
    hex_obj = (
        await session.execute(select(Hexagram).where(Hexagram.id == hex_id))
    ).scalar_one_or_none()
    if hex_obj:
        return {
            "fullNameHangul": hex_obj.name_full or f"제{hex_id}괘 {hex_obj.name_ko}",
            "nameHanja": hex_obj.name_hanja or "",
            "natureSummary": hex_obj.judgment_ko or "",
            "coreTheme": hex_obj.judgment_ko or "",
        }
    return {
        "fullNameHangul": f"제{hex_id}괘",
        "nameHanja": "",
        "natureSummary": "",
        "coreTheme": "",
    }


async def run_report_agent(
    session: AsyncSession,
    *,
    question: str,
    original_hex_id: int,
    transformed_hex_id: int,
    changing_lines: List[int],
    lines_val: List[int],  # 예: [7, 8, 9, 8, 9, 7]
    focus_rule: Dict[str, Any],
    evidences: List[Dict[str, Any]],
    client: Optional[LLMClient] = None,
) -> HexagramReportSchema:
    """수석 주역 AI 컨설팅 보고서(HexagramReportSchema)를 1:1 완편 집필합니다."""
    
    llm = client or get_client("report")
    system_prompt = load_system_prompt("report")
    
    orig_meta = await _fetch_hex_meta(session, original_hex_id)
    trans_meta = await _fetch_hex_meta(session, transformed_hex_id) if transformed_hex_id else orig_meta
    
    has_trans = len(changing_lines) > 0
    
    # 6효 라인 메타 구성
    casting_items: List[LineCastingItem] = []
    for idx, val in enumerate(lines_val):
        pos = idx + 1
        is_changing = pos in changing_lines
        if val == 7:
            type_ko, sym, note = "소양", "⚊", "변하지 않는 양효"
        elif val == 8:
            type_ko, sym, note = "소음", "⚋", "변하지 않는 음효"
        elif val == 9:
            type_ko, sym, note = "노양", "⚊○", "동효(변효) (양에서 음으로 변함)"
        elif val == 6:
            type_ko, sym, note = "노음", "⚋✕", "동효(변효) (음에서 양으로 변함)"
        else:
            type_ko, sym, note = "양효", "⚊", "양효"
            
        casting_items.append(LineCastingItem(
            position=pos,
            name=_get_line_name(pos),
            value=val,
            line_type_ko=type_ko,
            symbol=sym,
            is_changing=is_changing,
            note=note,
        ))

    # 주요 초점 효 한자 원문 조회
    target_lines = focus_rule.get("target_line_numbers") or []
    primary_target_pos = target_lines[0] if target_lines else None
    
    primary_line_hanja = ""
    if primary_target_pos:
        primary_line_hanja = await _fetch_line_hanja(session, original_hex_id, primary_target_pos)
    else:
        primary_line_hanja = await _fetch_hex_statement_hanja(session, original_hex_id)

    # 보조 동효 한자 원문 조회
    aux_pos = None
    aux_line_hanja = ""
    if len(changing_lines) > 1 and primary_target_pos:
        for c in changing_lines:
            if c != primary_target_pos:
                aux_pos = c
                break
    if aux_pos:
        aux_line_hanja = await _fetch_line_hanja(session, original_hex_id, aux_pos)

    # 지괘 괘사/대상전 한자 원문 조회
    trans_hex_hanja = ""
    if has_trans:
        trans_hex_hanja = await _fetch_hex_statement_hanja(session, transformed_hex_id)

    # RAG 고전 주석 정리
    evidence_texts = []
    for e in evidences[:3]:
        evidence_texts.append(f"[{e.get('source_title', '고전주석')}] {e.get('content', '')}")
    rag_context = "\n".join(evidence_texts) if evidence_texts else "기본 고전 주석 기반"

    # LLM 프롬프트에 제공할 주역 컨설팅 컨텍스트
    user_prompt = f"""
[내담자 고민 질문]
"{question}"

[1. 괘 도출 수리 메타데이터]
- 본괘: {orig_meta['fullNameHangul']}({orig_meta['nameHanja']}) - 상괘:{orig_meta['upperTrigram']}, 하괘:{orig_meta['lowerTrigram']} ("{orig_meta['natureSummary']}")
- 핵심 테마: {orig_meta['coreTheme']}
- 변효 위치: {changing_lines if has_trans else '없음 (불변괘)'}
- 지괘: {trans_meta['fullNameHangul']}({trans_meta['nameHanja']}) - "{trans_meta['natureSummary']}" ({trans_meta['coreTheme']})

[2. 주자 고변점 및 체용 메타데이터]
- 규칙 설명: {focus_rule.get('description_ko', '')}
- 주요 해석 대상: {orig_meta['fullNameHangul']} 괘 {primary_target_pos}효 (또는 괘사)
- 주요 해석 대상 한문 원문: {primary_line_hanja}
- 보조 동한 효({aux_pos}효) 한문 원문: {aux_line_hanja if aux_pos else '없음'}
- 지괘({trans_meta['fullNameHangul']}) 한문 원문/대상전: {trans_hex_hanja}

[3. RAG 고전 주석 뭉치]
{rag_context}

위 입력 데이터를 철저히 융합하여 내담자의 고민 사연("{question}")에 100% 1:1 맞춤 응답하는 최고의 주역 AI 컨설팅 리포트를 집필하여 HexagramReportSchema JSON 형식으로 반환하십시오.
"""

    try:
        res = await llm.generate_structured(
            system_prompt=system_prompt,
            prompt=user_prompt,
            schema_class=HexagramReportSchema,
        )
        return res
    except Exception as e:
        # LLM 실패 시 백업 기본 구조 생성 (안전망)
        focus_target_str = f"{orig_meta['fullNameHangul']} 괘 {primary_target_pos}효사" if primary_target_pos else f"{orig_meta['fullNameHangul']} 괘사"
        trans_name = trans_meta.get('fullNameHangul', '')
        section4_title = f"④ 미래의 귀결 및 주의점 (지괘: {trans_name})" if has_trans else "④ 미래의 귀결 및 주의점 (본괘 유지)"
        section3_title = f"③ 보조 경계 지침 (함께 동한 {aux_pos}효)" if aux_pos else "③ 보조 경계 지침 (경계 지침)"

        return HexagramReportSchema(
            question_setting=QuestionSettingSchema(
                question=question,
                mindset_rule="질문자는 사리사욕이나 무분별한 호기심을 비우고, 무념무상의 경건한 마음으로 단 한 번만 점을 치는 재삼덕 금기 원칙을 준수하며 점을 쳤습니다."
            ),
            hexagram_casting=HexagramCastingSchema(
                lines=casting_items,
                original_hex_id=original_hex_id,
                original_name_full=orig_meta['fullNameHangul'],
                original_name_hanja=orig_meta['nameHanja'],
                original_upper_trigram=orig_meta['upperTrigram'],
                original_lower_trigram=orig_meta['lowerTrigram'],
                original_summary=orig_meta['natureSummary'],
                has_transformation=has_trans,
                transformed_hex_id=transformed_hex_id if has_trans else None,
                transformed_name_full=trans_meta['fullNameHangul'] if has_trans else None,
                transformed_name_hanja=trans_meta['nameHanja'] if has_trans else None,
                transformed_summary=trans_meta['natureSummary'] if has_trans else None,
            ),
            focus_and_body_use=FocusAndBodyUseSchema(
                changing_count=len(changing_lines),
                rule_description=focus_rule.get('description_ko', '본괘와 지괘의 고변점 규칙 적용'),
                primary_target_name=focus_target_str,
                body_use_flow=f"본괘({orig_meta['fullNameHangul']})의 대전제에서 지괘({trans_meta['fullNameHangul']})의 미래 지향점으로 나아가는 흐름입니다."
            ),
            section1_diagnosis=SectionItemSchema(
                title=f"① 현재 상황 진단 (본괘: {orig_meta['fullNameHangul']})",
                target_name=orig_meta['fullNameHangul'],
                hanja_text=orig_meta['nameHanja'],
                interpretation=f"현재 사연은 {orig_meta['fullNameHangul']}의 '{orig_meta['natureSummary']}' 시공간적 흐름 속에 놓여 있습니다. '{orig_meta['coreTheme']}'의 성격에 따라 섣부른 조급함을 피하고 내실을 다져야 합니다."
            ),
            section2_action=SectionItemSchema(
                title=f"② 핵심 행동 지침 (주 주요 해석 대상: {focus_target_str})",
                target_name=focus_target_str,
                hanja_text=primary_line_hanja,
                interpretation=f"주 해석 대상의 이치에 따라 겉치레보다는 진실함과 명확한 비전을 세워 신뢰를 먼저 확보하는 것이 핵심 실천 조언입니다."
            ),
            section3_warning=SectionItemSchema(
                title=section3_title,
                target_name=f"{aux_pos}효" if aux_pos else "경계 지침",
                hanja_text=aux_line_hanja if aux_pos else None,
                interpretation="조급하게 성급한 확장을 서두르기보다 실행 전 치밀하게 조건과 계획을 검증한 뒤 나아가야 합니다."
            ),
            section4_future=SectionItemSchema(
                title=section4_title,
                target_name=trans_meta['fullNameHangul'] if has_trans else orig_meta['fullNameHangul'],
                hanja_text=trans_hex_hanja if has_trans else None,
                interpretation=f"변화 이후에는 {trans_meta['fullNameHangul']}의 이치처럼 내부 역량을 정비하고 내실 다지기에 집중하는 연착륙 전략이 성패의 열쇠입니다."
            ),
            final_summary=f"'{orig_meta['fullNameHangul']}'의 흐름 속에서 고민하시는 방향을 추진하되, 조급한 무리수를 삼가고 계획을 신중히 검증하십시오. 지괘({trans_meta['fullNameHangul']})의 가르침처럼 내실 정비와 신뢰 확보에 집중하는 것이 승리의 열쇠입니다."
        )
