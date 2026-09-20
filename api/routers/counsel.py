# -*- coding: utf-8 -*-
"""
주역 상담 앱 - 상담 세션 시작 및 대화 턴 진행 라우터 (CounselRouter)
- 최초 질문 intake 및 괘 도출 (/api/counsel/start)
- 소크라테스식 5턴 대화 진행 및 최종 저널 발급 (/api/counsel/turn)
- 작업 상태 조회 (/api/counsel/operations/{operation_id})

크레딧은 `credit-operation-v1` 계약대로 움직인다. 예약은 짧은 트랜잭션에서
커밋하고 닫은 뒤 파이프라인을 돌린다. 상담이 도는 20초 동안 크레딧 행 lock을
쥐고 있지 않는다.
"""

import logging
import uuid
from types import SimpleNamespace
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from agents.pipeline import run_turn
from api.deps import check_rate_limit, require_user, require_consent
from core.config import settings
from core.crisis_resources import get_crisis_resources_by_context
from core.db import AsyncSessionLocal
from core.models.counsel import CounselSession, CounselTurn
from core.release_gate import service_gate_reason
from services.credit_operation_service import (
    CODE_IDEMPOTENCY_KEY_REUSED,
    CODE_INSUFFICIENT_CREDITS,
    CODE_OPERATION_IN_PROGRESS,
    CODE_OPERATION_RECOVERED,
    CODE_PIPELINE_FAILED,
    ENDPOINT_START,
    ENDPOINT_TURN,
    KIND_CONFLICT,
    KIND_IN_PROGRESS,
    KIND_REPLAY,
    OPERATION_RETRY_AFTER_SECONDS,
    STATUS_PROCESSING,
    STATUS_REJECTED,
    IdempotencyKeyError,
    OperationOutcome,
    begin_operation,
    compute_request_hash,
    finalize_release,
    finalize_success,
    load_owned_operation,
    recover_operation_if_stale,
    validate_idempotency_key,
)
from services.credit_service import (
    CONSULTATION_CREDIT_COST,
    RefillStatus,
    is_chargeable,
    refill_free_credits_if_due,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/counsel", tags=["Counsel"])

# 내부 예외 문자열, DB명, 스택은 절대 응답에 넣지 않는다.
_GENERIC_ERROR_MESSAGE = "일시적인 서비스 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
_RECOVERED_MESSAGE = "이전 요청이 시간 안에 끝나지 않아 취소되었습니다. 크레딧은 차감되지 않았습니다."


async def require_service_gate():
    """출시 준비가 끝나지 않았으면 상담을 열지 않는다 (fail-closed).

    운영자가 `OPERATOR_ATTESTED_DECISIONS`에 확인을 마친 결정 ID를 기입하기
    전까지는 무료 베타도 열리지 않는다. 크레딧 차감·DB 접근·LLM 호출보다
    앞에서 끊긴다.

    `require_generation_enabled`와 의미가 다르다. 이쪽은 "출시 준비가 끝났는가",
    저쪽은 "장애·비용 때문에 지금 내려야 하는가"다.
    """
    reason = service_gate_reason(settings)
    if reason:
        raise HTTPException(status_code=503, detail=reason)


async def require_generation_enabled():
    """상담 생성이 꺼져 있으면 크레딧 차감과 LLM 호출 전에 막는다.

    장애·비용 급증 시 운영자가 즉시 내리는 스위치다. 차단되더라도 `/safety`의
    정적 긴급 안내와 본인 데이터 권리행사는 영향을 받지 않는다(별도 경로).
    """
    if not settings.GENERATION_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="상담 생성이 일시 중단되었습니다. 잠시 후 다시 시도해 주세요.",
        )


