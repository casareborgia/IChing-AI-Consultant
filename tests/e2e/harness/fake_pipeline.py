# -*- coding: utf-8 -*-
"""결정론적 test-only 상담 파이프라인.

외부 LLM(Vertex AI·Gemini·Anthropic·OpenAI·Ollama)과 임베딩을 한 번도 부르지
않는다. 같은 입력에 언제나 같은 결과를 돌려준다.

제품 코드는 고치지 않는다. `api/routers/counsel.py`가 이미
`getattr(api_main, "run_turn", run_turn)`로 동적 참조하는 이음매에 이 함수를
꽂는다. 그 이음매는 제품이 테스트 mocking을 위해 스스로 열어 둔 자리다.

반환 타입은 제품의 `agents.pipeline.TurnResult` 그대로다. 필드 이름을 하네스가
새로 지어내지 않는다. 세션·턴 행도 제품 모델로 실제로 쓴다. 그래야 `/turn`의
소유권 검사(404/403)가 진짜 행을 상대로 검증된다.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Dict, Optional

from sqlalchemy import func, select

from agents.pipeline import TurnResult
from core.models.counsel import CounselSession, CounselTurn

# 사용자별 동작 지시. 오케스트레이터가 시나리오 시작 전에 채운다.
#   "succeed"  정상 종결
#   "fail"     파이프라인 예외 (RELEASED·0C 경로)
#   "block"    release 신호가 올 때까지 대기 (202 IN_PROGRESS 경로)
#   "crisis"   위기 판정 (BLOCK_CRISIS → 응답은 주되 크레딧은 환불)
BEHAVIORS: Dict[str, str] = {}

# "block" 동작에서 쓰는 신호. 서버 루프와 오케스트레이터 스레드가 함께 본다.
ENTERED: Dict[str, threading.Event] = {}
RELEASE: Dict[str, threading.Event] = {}

# 몇 번째 턴에서 상담을 끝낼지. 기본 3턴.
FINAL_TURN_AT: Dict[str, int] = {}

BLOCK_TIMEOUT_SECONDS = 60.0


class FakePipelineFailure(RuntimeError):
    """의도적으로 일으키는 파이프라인 장애.

    메시지에 사용자 식별자나 발화를 담지 않는다. 제품 라우터는 어차피 이
    문자열을 응답에 넣지 않지만, 로그에도 남지 않게 여기서부터 지운다.
    """


def reset() -> None:
    BEHAVIORS.clear()
    ENTERED.clear()
    RELEASE.clear()
    FINAL_TURN_AT.clear()


def arm_block(user_id: str) -> None:
    BEHAVIORS[user_id] = "block"
    ENTERED[user_id] = threading.Event()
    RELEASE[user_id] = threading.Event()


def wait_until_entered(user_id: str, timeout: float = 30.0) -> bool:
    event = ENTERED.get(user_id)
    return bool(event and event.wait(timeout))


def release_block(user_id: str) -> None:
    event = RELEASE.get(user_id)
    if event:
        event.set()


def _message_for(turn_number: int, is_final: bool) -> str:
    """결정론적 상담 문구. 무작위성도 외부 호출도 없다."""
    if is_final:
        return "E2E-FAKE 최종 턴 {0}: 정리와 다음 행동을 제안합니다.".format(turn_number)
    return "E2E-FAKE 턴 {0}: 더 여쭙겠습니다. 어떤 점이 가장 마음에 걸리시나요?".format(
        turn_number
    )


async def fake_run_turn(
    *,
    session,
    counsel_session_id: Optional[str],
    user_id: str,
    message: str,
    **_ignored,
) -> TurnResult:
    """제품 `run_turn`과 같은 호출 규약의 결정론적 대역."""
    behavior = BEHAVIORS.get(user_id, "succeed")

    if behavior == "block":
        entered = ENTERED.get(user_id)
        if entered:
            entered.set()
        release = RELEASE.get(user_id)
        if release:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, release.wait, BLOCK_TIMEOUT_SECONDS)
        behavior = "succeed"

    if behavior == "fail":
        raise FakePipelineFailure("결정론적 test-only 파이프라인 장애")

    if counsel_session_id is None:
        counsel = CounselSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            raw_question=message,
            status="active",
            report_status="not_requested",
        )
        session.add(counsel)
        await session.flush()
        turn_number = 1
    else:
        counsel = (
            await session.execute(
                select(CounselSession).where(CounselSession.id == counsel_session_id)
            )
        ).scalar_one()
        highest = (
            await session.execute(
                select(func.max(CounselTurn.turn_number)).where(
                    CounselTurn.session_id == counsel.id
                )
            )
        ).scalar_one_or_none()
        turn_number = (highest or 0) + 1

    final_at = FINAL_TURN_AT.get(user_id, 3)
    is_final = turn_number >= final_at
    agent_response = _message_for(turn_number, is_final)

    session.add(
        CounselTurn(
            session_id=counsel.id,
            turn_number=turn_number,
            original_hexagram_id=None,
            transformed_hexagram_id=None,
            changing_lines=[3],
            user_message=message,
            agent_response=agent_response,
            needs_followup=not is_final,
            is_final=is_final,
        )
    )
    if is_final:
        counsel.status = "completed"
    await session.commit()

    return TurnResult(
        session_id=counsel.id,
        turn_number=turn_number,
        user_facing_message=agent_response,
        needs_followup=not is_final,
        is_final=is_final,
        hexagram_id=1,
        transformed_hexagram_id=44 if is_final else None,
        changing_lines=[3],
        safety_category="BLOCK_CRISIS" if behavior == "crisis" else "NORMAL",
        is_duplicate=False,
        journal_summary="E2E-FAKE 저널 요약" if is_final else None,
        journal_data={"headline": "E2E-FAKE", "turn": turn_number} if is_final else None,
        focus_rule={"rule": "E2E-FAKE 단일 변효", "line": 3},
        evidences=[{"source": "E2E-FAKE", "text": "결정론적 근거 문자열"}],
        raw_text=None,
        report_data=None,
        report_status="not_requested",
        report_error_code=None,
    )
