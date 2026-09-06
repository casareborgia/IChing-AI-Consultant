"""리포트 프롬프트의 구체 예시 어휘가 가족 사연에 미치는 영향을 A/B 비교한다.

동일한 사용자 질문과 주역 근거를 두 프롬프트에 넣고, 구체적인 도메인·상징 예시만
제거한 B안과 현재 운영 A안을 같은 Gemini 설정으로 반복 호출한다.

사용법:
    python scripts/compare_report_prompt_priming.py -p gemini -n 2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.llm import get_client
from core.prompts import load_system_prompt


QUESTIONS = [
    "명절마다 부모님과 배우자 사이에서 갈등이 생깁니다. 어떻게 대화해야 할까요?",
    "형제와 부모님 돌봄 문제로 자꾸 다투게 됩니다. 관계를 어떻게 풀어야 할까요?",
    "성인이 된 자녀와 대화가 끊겼습니다. 먼저 다가가도 괜찮을까요?",
]

CONTEXT = """<actual_divination_context>
- User's Real Question: "{question}"
- Topic Category: 가족/인간관계
- Original Hexagram: 제37괘 풍화가인(家人) ("가족 안에서 역할과 관계의 질서를 살핌")
- Core Theme: 가까운 관계일수록 말과 행동의 일관성을 돌아봄
- Changing Lines: [3]
- Transformed Hexagram: 제42괘 풍뢰익(益) ("서로에게 실제 도움이 되는 방향을 찾음")

[Gobyeonjeom Rule Engine v4.1]
- Changing Count: 1 (변효 1개)
- Target Focus: 본괘(제37괘 풍화가인)의 제3효 효사
- Rule Description: 해당 변효의 효사를 핵심 지침으로 삼습니다.
- Target Line Hanja: 家人嗃嗃 悔厲吉 婦子嘻嘻 終吝
- Auxiliary Line Hanja: None
- Transformed Hexagram Hanja: 利有攸往 利涉大川

[RAG Classical Annotations]
[효사 주석(3효)] 지나치게 엄격하면 후회가 따르지만 방임하여 웃고 즐기기만 하면 끝내 부끄러움이 있다.
[본의 효사(3효)] 가족을 다스릴 때 엄함과 온화함 사이의 균형을 살핀다.
</actual_divination_context>

[CRITICAL INSTRUCTION - DOMAIN CONTEXT ALIGNMENT & NO TEMPLATE CLICHES]
Write a customized I-Ching consulting report in Korean adhering strictly to the JSON schema below.
- Align the terminology, emotional tone, and metaphors with the User's Real Question and Topic Category (가족/인간관계).
  * Family/Interpersonal/Emotional: Use psychological depth, relational balance, boundaries, empathy, and personal reflection. NEVER inject corporate or business jargon (such as market validation, contract risks, soft landing, profit margins) into family or interpersonal issues.
  * Career/Business/Studies: Adapt appropriately to practical decisions, pacing, structural challenges, and strategic timing.
- Map the ancient I-Ching metaphor 1:1 to the user's specific real-world question.

Return a JSON with these exact string keys:
{{
  "section1_diagnosis": "2-3 sentences",
  "section2_action": "specific action guidance",
  "section3_warning": "cautions",
  "section4_future": "future direction",
  "final_summary": "1-2 sentence summary"
}}
"""

SYSTEM_DOMAIN_EXAMPLES = """- Strict Domain Alignment: Strictly adopt the vocabulary and framing appropriate to the user's specific problem domain (e.g., for relationships/family: emotional boundaries, mutual respect, psychological peace; for business/career: realistic execution, timing, prudent resource management; for inner growth: patience, self-reflection). NEVER use uncalled-for corporate jargon in family/personal struggles."""
SYSTEM_DOMAIN_ABSTRACT = """- Strict Domain Alignment: Derive vocabulary and framing only from the user's question and supplied topic category. Do not import concepts from an unrelated domain."""