async def require_cost_budget():
    """일일/월간 AI 비용 예산 한도를 초과하거나 DB 장애 시 503으로 fail-closed 차단한다 (A02-R1).

    외부 트래픽 유입 시 금전적 손실을 선제 차단하며, 차단 중에도 비생성 경로(기록 조회, 잔액 확인 등)는
    정상 서비스된다.
    """
    from core.cost_budget import (
        BudgetUnverifiableError,
        CostBudgetExceededError,
        budget_tracker,
    )

    try:
        await budget_tracker.check_budget_available_async()
    except CostBudgetExceededError as exc:
        logger.warning(
            "비용 예산 초과로 상담 차단: %s (기간=%s, 현재=$%.4f, 한도=$%.2f)",
            exc.message,
            exc.period,
            exc.current_cost,
            exc.budget_limit,
        )
        raise HTTPException(
            status_code=503,
            detail="AI 호출 비용 예산 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
        )
    except BudgetUnverifiableError as exc:
        logger.error("예산 상태 확인 불가로 fail-closed 차단: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "BUDGET_UNVERIFIABLE",
                "message": "예산 상태를 확인할 수 없어 요청이 일시 차단되었습니다.",
            },
        )


def _string_result_attr(result, name: str, default=None):
    """실제 TurnResult와 기존 테스트/호환 객체 모두에서 문자열 메타데이터만 꺼낸다."""
    value = getattr(result, name, default)
    return value if isinstance(value, str) else default


def _error_json(
    status_code: int,
    code: str,
    message: str,
    *,
    operation_id: Optional[str] = None,
    remaining_credits: Optional[int] = None,
    retry_after_seconds: Optional[int] = None,
) -> JSONResponse:
    """계약이 정한 최소 오류 형태.

    `detail`은 기존 클라이언트와 회귀 테스트가 읽던 자리라 같은 문구로 함께
    남긴다. DB명·토큰·스택·타 사용자 ID는 어느 필드에도 넣지 않는다.
    """
    body: dict[str, Any] = {"code": code, "message": message, "detail": message}
    if operation_id:
        body["operation_id"] = operation_id
    if remaining_credits is not None:
        body["remaining_credits"] = remaining_credits
    if retry_after_seconds is not None:
        body["retry_after_seconds"] = retry_after_seconds

    headers = (
        {"Retry-After": str(retry_after_seconds)} if retry_after_seconds else None
    )
    return JSONResponse(status_code=status_code, content=body, headers=headers)


class StartConsultationRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="내담자의 최초 질문 발화 (최대 1000자)",
    )


class PreviewConsultationRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="비회원의 괘 도출 및 리포트 조회용 최초 질문 (최대 1000자)",
    )


class ClaimSessionRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="비회원 상태에서 발급받은 세션 ID",
    )


class ConsultationTurnApiRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="상담 세션 UUID",
    )
    user_message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="내담자의 이번 턴 발화 (최대 1000자)",
    )


def _build_response_body(result) -> dict:
    """기존 응답 필드를 그대로 만든다.

    잔액과 operation 메타데이터는 여기 넣지 않는다. 그 값들은 종결 시점에
    확정되고, 재생할 때도 저장된 확정값을 써야 같은 답이 나온다.
    """
    is_crisis = result.safety_category == "BLOCK_CRISIS"
    crisis_resources = get_crisis_resources_by_context() if is_crisis else []
    journal_data = getattr(result, "journal_data", None)

    return {
        "session_id": result.session_id,
        "turn_number": result.turn_number,
        "user_facing_message": result.user_facing_message,
        "needs_followup": result.needs_followup,
        "is_final": result.is_final,
        "hexagram_id": result.hexagram_id,
        "transformed_hexagram_id": result.transformed_hexagram_id,
        "changing_lines": result.changing_lines,
        "is_crisis": is_crisis,
        "crisis_resources": [r.dict() for r in crisis_resources],
        "is_duplicate": result.is_duplicate,
        "journal_summary": result.journal_summary,
        "journal_data": journal_data if isinstance(journal_data, dict) else None,
        "focus_rule": result.focus_rule,
        "evidences": result.evidences,
        "report_data": result.report_data if isinstance(result.report_data, dict) else None,
        "report_status": _string_result_attr(result, "report_status", "not_requested"),
        "report_error_code": _string_result_attr(result, "report_error_code"),
    }


