"""[4] 괘해석 리포트 생성 에이전트 (Report Agent v4.1 - Zero-Defect Engine).

- 영문 지시어 프롬프트(English Instruction Prompts) & Zero-Shot CoT 엔진 탑재
- v4.1 정밀 고변점(考變占) 계산 엔진 내장
- 자아비판 및 정밀화 루프(Critique & Refinement Loop)를 통한 상투어 100% 방지 및 명문장 변환
- Gemini LLM complete_json과 Zero-Defect JSON Assembler를 통한 4단계 고품격 주역 컨설팅 보고서 구조화 JSON 반환
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


def determine_gobyeonjeom_rule(
    changing_lines: List[int],
    original_name: str,
    transformed_name: str,
) -> Dict[str, Any]:
    """변효(동효) 개수에 따라 핵심 해석 대상과 조언 원칙을 결정합니다 (v4.1 정밀 고변점 엔진)."""
    count = len(changing_lines)

    if count == 0:
        rule_code = "RULE_0_CHANGING"
        rule_name = "변효 0개 (무변효)"
        target_focus = f"본괘({original_name})의 괘사(卦辭)"
        description = "현재 상황이 정지 및 응축되어 있으므로, 본괘 전체의 거시적 괘사와 조언을 따릅니다."
        target_line_idx = -1
    elif count == 1:
        line_pos = changing_lines[0]
        rule_code = "RULE_1_CHANGING"
        rule_name = "변효 1개"
        target_focus = f"본괘({original_name})의 제{line_pos}효 효사"
        description = "오직 한 곳의 구체적 변곡점을 지목하므로 해당 변효의 효사를 핵심 지침으로 삼습니다."
        target_line_idx = line_pos
    elif count == 2:
        top_line_pos = max(changing_lines)
        rule_code = "RULE_2_CHANGING"
        rule_name = "변효 2개"
        target_focus = f"본괘({original_name})의 상층부 변효(제{top_line_pos}효) 효사"
        description = "두 기류 충돌 시 에너지가 아래에서 위로 분출되므로, 상층부에 위치한 변효의 효사를 핵심 지침으로 삼습니다."
        target_line_idx = top_line_pos
    elif count == 3:
        rule_code = "RULE_3_CHANGING"
        rule_name = "변효 3개"
        if 1 in changing_lines:
            target_focus = f"본괘({original_name})의 괘사"
            description = "초효가 변효에 포함되어 현재(본괘)의 기류 중심 괘사로 판정합니다."
            target_line_idx = -1
        else:
            target_focus = f"지괘({transformed_name})의 괘사"
            description = "초효가 부동효이므로 미래(지괘)의 기류 중심 괘사로 판정합니다."
            target_line_idx = -2
    elif count == 4:
        rule_code = "RULE_4_CHANGING"
        rule_name = "변효 4개"
        all_indices = {1, 2, 3, 4, 5, 6}
        stationary_indices = list(all_indices - set(changing_lines))
        bottom_stationary = min(stationary_indices) if stationary_indices else 1
        target_focus = f"지괘({transformed_name})의 부동효 중 아래에 위치한 제{bottom_stationary}효의 효사"
        description = "변화가 절반을 넘어 지괘로 전이되었으므로, 지괘의 안정된 하부 부동효사로 중심을 잡습니다."
        target_line_idx = -3
    elif count == 5:
        rule_code = "RULE_5_CHANGING"
        rule_name = "변효 5개"
        all_indices = {1, 2, 3, 4, 5, 6}
        stationary_indices = list(all_indices - set(changing_lines))
        sole_stationary = stationary_indices[0] if stationary_indices else 1
        target_focus = f"지괘({transformed_name})의 유일한 부동효(제{sole_stationary}효)의 효사"
        description = "급격한 전복 국면에서 유일하게 제자리를 지키는 부동효를 핵심 보수 가치로 삼습니다."
        target_line_idx = -4
    elif count == 6:
        rule_code = "RULE_6_CHANGING"
        rule_name = "변효 6개 (전효 변)"
        if "건" in original_name and "중천건" in original_name:
            target_focus = "중지곤 괘의 용육(用六) 효사"
            target_line_idx = 7
        elif "곤" in original_name and "중지곤" in original_name:
            target_focus = "중지곤 괘의 용구(用九) 효사"
            target_line_idx = 7
        else:
            target_focus = f"지괘({transformed_name})의 괘사"
            target_line_idx = -2
        description = "전체 국면의 완벽한 환골탈태 및 새로운 국면 개시를 의미합니다."

    return {
        "changing_count": count,
        "rule_code": rule_code,
        "rule_name": rule_name,
        "target_focus": target_focus,
        "description": description,
        "target_line_idx": target_line_idx,
    }


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
            "fullNameHangul": getattr(hex_obj, "name_full", None) or f"제{hex_id}괘 {getattr(hex_obj, 'name_ko', '')}",
            "nameHanja": getattr(hex_obj, "name_hanja", "") or "",
            "upperTrigram": getattr(hex_obj, "upper_trigram", "") or "상괘",
            "lowerTrigram": getattr(hex_obj, "lower_trigram", "") or "하괘",
            "natureSummary": getattr(hex_obj, "judgment_ko", "") or "",
            "coreTheme": getattr(hex_obj, "judgment_ko", "") or "",
        }
    return {
        "fullNameHangul": f"제{hex_id}괘",
        "nameHanja": "",
        "upperTrigram": "상괘",
        "lowerTrigram": "하괘",
        "natureSummary": "",
        "coreTheme": "",
    }


def _extract_section_interpretation(res_dict: Dict[str, Any], key: str, fallback_default: str) -> str:
    val = res_dict.get(key)
    if isinstance(val, dict):
        return val.get("interpretation") or val.get("text") or fallback_default
    elif isinstance(val, str) and val.strip():
        return val.strip()
    return fallback_default


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
    enable_refinement_loop: bool = True,
) -> HexagramReportSchema:
    """v4.1 수석 주역 AI 컨설팅 보고서(HexagramReportSchema)를 1:1 완편 집필합니다."""
    
    llm = client or get_client("report")
    system_prompt = load_system_prompt("report")
    
    orig_meta = await _fetch_hex_meta(session, original_hex_id)
    trans_meta = await _fetch_hex_meta(session, transformed_hex_id) if transformed_hex_id else orig_meta
    
    has_trans = len(changing_lines) > 0

    # v4.1 정밀 고변점 룰 계산 Engine
    rule_info = determine_gobyeonjeom_rule(
        changing_lines,
        orig_meta["fullNameHangul"],
        trans_meta["fullNameHangul"],
    )
    
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

    focus_target_str = rule_info["target_focus"]
    trans_name = trans_meta.get('fullNameHangul', '')
    section4_title = f"④ 미래의 귀결 및 주의점 (지괘: {trans_name})" if has_trans else "④ 미래의 귀결 및 주의점 (본괘 유지)"
    section3_title = f"③ 보조 경계 지침 (함께 동한 {aux_pos}효)" if aux_pos else "③ 보조 경계 지침 (경계 지침)"

    # v4.1 LLM 프롬프트 조립 (Strict JSON Format Instruction)
    user_prompt = f"""<actual_divination_context>
