import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from core.hexagram_engine import cast_hexagram
from scripts.seed_hexagrams import HEXAGRAM_NAME_MAP


def run_demo():
    print("=" * 60)
    print(" ☯️  주역 괘 도출 엔진 (Step 2 Hexagram Engine) 데모 ☯️")
    print("=" * 60)

    # 동전점 방식으로 무작위 괘 산출
    result = cast_hexagram(method="coin")

    orig_ko, orig_full = HEXAGRAM_NAME_MAP.get(result.original_hexagram_id, ("?", "?"))
    print(f"\n[본괘] 제{result.original_hexagram_id}괘 {orig_full} ({orig_ko})")
    print(f"       이진 코드: {result.original_binary} (초효 → 상효)")

    if result.transformed_hexagram_id:
        trans_ko, trans_full = HEXAGRAM_NAME_MAP.get(result.transformed_hexagram_id, ("?", "?"))
        print(f"[지괘] 제{result.transformed_hexagram_id}괘 {trans_full} ({trans_ko})")
        print(f"       이진 코드: {result.transformed_binary}")
        print(f"[동효] 변효 위치: {result.changing_lines}")
    else:
        print("[지괘] 없음 (동효 없음)")

    print("\n--- 6개 효 산출 상세 (1효: 초효 ~ 6효: 상효) ---")
    for line in result.lines:
        chg_tag = "⚡ [동효]" if line.is_changing else "  "
        print(f"  {line.position}효: 수치 {line.value} | 본괘 비트 '{line.original_bit}' → 지괘 비트 '{line.transformed_bit}' {chg_tag}")

    print("\n--- 📜 주자 점법 해석 지침 (Focus Rule) ---")
    print(f"  · 해석 포커스 유형: {result.focus_rule.focus_type.value}")
    print(f"  · 주요 타깃: {result.focus_rule.target_hexagram_type} 괘")
    print(f"  · 집중 효 번호: {result.focus_rule.target_line_numbers}")
    print(f"  · 지침 설명: {result.focus_rule.description_ko}")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