def _terminal_response(outcome: OperationOutcome) -> JSONResponse:
    """종결된 작업 하나를 HTTP 응답으로 옮긴다.

    최초 요청의 응답과 재시도의 재생이 모두 이 함수를 지난다. 그래서 둘이
    다를 수 없다.
    """
    if outcome.status == STATUS_REJECTED:
        return _error_json(
            402,
            outcome.error_code or CODE_INSUFFICIENT_CREDITS,
            outcome.error_message or "크레딧이 부족합니다.",
            operation_id=outcome.operation_id,
            remaining_credits=outcome.remaining_credits,
        )

    if outcome.response_snapshot is None:
        # 사용자에게 답변을 제공하지 못한 기술 장애다. 최종 0C.
        recovered = outcome.error_code == CODE_OPERATION_RECOVERED
        return _error_json(
            503 if recovered else 500,
            outcome.error_code or "INTERNAL_ERROR",
            _RECOVERED_MESSAGE if recovered else _GENERIC_ERROR_MESSAGE,
            operation_id=outcome.operation_id,
            remaining_credits=outcome.remaining_credits,
        )

    body = dict(outcome.response_snapshot)
    body["operation_id"] = outcome.operation_id
    body["operation_status"] = outcome.status
    body["credit_delta"] = outcome.credit_delta
    body["remaining_credits"] = outcome.remaining_credits
    return JSONResponse(status_code=200, content=body)