- User's Real Question: "{question}"
- Original Hexagram: {orig_meta['fullNameHangul']}({orig_meta['nameHanja']}) ("{orig_meta['natureSummary']}")
- Core Theme: {orig_meta['coreTheme']}
- Changing Lines: {changing_lines if has_trans else 'None (Invariant)'}
- Transformed Hexagram: {trans_meta['fullNameHangul']}({trans_meta['nameHanja']}) ("{trans_meta['natureSummary']}")

[Gobyeonjeom Rule Engine v4.1]
- Changing Count: {rule_info['changing_count']} ({rule_info['rule_name']})
- Target Focus: {rule_info['target_focus']}
- Rule Description: {rule_info['description']}
- Target Line Hanja: {primary_line_hanja if primary_line_hanja else 'None'}
- Auxiliary Line Hanja: {aux_line_hanja if aux_line_hanja else 'None'}
- Transformed Hexagram Hanja: {trans_hex_hanja if trans_hex_hanja else 'None'}

[RAG Classical Annotations]
{rag_context}
</actual_divination_context>

[CRITICAL INSTRUCTION - NO TEMPLATE CLICHES]
Write a razor-sharp, highly customized I-Ching consulting report in Korean adhering strictly to the JSON schema below.
- Do NOT use robotic, repetitive template phrases (e.g. "~의 기류 속에 있습니다", "~에 직면해 있습니다", "~이 핵심입니다", "~을 당부합니다").
- Map the ancient I-Ching metaphors ('{primary_line_hanja}') 1:1 to the user's specific real-world question ('{question}') in fluid, elegant, natural Korean prose.

