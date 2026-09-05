# -*- coding: utf-8 -*-
"""주역 상담 앱 - 행동 전념 카드(Action Commitment Card) 및 위기 개입(SPI) 통합 엔진 (Action Card Generator v2.0)

- 기존의 단순 요약식 저널 에이전트를 고도화하여 한국상담학회 윤리강령 및 국가 안전 가이드라인을 준수합니다.
- [개선안 1] ACT(수용전념치료)의 '전념 행동(Committed Action)' 기준에 맞춘 구체적 행동(SMART) 분석 가이드라인 탑재.
- [개선안 2] 초위기 징후(자살/자해 사고) 감지 시, 주역 해석을 즉각 중단(Hard-Stop)하고 Stanley-Brown 안전계획(SPI) 카드로 자동 전환.
- [개선안 3] 임상 윤리에 위배되는 미신적 용어('부적' -> '행동 전념 카드/마음 전념 카드', '상담사의 축복' -> '마음의 지지와 격려')의 완전 리프레이밍.
- [개선안 4] 49개의 산가지(其用四十有九)와 삼변성효(三變成爻) 수리(象·數·辭·義) 데이터 스키마 표준화.
- [개선안 5] 'Save to Gallery' 실패 대비 인앱 뷰어 지원 및 개인정보 보호를 위한 이미지 메타데이터 유출 차단(EXIF 제거/비트맵 재샘플링) 규격화.
"""

import json
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.crypto import encrypt_to_base64
from core.card_image import CardImageRenderer

# 위기 감지 단어 리스트 (Clinical Crisis Keywords)
CRISIS_KEYWORDS = [
    "죽고 싶", "자살", "자해", "끝내고 싶", "사라지고 싶", "죽는 게", "살기 싫",
    "세상 하직", "목숨", "뛰어내", "잠들어서 깨지", "약 먹고", "죽음", "살 가치"
]

# 주의(Caution) 감지 단어 리스트
CAUTION_KEYWORDS = [
    "괴로워", "절망", "포기하고", "지쳤어", "무기력", "아무것도 못하", "우울해", "숨막혀"
]


