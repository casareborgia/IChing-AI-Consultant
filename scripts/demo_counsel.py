"""주역 AI 상담 대화형 CLI 데모 스크립트.

사용 예시:
    python scripts/demo_counsel.py
    python scripts/demo_counsel.py --message "너무 힘들어서 죽고 싶어"
    python scripts/demo_counsel.py --user-id "test_user_1"
"""

import argparse
import asyncio
import os
import sys

# 프로젝트 루트 sys.path 추가
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))

from agents.pipeline import run_turn
from core.db import AsyncSessionLocal


async def main_async(args):
    print("=" * 64)
    print(" 🧭 주역 상담 AI (I-Ching Consultant) — 5단계 대화 데모")
    print("=" * 64)
    print(" * 종료하려면 'q', 'exit', '종료'를 입력하세요.\n")

    user_id = args.user_id or "demo_user"
    session_id = None
    first_msg = args.message

    async with AsyncSessionLocal() as session:
        while True:
            if first_msg:
                user_input = first_msg
                first_msg = None
                print(f"[내담자]: {user_input}")
            else:
                try:
                    user_input = input("\n[내담자]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n상담을 종료합니다.")
                    break

                if not user_input:
                    print("  (말씀하실 내용을 입력해 주세요. 종료하시려면 'q' 또는 '종료'를 입력하세요.)")
                    continue

                if user_input.lower() in ("q", "exit", "quit", "종료"):
                    print("\n상담을 종료합니다. 마음이 평안하시기를 바랍니다.")
                    break

            print("\n[AI 상담사 생각 중...]")
            res = await run_turn(
                session,
                counsel_session_id=session_id,
                user_id=user_id,
                message=user_input,
                method=args.method,
            )

            session_id = res.session_id

            print(f"\n[AI 상담사 (턴 {res.turn_number})]:")
            print(res.user_facing_message)

            if res.hexagram_id and res.turn_number == 1:
                trans_info = f" -> 지괘 {res.transformed_hexagram_id}" if res.transformed_hexagram_id else ""
                print(f"\n  (시스템 내부: 본괘 {res.hexagram_id}{trans_info}, 동효 {res.changing_lines})")


            if res.is_final:
                print("\n" + "-" * 64)
                print(" 상담 세션이 종료되었습니다.")
                if res.journal_summary:
                    print(f" [저널 기록]: {res.journal_summary}")
                print("-" * 64)
                break


def main():
    ap = argparse.ArgumentParser(description="주역 AI 상담 대화형 CLI 데모")
    ap.add_argument("-m", "--message", default=None, help="첫 번째 턴 발화 직접 주입")
    ap.add_argument("-u", "--user-id", default="demo_user", help="사용자 식별자")
    ap.add_argument("--method", default="coin", choices=["coin", "yarrow"], help="괘 산출 방식")
    args = ap.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