async def _execute_counsel_operation(
    *,
    endpoint: str,
    user_id: str,
    idempotency_key: str,
    request_hash: str,
    run_pipeline: Callable,
    user_message: Optional[str] = None,
) -> JSONResponse:
    """예약 → 실행 → 종결. 크레딧 세션과 파이프라인 세션을 분리한다."""

    # 1. 예약: 짧은 트랜잭션 하나로 열고 닫는다.
    async with AsyncSessionLocal() as credit_session:
        # 12시간 경과 무료 크레딧 자동 충전 (예약 차감 전 선행 충전)
        refill_outcome = await refill_free_credits_if_due(credit_session, user_id)
        if refill_outcome.status == RefillStatus.REFILLED:
            try:
                await credit_session.commit()
                logger.info(
                    "무료 크레딧 자동 충전 커밋 완료: user_id=%s, new_balance=%d",
                    user_id,
                    refill_outcome.new_balance,
                )
            except Exception as commit_err:
                await credit_session.rollback()
                logger.warning("무료 크레딧 충전 커밋 실패(기존 잔액으로 진행): %s", commit_err)
        elif refill_outcome.status == RefillStatus.FAILED_RECOVERED:
            # savepoint 롤백으로 세션은 복구되었으므로 commit하지 않고 로깅 후 기존 잔액으로 진행
            logger.warning(
                "무료 크레딧 자동 충전 실패(세션 복구 완료, 기존 잔액으로 진행): user_id=%s, err=%s",
                user_id,
                refill_outcome.error,
            )
        else:
            # SKIPPED: 충전 조건 미도달(쿨다운 미도달, 잔액 충분 등)
            pass

        try:
            outcome = await begin_operation(
                credit_session,
                user_id=user_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                amount=CONSULTATION_CREDIT_COST,
            )
        except Exception:
            await credit_session.rollback()
            logger.error("크레딧 예약 중 오류: endpoint=%s", endpoint, exc_info=True)
            return _error_json(500, "INTERNAL_ERROR", _GENERIC_ERROR_MESSAGE)

    if outcome.kind == KIND_CONFLICT:
        return _error_json(
            409,
            CODE_IDEMPOTENCY_KEY_REUSED,
            outcome.error_message or "같은 Idempotency-Key가 다른 요청에 사용되었습니다.",
            operation_id=outcome.operation_id,
        )

    if outcome.kind == KIND_IN_PROGRESS:
        return _error_json(
            202,
            CODE_OPERATION_IN_PROGRESS,
            "이전 요청을 처리하는 중입니다.",
            operation_id=outcome.operation_id or None,
            retry_after_seconds=outcome.retry_after_seconds
            or OPERATION_RETRY_AFTER_SECONDS,
        )

    if outcome.kind == KIND_REPLAY:
        # 잔액 부족으로 REJECTED된 경우, 사용자 발화에 위기 징후가 있는지 선제 스크리닝한다 (BACKLOG.md #73).
        if outcome.status == STATUS_REJECTED and user_message:
            try:
                from agents.safety import screen, format_safety_response
                from core.crisis_resources import get_crisis_resources_by_context

                safety_res = await screen(user_message)
                if safety_res.category == "BLOCK_CRISIS":
                    logger.warning(
                        "크레딧 부족 상태에서 위기 신호 감지: user_id=%s, endpoint=%s -> 핫라인 무료 안내",
                        user_id,
                        endpoint,
                    )
                    crisis_msg = format_safety_response(safety_res) or (
                        "지금 매우 힘든 시간을 보내고 계신 것 같습니다. "
                        "당신의 생명과 안전이 무엇보다 소중합니다. "
                        "전문 상담 기관의 도움을 받아보시기를 권합니다."
                    )
                    crisis_resources = get_crisis_resources_by_context(safety_res.context)
                    crisis_body = {
                        "session_id": f"crisis-{uuid.uuid4()}",
                        "turn_number": 1,
                        "user_facing_message": crisis_msg,
                        "needs_followup": False,
                        "is_final": True,
                        "hexagram_id": None,
                        "transformed_hexagram_id": None,
                        "changing_lines": [],
                        "is_crisis": True,
                        "crisis_resources": [
                            r.model_dump() if hasattr(r, "model_dump") else r.dict()
                            for r in crisis_resources
                        ],
                        "is_duplicate": False,
                        "journal_summary": None,
                        "journal_data": None,
                        "focus_rule": None,
                        "evidences": [],
                        "report_data": None,
                        "report_status": "not_requested",
                        "report_error_code": None,
                        "operation_id": outcome.operation_id,
                        "operation_status": "RELEASED",
                        "credit_delta": 0,
                        "remaining_credits": outcome.remaining_credits,
                    }
                    return JSONResponse(status_code=200, content=crisis_body)
            except Exception as e:
                logger.error("위기 선제 스크리닝 중 오류: %s", e, exc_info=True)

        # 이미 확정된 작업이거나 위기 징후가 없는 정상 거부
        return _terminal_response(outcome)

    # 2. 실행: 크레딧과 무관한 별도 세션. 여기서는 크레딧 lock을 쥐지 않는다.
    operation_id = outcome.operation_id
    fencing_token = outcome.fencing_token or ""
    try:
        async with AsyncSessionLocal() as pipeline_session:
            result = await run_pipeline(pipeline_session)
            # 파이프라인은 각 쓰기 지점에서 스스로 커밋한다. 남은 것이 있어도
            # 여기서 닫고 나가도록 이전 동작과 똑같이 한 번 더 커밋한다.
            await pipeline_session.commit()
    except Exception:
        logger.error(
            "상담 파이프라인 실행 실패: operation=%s endpoint=%s",
            operation_id,
            endpoint,
            exc_info=True,
        )
        # 3-a. 답변을 제공하지 못했으므로 예약을 되돌린다 (최종 0C).
        async with AsyncSessionLocal() as release_session:
            try:
                released = await finalize_release(
                    release_session,
                    operation_id=operation_id,
                    fencing_token=fencing_token,
                    error_code=CODE_PIPELINE_FAILED,
                    error_message=_GENERIC_ERROR_MESSAGE,
                )
            except Exception:
                await release_session.rollback()
                logger.error(
                    "예약 해제 실패: operation=%s", operation_id, exc_info=True
                )
                return _error_json(
                    500,
                    "INTERNAL_ERROR",
                    _GENERIC_ERROR_MESSAGE,
                    operation_id=operation_id,
                )
        return _terminal_response(released)

    # 3-b. 종결. 위기 응답은 사용자에게 그대로 주되 크레딧은 되돌린다.
    body = _build_response_body(result)
    chargeable = is_chargeable(result)

    async with AsyncSessionLocal() as finalize_session:
        try:
            if chargeable:
                final = await finalize_success(
                    finalize_session,
                    operation_id=operation_id,
                    fencing_token=fencing_token,
                    response_snapshot=body,
                )
            else:
                final = await finalize_release(
                    finalize_session,
                    operation_id=operation_id,
                    fencing_token=fencing_token,
                    response_snapshot=body,
                )
                logger.info("위기 감지로 크레딧 예약 해제: operation=%s", operation_id)
        except Exception:
            await finalize_session.rollback()
            logger.error("작업 종결 실패: operation=%s", operation_id, exc_info=True)
            return _error_json(
                500,
                "INTERNAL_ERROR",
                _GENERIC_ERROR_MESSAGE,
                operation_id=operation_id,
            )

    return _terminal_response(final)