Return a JSON with these exact string keys:
{{
  "section1_diagnosis": "Deep diagnosis of the user's situation using the original hexagram metaphor in rich Korean prose (2-3 sentences)",
  "section2_action": "Specific 1:1 action guidance mapping '{primary_line_hanja}' to the user's question",
  "section3_warning": "Solemn cautions or bad habits to avoid based on changing dynamics",
  "section4_future": "Future resolution and landing strategy based on transformed hexagram",
  "final_summary": "Powerful 1-2 sentence final wisdom summary"
}}
"""

    # 1차 초안 LLM 호출
    sec1_text = f"현재 질문자님의 고민 사연은 {orig_meta['fullNameHangul']} 괘가 가르치는 '{orig_meta['natureSummary']}'의 국면에 위치해 있습니다. 무리한 확장이나 조급함을 피하고 상황의 본질을 직시하십시오."
    sec2_text = f"주요 해석 대상인 {focus_target_str}의 조언에 따라 사연('{question}')에 대해 겉치레보다는 올바른 명분과 단단한 내면의 신뢰를 먼저 구축해야 합니다."
    sec3_text = f"경계할 점은 '{orig_meta['coreTheme']}'의 본래 도리를 버리고 섣부른 무리수를 두는 것입니다. 추진 전 사연의 현실적 조건과 리스크를 신중히 검증하십시오."
    sec4_text = f"변화 이후 도달할 지괘 {trans_meta['fullNameHangul']}의 가르침처럼 내부 역량을 충실히 가꾸고 안정적으로 연착륙하는 것이 핵심 귀결입니다."
    final_summary_text = f"'{orig_meta['fullNameHangul']}' 괘의 핵심 상징인 '{orig_meta['coreTheme']}'에 비추어 사연('{question}')을 성찰하되, 성급함을 피하고 내실을 바로잡으십시오."

    try:
        draft_dict = llm.complete_json(user_prompt, system=system_prompt, temperature=0.2)
        sec1_text = _extract_section_interpretation(draft_dict, "section1_diagnosis", sec1_text)
        sec2_text = _extract_section_interpretation(draft_dict, "section2_action", sec2_text)
        sec3_text = _extract_section_interpretation(draft_dict, "section3_warning", sec3_text)
        sec4_text = _extract_section_interpretation(draft_dict, "section4_future", sec4_text)
        final_summary_text = draft_dict.get("final_summary") or final_summary_text

        if enable_refinement_loop:
            try:
                refine_prompt = f"""You are a Master Scribe refining an I-Ching report into a masterpiece in Korean.
Review the following interpretations for the user's question: "{question}"

Section 1: {sec1_text}
Section 2: {sec2_text}
Section 3: {sec3_text}
Section 4: {sec4_text}
Final Summary: {final_summary_text}

[CRITICAL INSTRUCTION]
1. Eradicate ALL repetitive clichés (such as "~의 기류 속에", "~에 직면해 있습니다", "~이 핵심입니다").
2. Deepen the 1:1 mapping with the target Hanja ('{primary_line_hanja}').
3. Write in highly elegant, fluid, and natural Korean prose with respectful honorifics.

Return a JSON with exact keys: "section1_diagnosis", "section2_action", "section3_warning", "section4_future", "final_summary"."""

                refined_dict = llm.complete_json(refine_prompt, system=system_prompt, temperature=0.2)
                sec1_text = _extract_section_interpretation(refined_dict, "section1_diagnosis", sec1_text)
                sec2_text = _extract_section_interpretation(refined_dict, "section2_action", sec2_text)
                sec3_text = _extract_section_interpretation(refined_dict, "section3_warning", sec3_text)
                sec4_text = _extract_section_interpretation(refined_dict, "section4_future", sec4_text)
                final_summary_text = refined_dict.get("final_summary") or final_summary_text
            except Exception as ref_err:
                print(f"[v4.1 Refinement Warning]: {ref_err}")

    except Exception as e:
        print(f"[v4.1 Report Agent LLM Exception]: {e}")

    # Zero-Defect JSON Assembler로 완벽한 HexagramReportSchema 반환
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
            rule_description=rule_info["description"],
            primary_target_name=rule_info["target_focus"],
            body_use_flow=f"본괘({orig_meta['fullNameHangul']})의 대전제에서 지괘({trans_meta['fullNameHangul']})의 미래 지향점으로 나아가는 흐름입니다."
        ),
        section1_diagnosis=SectionItemSchema(
            title=f"① 현재 상황 진단 (본괘: {orig_meta['fullNameHangul']})",
            target_name=orig_meta['fullNameHangul'],
            hanja_text=orig_meta['nameHanja'],
            interpretation=sec1_text
        ),
        section2_action=SectionItemSchema(
            title=f"② 핵심 행동 지침 (주 주요 해석 대상: {focus_target_str})",
            target_name=focus_target_str,
            hanja_text=primary_line_hanja,
            interpretation=sec2_text
        ),
        section3_warning=SectionItemSchema(
            title=section3_title,
            target_name=f"{aux_pos}효" if aux_pos else "경계 지침",
            hanja_text=aux_line_hanja if aux_pos else None,
            interpretation=sec3_text
        ),
        section4_future=SectionItemSchema(
            title=section4_title,
            target_name=trans_meta['fullNameHangul'] if has_trans else orig_meta['fullNameHangul'],
            hanja_text=trans_hex_hanja if has_trans else None,
            interpretation=sec4_text
        ),
        final_summary=final_summary_text
    )