SYSTEM_IMAGE_EXAMPLES = """- Step 1 [Metaphor Conceptualization]: Understand the primitive physical objects/actions in the retrieved I-Ching text (e.g., tiger's tail, old rags, boat leaks, clothing, thunder, fire, mountain) and conceptualize their underlying philosophical warning/message."""
SYSTEM_IMAGE_ABSTRACT = """- Step 1 [Metaphor Conceptualization]: Identify the concrete image in the retrieved I-Ching text and conceptualize its underlying philosophical warning or message."""

SYSTEM_TONE_EXAMPLES = """- Category-Specific Tone Adaptation:
  * For business/finance/career: Use a professional, analytical, and sharp consultant's voice.
  * For relationships/family: Use a warm, healing, and deeply empathetic counselor's voice focusing on healthy emotional boundaries.
  * For study/slump/career transition: Use a firm, encouraging, and mentoring voice focusing on steady inner discipline."""
SYSTEM_TONE_ABSTRACT = """- Adapt the tone to the supplied category without borrowing subject matter, entities, or vocabulary from categories that the user did not mention."""

USER_DOMAIN_EXAMPLES = """- Align the terminology, emotional tone, and metaphors with the User's Real Question and Topic Category (가족/인간관계).
  * Family/Interpersonal/Emotional: Use psychological depth, relational balance, boundaries, empathy, and personal reflection. NEVER inject corporate or business jargon (such as market validation, contract risks, soft landing, profit margins) into family or interpersonal issues.
  * Career/Business/Studies: Adapt appropriately to practical decisions, pacing, structural challenges, and strategic timing."""
USER_DOMAIN_ABSTRACT = """- Derive terminology, emotional tone, and metaphors only from the User's Real Question and Topic Category (가족/인간관계).
- Do not import vocabulary from a domain absent from the user's question."""

LEAK_TERMS = (
    "시장", "계약", "연착륙", "수익", "마진", "비즈니스", "기업", "사업",
    "market", "contract", "soft landing", "profit margin", "business", "corporate",
)


def sanitized_prompts(system: str, user: str) -> tuple[str, str]:
    clean_system = system.replace(SYSTEM_DOMAIN_EXAMPLES, SYSTEM_DOMAIN_ABSTRACT)
    clean_system = clean_system.replace(SYSTEM_IMAGE_EXAMPLES, SYSTEM_IMAGE_ABSTRACT)
    clean_system = clean_system.replace(SYSTEM_TONE_EXAMPLES, SYSTEM_TONE_ABSTRACT)
    clean_user = user.replace(USER_DOMAIN_EXAMPLES, USER_DOMAIN_ABSTRACT)
    if clean_system == system or clean_user == user:
        raise RuntimeError("현재 프롬프트 문구가 바뀌어 A/B 치환 규칙을 적용하지 못했습니다")
    return clean_system, clean_user


def flatten(result: Dict[str, Any]) -> str:
    return " ".join(str(value) for value in result.values()).lower()


def leaked_terms(result: Dict[str, Any]) -> List[str]:
    text = flatten(result)
    return [term for term in LEAK_TERMS if term.lower() in text]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--provider", default="gemini")
    parser.add_argument("-n", "--repeats", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=Path("/tmp/report_prompt_priming.json"))
    args = parser.parse_args()

    client = get_client("report", provider=args.provider)
    current_system = load_system_prompt("report")
    rows: List[Dict[str, Any]] = []

    for question in QUESTIONS:
        current_user = CONTEXT.format(question=question)
        clean_system, clean_user = sanitized_prompts(current_system, current_user)
        for repeat in range(1, args.repeats + 1):
            for variant, system, user in (
                ("current", current_system, current_user),
                ("zero_shot", clean_system, clean_user),
            ):
                result = client.complete_json(user, system=system, temperature=0.1)
                rows.append({
                    "question": question,
                    "repeat": repeat,
                    "variant": variant,
                    "leaked_terms": leaked_terms(result),
                    "result": result,
                })
                print(f"{variant:9} repeat={repeat} leaks={rows[-1]['leaked_terms']}")

    summary = {
        variant: sum(bool(row["leaked_terms"]) for row in rows if row["variant"] == variant)
        for variant in ("current", "zero_shot")
    }
    payload = {"provider": args.provider, "repeats": args.repeats, "summary": summary, "rows": rows}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