@router.post(
    "/preview",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_service_gate),
        Depends(require_generation_enabled),
    ],
    summary="비회원 무료 괘 도출 및 주역 리포트 미리보기",
)
async def preview_consultation_endpoint(
    req: PreviewConsultationRequest,
):
    """비회원(로그인 전) 질문으로 괘를 도출하고 심층 리포트를 무료로 생성합니다.
    크레딧을 차감하지 않으며 익명 세션(user_id=None)으로 저장됩니다.
    """
    import api.main as api_main
    runner = getattr(api_main, "run_turn", run_turn)

    async with AsyncSessionLocal() as db_session:
        try:
            result = await runner(
                session=db_session,
                counsel_session_id=None,
                user_id=None,
                message=req.question,
            )
            await db_session.commit()
            body = _build_response_body(result)
            return JSONResponse(status_code=200, content=body)
        except Exception as exc:
            await db_session.rollback()
            logger.error("비회원 프리뷰 리포트 생성 실패: %s", exc, exc_info=True)
            return _error_json(500, "INTERNAL_ERROR", _GENERIC_ERROR_MESSAGE)


@router.post(
    "/claim",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_service_gate),
        Depends(require_generation_enabled),
    ],
    summary="비회원 세션을 본인 계정으로 승계 및 1턴 상담 확정",
)
async def claim_consultation_session_endpoint(
    req: ClaimSessionRequest,
    request: Request,
    user_id: str = Depends(require_consent),
    _budget: None = Depends(require_cost_budget),
):
    """비회원 상태에서 생성된 익명 세션을 로그인된 본인 계정으로 소유권을 이전하고,
    10 크레딧을 소비하여 1턴 상담을 정식 확정합니다.
    """
    try:
        idempotency_key = validate_idempotency_key(
            request.headers.get("Idempotency-Key")
        )
    except IdempotencyKeyError as exc:
        return _error_json(400, exc.code, exc.message)

    # 1. 세션 존재 및 user_id 검증 (소유권 탈취 방지)
    async with AsyncSessionLocal() as db_session:
        c_session = (
            await db_session.execute(
                select(CounselSession).where(CounselSession.id == req.session_id)
            )
        ).scalar_one_or_none()

        if not c_session:
            return _error_json(404, "SESSION_NOT_FOUND", "해당 상담 세션을 찾을 수 없습니다.")

        if c_session.user_id and c_session.user_id != user_id:
            return _error_json(404, "SESSION_NOT_FOUND", "해당 상담 세션을 찾을 수 없습니다.")

    # 2. 크레딧 작업 예약 및 소유권 이전
    async def run_pipeline(db_session):
        target_session = (
            await db_session.execute(
                select(CounselSession).where(CounselSession.id == req.session_id)
            )
        ).scalar_one()
        target_session.user_id = user_id

        turn_row = (
            await db_session.execute(
                select(CounselTurn).where(
                    CounselTurn.session_id == req.session_id,
                    CounselTurn.turn_number == 1,
                )
            )
        ).scalar_one_or_none()

        await db_session.commit()

        return SimpleNamespace(
            session_id=target_session.id,
            turn_number=1,
            user_facing_message=turn_row.agent_response if turn_row else "주역 심층 상담이 연결되었습니다.",
            needs_followup=True,
            is_final=False,
            hexagram_id=turn_row.original_hexagram_id if turn_row else None,
            transformed_hexagram_id=turn_row.transformed_hexagram_id if turn_row else None,
            changing_lines=turn_row.changing_lines if turn_row else [],
            safety_category="NORMAL",
            is_duplicate=target_session.is_duplicate,
            journal_summary=None,
            journal_data=None,
            focus_rule=None,
            evidences=[],
            report_data=target_session.report_data,
            report_status=target_session.report_status,
            report_error_code=target_session.report_error_code,
        )

    return await _execute_counsel_operation(
        endpoint=ENDPOINT_START,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=compute_request_hash(ENDPOINT_START, {"claim_session_id": req.session_id}),
        run_pipeline=run_pipeline,
    )