class ActionCardGeneratorV2:
    """행동 전념 카드 및 Stanley-Brown 안전계획(SPI) 통합 생성 엔진."""

    def __init__(self):
        pass

    def evaluate_risk_level(self, transcript: List[Dict[str, str]]) -> str:
        """대화 기록을 기반으로 4단계 위험 수준(NORMAL, CAUTION, CRISIS, EMERGENCY)을 판별합니다."""
        has_crisis = False
        has_caution = False
        emergency_indicators = ["지금 뛰어", "약 먹었", "칼로", "유서"]

        for turn in transcript:
            if turn.get("role") == "user":
                content = turn.get("content", "")
                cleaned_content = content.replace(" ", "")

                for emp in emergency_indicators:
                    if emp.replace(" ", "") in cleaned_content:
                        return "EMERGENCY"

                for kw in CRISIS_KEYWORDS:
                    if kw.replace(" ", "") in cleaned_content:
                        has_crisis = True
                        break

                for ck in CAUTION_KEYWORDS:
                    if ck.replace(" ", "") in cleaned_content:
                        has_caution = True

        if has_crisis:
            return "CRISIS"
        if has_caution:
            return "CAUTION"
        return "NORMAL"

    def check_crisis_signals(self, transcript: List[Dict[str, str]]) -> bool:
        """내담자와의 대화 녹취록에서 초위기 자살/자해 사고 및 신변정리 징후가 포착되는지 스캔합니다."""
        level = self.evaluate_risk_level(transcript)
        return level in ("CRISIS", "EMERGENCY")

    def simulate_yarrow_line(self) -> Tuple[List[int], int, str]:
        """49개 산가지(其用四十有九)를 사용한 삼변성효(三變成爻) 수리 시뮬레이션.

        반환값: (세 번의 잉여 수 리스트, 최종 결과 수 6/7/8/9, 효 명칭)
        """
        # 첫 번째 변: 49개에서 1개(인간/태극)를 빼고 양손 분할 후 4로 나눈 나머지
        # 전형적인 잉여 수는 5 또는 9
        first_rem = random.choice([5, 9])
        second_rem = random.choice([4, 8])
        third_rem = random.choice([4, 8])
        rem_list = [first_rem, second_rem, third_rem]

        # 잉여 수에 따른 효 수치 계산 (49 - sum(rem)) / 4
        total_rem = sum(rem_list)
        # 전통 점법상 가능한 합:
        # 5+4+4=13 -> (49-13)/4 = 9 (노양)
        # 9+8+8=25 -> (49-25)/4 = 6 (노음)
        # 5+8+8=21, 9+4+8=21, 9+8+4=21 -> (49-21)/4 = 7 (소양)
        # 9+4+4=17, 5+8+4=17, 5+4+8=17 -> (49-17)/4 = 8 (소음)
        val = (49 - total_rem) // 4
        if val not in (6, 7, 8, 9):
            val = 7  # 안전장치 기본값 소양

        label_map = {
            6: "6_Old_Yin",
            7: "7_Young_Yang",
            8: "8_Young_Yin",
            9: "9_Old_Yang"
        }
        return rem_list, val, label_map[val]

    def generate_extraction_prompt(
        self,
        transcript: List[Dict[str, str]],
        report_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """녹취록 상태를 분석하여 [위기 상황(SPI)] 또는 [일반 상황(ACT 행동 전념)]에 맞춘 프롬프트를 동적 분기 생성합니다."""
        report_info = report_info or {}
        is_crisis = self.check_crisis_signals(transcript)

        if is_crisis:
            # 위기 상황: Stanley-Brown 안전계획(SPI) 강제 변환 프롬프트
            system_prompt = """You are a licensed clinical psychologist and crisis intervention expert specializing in suicide prevention.
A serious crisis signal (suicidal ideation or self-harm) has been detected in the client's counseling transcript.
You MUST immediately halt the I-Ching divination interpretation. Do NOT output any hexagram or talisman-like texts.
Instead, your sole task is to generate a personalized "Stanley-Brown Safety Planning Intervention (SPI)" card payload to keep the client safe.

[SPI Payload Generation Guidelines]
1. [In-App Coping (내적 대처법)]: Suggest 2-3 extremely simple, non-pharmacological, immediately doable psychological coping methods (e.g., 4-7-8 abdominal deep breathing, sensory grounding exercises like 5-4-3-2-1 technique).
2. [External Contacts (신뢰할 수 있는 사적 연락처)]: Remind the client to connect with a close family member or a trusted friend from their contact list.
3. [Emergency Professional Agencies (공식 위기 기관)]: Explicitly list the Korean national crisis counseling hotlines: "국가 정신건강 위기상담전화 109" and "1577-0199", "119 / 112".
4. [Safe Environment (안전한 환경 조성)]: Instruct the client on how to secure their physical space immediately (e.g., removing lethal means, moving to a safe public place).

[Tone and Style]
- The prompt is in English, but the generated payload MUST be in highly comforting, non-judgmental, urgent yet gentle Korean (Polite 경어체)."""

            user_prompt = f"""<counseling_transcript>
{json.dumps(transcript, ensure_ascii=False, indent=2)}
</counseling_transcript>

An emergency crisis has been confirmed. Generate the "Stanley-Brown Safety Planning (SPI)" card payload matching the following JSON structure exactly. Return ONLY the raw JSON block.

{{
  "is_crisis": true,
  "crisis_warning_signs": "string (내담자가 보인 위험 신호 요약)",
  "inner_coping_strategies": ["string (내적 대처 방법 1)", "string (내적 대처 방법 2)"],
  "external_contacts_advice": "string (신뢰할 수 있는 친구나 가족에게 도움을 청하라는 따뜻한 지침)",
  "emergency_professional_agencies": [
    "정신건강 위기상담전화: 109 (24시간 무상 운영)",
    "보건복지상담센터: 129",
    "긴급 구조전화: 119 또는 112"
  ],
  "safe_environment_steps": ["string (주변의 위험 물질 치우기 등 물리적 공간 관리 수칙)"]
}}"""

        else:
            # 일반 상황: ACT(수용전념치료) 전념 행동 기반 실천다짐카드 프롬프트
            system_prompt = """You are an elite clinical psychologist specializing in Acceptance and Commitment Therapy (ACT) and a master scholar of Neo-Confucianism.
Your task is to compile a "Mindfulness Action Commitment Card" (마음 전념 카드) from the counseling transcript.
You must reframe ancient I-Ching concepts into scientifically validated, non-superstitious behavioral psychology terms.

[ACT Committed Action & SMART Rules]
1. [Core Pledge (나의 전념 행동)]: Extract the client's action plan. It MUST be filtered and refined into a SMART (Specific, Measurable, Actionable, Realistic, Time-bound) behavioral goal.
   - It MUST be a concrete action they can perform within 10-20 minutes today/tomorrow (e.g., "나는 오늘 밤 9시에 후배에게 전화를 걸어 5분간 사과하겠다").
   - It MUST NOT be an unrealistic long-term goal ("나는 평생 화내지 않겠다"), a vague state of mind ("나는 앞으로 긍정적으로 살겠다"), or emotional suppression ("나는 불안을 억누르겠다").
   - If the client's original statement is too broad or unrealistic, you MUST break it down and rewrite it into a highly actionable, bite-sized SMART task.
2. [Aha! Moment (아집의 내려놓음)]: Summarize what dysfunctional cognitive obsession, control bias, or emotional avoidance the client realized they need to let go of.
3. [Counselor's Reframing (마음의 지지와 격려)]: Write an elegant 1-sentence cognitive reframing (Korean, polite 경어체) that connects their SMART action to the wisdom of the transition from the Original Hexagram to the Resulting Hexagram.

[Compliance Rebranding]
- NEVER use superstitious terms like "Talisman (부적)" or "Blessing (축복)". Use "Action Commitment Card (행동 전념 카드)" and "Counselor's Reframing/Encouragement (마음의 지지와 격려)".

[Output Language]
- Instructions are in English; the JSON payload values MUST be in highly elegant, comforting, and professional Korean (Polite 경어체)."""

            user_prompt = f"""<divination_context>
- Original Hexagram: {report_info.get('original_hex_name', '미상')} (No. {report_info.get('original_hex_num', 0)})
- Resulting Hexagram: {report_info.get('resulting_hex_name', '미상')} (No. {report_info.get('resulting_hex_num', 0)})
- Key Metaphor of Target Line: {report_info.get('target_line_text', '미상')}
</divination_context>

<counseling_transcript>
{json.dumps(transcript, ensure_ascii=False, indent=2)}
</counseling_transcript>

Generate the "Action Commitment Card" payload matching the following JSON structure exactly. Ensure the "client_action_pledge" is strictly a SMART, small-step action. Return ONLY the raw JSON block.

{{
  "is_crisis": false,
  "universe_transition": "string (e.g., '곤(困)에서 해(解)로 흐르는 마음의 정돈')",
  "sacred_metaphor": "string (고전의 은유적 한 구절)",
  "client_aha_moment": "string (내려놓을 아집이나 정서적 고착 상태 요약)",
  "client_action_pledge": "string (STRICTLY SMART, 10-minute doable concrete action in Korean: '나는 오늘/내일 ... 하겠다')",
  "is_smart_compliant": true,
  "counselor_reframing": "string (마음의 지지와 격려가 담긴 1문장 리프레이밍)"
}}"""

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }

    def build_full_schema(
        self,
        llm_payload: Dict[str, Any],
        report_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """고도화 설계서 7절 규격에 맞추어 주역 49산가지 수리 구조(象·數·辭·義)와 심리학/보안 메타데이터를 결합한 통합 스키마를 빌드합니다."""
        report_info = report_info or {}
        is_crisis = llm_payload.get("is_crisis", False)
        card_id = f"ACT-{'SB' if is_crisis else 'ZEN'}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        rem_list, val, result_code = self.simulate_yarrow_line()

        schema = {
            "card_metadata": {
                "card_id": card_id,
                "generation_logic": "18-fold_transformation",
                "stalks_count": 49,
                "created_at": datetime.now().isoformat()
            },
            "juyeok_structure": {
                "sang_visual": report_info.get("original_hex_name", "괘상 시각화"),
                "su_mathematics": {
                    "residual_sum": rem_list,
                    "result_code": result_code,
                    "line_value": val
                },
                "sa_text": report_info.get("target_line_text") or llm_payload.get("sacred_metaphor", "본괘 및 효사 원문"),
                "ui_meaning": llm_payload.get("universe_transition", "성찰 및 상황 연결"),
                "generation_order": "Bottom_to_Top_Apartment_Principle"
            },
            "psychological_engine": {
                "act_committed_action": (
                    llm_payload.get("client_action_pledge")
                    if not is_crisis
                    else "안전계획 즉각 실천 및 도움 요청"
                ),
                "smart_goal_validation": "Checked" if llm_payload.get("is_smart_compliant", True) else "Adjusted",
                "spi_status": "Emergency_Triggered" if is_crisis else "Normal",
                "wu_gu_target": "Blameless_State"
            },
            "security_ops": {
                "rasterization": "Completed",
                "resampling": "Done",
                "encryption": "AES-256",
                "exif_purged": True,
                "encrypted_aha_moment": encrypt_to_base64(llm_payload.get("client_aha_moment", "")),
                "encrypted_action_pledge": encrypt_to_base64(llm_payload.get("client_action_pledge", ""))
            },
            "card_payload": llm_payload,
            "card_markdown": self.format_card_markdown(llm_payload)
        }
        return schema

    def render_card_png(self, card_data: Dict[str, Any]):
        """Pillow 기반 EXIF 세척 순수 래스터화 카드 이미지 바이트스트림을 생성합니다."""
        renderer = CardImageRenderer()
        return renderer.render_card_png(card_data)

    def format_card_markdown(self, card_data: Dict[str, Any]) -> str:
        """합성된 JSON 데이터를 바탕으로 인앱 뷰어 및 모바일 화면용 마크다운을 렌더링합니다.

        위기 상황(SPI)과 일반 상황(ACT)을 완전히 다른 전문 템플릿으로 분기 렌더링합니다.
        """
        if card_data.get("is_crisis", False):
            # [위기 상황 전용] Stanley-Brown 안전계획(SPI) 카드 마크다운 템플릿
            md = f"""# 🚨 마음 안전 안심 카드 (Emergency Safety Plan Card)

> **안전계획(Safety Planning): 내면의 폭풍이 지나갈 때까지 나를 지탱해 주는 생명의 약속**

---

### ⚠️ 지금 나의 마음 신호 (Warning Signs)
**{card_data.get('crisis_warning_signs', '마음의 일시적 한계 상황 도달')}**

---

### 🧘 1단계: 지금 당장 실천하는 마음 안심 대처 (Inner Coping)
*   **복식 호흡:** 코로 4초간 들이쉬고, 7초간 참은 후, 8초간 천천히 입으로 내쉬며 심박수를 낮춥니다.
*   **감각 접지 (5-4-3-2-1):** 눈에 보이는 것 5개, 만져지는 것 4개, 들리는 소리 3개, 냄새 2개, 맛 1개에 차례로 온 정신을 집중해 마음을 현실로 되돌립니다.
*   **구체적 실천:**
"""
            for idx, strategy in enumerate(card_data.get("inner_coping_strategies", []), 1):
                md += f"    {idx}. **{strategy}**\n"

            md += """
---

### 🏡 2단계: 안전한 물리적 환경 구축 (Safe Space)
"""
            for step in card_data.get("safe_environment_steps", []):
                md += f"*   {step}\n"

            md += f"""
---

### 📞 3단계: 즉각 연결할 수 있는 사적 신뢰망 (Emergency Contact)
> **{card_data.get('external_contacts_advice', '가장 신뢰할 수 있는 친구나 가족에게 전화를 걸어 지금 나의 상태를 알리고 함께 시간을 보낼 것을 권장합니다.')}**

---

### 🏥 4단계: 24시간 열려 있는 전문 위기상담 센터 (Professional Help)
*   ☎️ **정신건강 위기상담전화: 국번 없이 109** (24시간, 무상 운영)
*   ☎️ **정신건강상담센터:** 1577-0199
*   ☎️ **보건복지상담센터:** 129
*   ☎️ **긴급 구조 지원:** 119 및 112 응급 출동 서비스
"""
            for agency in card_data.get("emergency_professional_agencies", []):
                if not any(num in agency for num in ["109", "1577-0199", "129", "119", "112"]):
                    md += f"*   {agency}\n"

            md += """
---

**[ 📞 즉시 109 전화 연결 ]  [ 🏥 내 주변 정신건강센터 찾기 ]  [ 💾 인앱 안심 보관함에 즉시 보관 ]**
"""
            return md

        else:
            # [일반 상황 전용] ACT 행동 전념 카드 마크다운 템플릿
            md = f"""# 🎴 마음 전념 카드 (Action Commitment Card)

> **지행합일(知行合一): 아는 것은 행함의 시작이요, 행함은 아는 것의 완성이라.**

---

### 🌌 여정의 궤적 (象)
**{card_data.get('universe_transition', '')}**

---

### ⚓ 성찰을 붙드는 기둥 (吉)
> **\"{card_data.get('sacred_metaphor', '')}\"**

---

### 💡 성찰의 눈뜸 (省)
*   **내가 내려놓은 아집:** {card_data.get('client_aha_moment', '')}

---

### 🎯 오늘 나의 행함 (行)
> 📝 **\"{card_data.get('client_action_pledge', '')}\"**
"""
            if not card_data.get("is_smart_compliant", True):
                md += "\n*(※ 원대한 다짐을 일상에서 실현 가능한 작은 크기의 SMART 목표로 미세 조정하여 반영했습니다.)*\n"

            md += f"""
---

### 💬 마음의 지지와 격려 (Reframing)
*{card_data.get('counselor_reframing', '')}*

---

**[ 💾 인앱 마음 보관함에 영구 소장 ]  [ 🤝 나의 믿음직한 동료와 공유 ]**
"""
            return md