@router.post(
    "/start",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_service_gate),
        Depends(require_generation_enabled),
    ],
    summary="상담 세션 시작 및 괘 도출",
)
async def start_consultation_endpoint(
    req: StartConsultationRequest,
    request: Request,
    user_id: str = Depends(require_consent),
    _budget: None = Depends(require_cost_budget),
):
    """최초 질문으로 상담 세션을 시작하고 괘 도출 및 1턴 결과를 반환합니다.

    JWT 인증과 `Idempotency-Key` 헤더가 필요하며 정상 답변 1회당 10 크레딧을
    소비합니다.
    """
    try:
        idempotency_key = validate_idempotency_key(
            request.headers.get("Idempotency-Key")
        )
    except IdempotencyKeyError as exc:
        return _error_json(400, exc.code, exc.message)

    async def run_pipeline(db_session):
        # 테스트 mocking 호환을 위해 api.main.run_turn을 동적 참조한다.
        import api.main as api_main

        runner = getattr(api_main, "run_turn", run_turn)
        return await runner(
            session=db_session,
            counsel_session_id=None,
            user_id=user_id,
            message=req.question,
        )

    return await _execute_counsel_operation(
        endpoint=ENDPOINT_START,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=compute_request_hash(ENDPOINT_START, {"question": req.question}),
        run_pipeline=run_pipeline,
        user_message=req.question,
    )


@router.post(
    "/turn",
    dependencies=[
        Depends(check_rate_limit),
        Depends(require_service_gate),
        Depends(require_generation_enabled),
    ],
    summary="상담 턴 대화 진행",
)
async def counsel_turn_endpoint(
    req: ConsultationTurnApiRequest,
    request: Request,
    user_id: str = Depends(require_consent),
    _budget: None = Depends(require_cost_budget),
):
    """상담 턴을 실행하고 결과를 반환합니다 (JWT 인증 및 엄격한 세션 소유권 검증)."""
    try:
        idempotency_key = validate_idempotency_key(
            request.headers.get("Idempotency-Key")
        )
    except IdempotencyKeyError as exc:
        return _error_json(400, exc.code, exc.message)

    # 소유권 검증은 크레딧이 움직이기 전에 끝난다 (BOLA 방지).
    async with AsyncSessionLocal() as db_session:
        c_session = (
            await db_session.execute(
                select(CounselSession).where(CounselSession.id == req.session_id)
            )
        ).scalar_one_or_none()

        if not c_session:
            raise HTTPException(status_code=404, detail="존재하지 않는 상담 세션입니다.")

        if not c_session.user_id or c_session.user_id != user_id:
            logger.warning(
                "세션 접근 권한 불일치 감지: session=%s, owner=%s, req_user=%s",
                req.session_id,
                c_session.user_id,
                user_id,
            )
            raise HTTPException(status_code=403, detail="이 상담 세션에 접근할 권한이 없습니다.")

        if c_session.status == "safety_redirect":
            logger.warning(
                "위기 지원 종료 세션 재개 시도 차단: session=%s, user=%s",
                req.session_id,
                user_id,
            )
            return _error_json(
                403,
                "SESSION_CLOSED_FOR_SAFETY",
                "위기 지원 안내로 종료된 세션은 추가 대화를 이어갈 수 없습니다.",
            )

        turn_count_res = await db_session.execute(
            select(func.count(CounselTurn.id)).where(CounselTurn.session_id == req.session_id)
        )
        current_turns = turn_count_res.scalar() or 0
        max_resume_turns = getattr(settings, "RESUME_MAX_TURNS", 15)
        if current_turns >= max_resume_turns:
            logger.warning(
                "세션 최대 대화 턴 상한 도달: session=%s, turns=%d >= %d",
                req.session_id,
                current_turns,
                max_resume_turns,
            )
            return _error_json(
                403,
                "SESSION_TURN_LIMIT_REACHED",
                f"이 상담 세션의 최대 대화 턴 수({max_resume_turns}턴)에 도달하여 더 이상 이어갈 수 없습니다.",
            )

    async def run_pipeline(db_session):
        import api.main as api_main

        runner = getattr(api_main, "run_turn", run_turn)
        return await runner(
            session=db_session,
            counsel_session_id=req.session_id,
            user_id=user_id,
            message=req.user_message,
        )

    return await _execute_counsel_operation(
        endpoint=ENDPOINT_TURN,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_hash=compute_request_hash(
            ENDPOINT_TURN,
            {"session_id": req.session_id, "user_message": req.user_message},
        ),
        run_pipeline=run_pipeline,
        user_message=req.user_message,
    )


@router.get(
    "/operations/{operation_id}",
    dependencies=[Depends(check_rate_limit)],
    summary="크레딧 작업 상태 조회",
)
async def get_operation_status_endpoint(
    operation_id: str,
    user_id: str = Depends(require_user),
):
    """소유자 본인의 작업 상태와 저장된 결과를 반환합니다.

    남의 작업은 존재 여부가 드러나지 않도록 없는 것과 똑같이 404다.
    lease가 만료된 채 남아 있던 작업은 이 조회에서 복구되어 예약이 풀린다.
    """
    async with AsyncSessionLocal() as db_session:
        operation = await load_owned_operation(
            db_session, user_id=user_id, operation_id=operation_id
        )
        if operation is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 작업입니다.")

        if operation.status == STATUS_PROCESSING:
            operation = await recover_operation_if_stale(
                db_session, operation=operation
            )

        if operation.status == STATUS_PROCESSING:
            return JSONResponse(
                status_code=200,
                content={
                    "operation_id": str(operation.id),
                    "operation_status": STATUS_PROCESSING,
                    "credit_delta": None,
                    "remaining_credits": None,
                    "result": None,
                    "retry_after_seconds": OPERATION_RETRY_AFTER_SECONDS,
                },
            )

        return JSONResponse(
            status_code=200,
            content={
                "operation_id": str(operation.id),
                "operation_status": operation.status,
                "credit_delta": operation.credit_delta
                if operation.credit_delta is not None
                else 0,
                "remaining_credits": operation.balance_snapshot,
                "result": operation.response_snapshot,
                "error_code": operation.error_code,
            },
        )
