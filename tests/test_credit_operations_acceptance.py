"""T03 credit-operation-v1 PostgreSQL acceptance tests.

이 파일은 실제 transaction, UNIQUE/CHECK 제약과 row lock 경합을 확인하므로
marker가 있는 새 폐기 PostgreSQL에서만 실행한다. 외부 API와 LLM은 호출하지 않는다.
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select, update

from core.db import AsyncSessionLocal
from core.models.counsel import (
    CounselSession,
    CreditLedger,
    CreditOperation,
    UserProfile,
)
from services.credit_operation_service import (
    ENDPOINT_START,
    KIND_CONFLICT,
    KIND_IN_PROGRESS,
    KIND_REPLAY,
    KIND_RESERVED,
    STATUS_PROCESSING,
    STATUS_RELEASED,
    STATUS_SUCCEEDED,
    begin_operation,
    compute_request_hash,
    finalize_success,
    load_owned_operation,
    recover_operation_if_stale,
    utcnow,
)
from services.credit_service import ensure_user_profile


pytestmark = [pytest.mark.destructive_db]


@pytest.fixture(autouse=True)
async def clean_credit_tables(require_disposable_database):
    async with AsyncSessionLocal() as session:
        await session.execute(delete(CreditLedger))
        await session.execute(delete(CreditOperation))
        await session.execute(delete(CounselSession))
        await session.execute(delete(UserProfile))
        await session.commit()
    yield


async def _begin(user_id: str, key: str, payload: dict):
    async with AsyncSessionLocal() as session:
        return await begin_operation(
            session,
            user_id=user_id,
            endpoint=ENDPOINT_START,
            idempotency_key=key,
            request_hash=compute_request_hash(ENDPOINT_START, payload),
        )


@pytest.mark.asyncio
async def test_same_key_is_one_operation_and_different_body_conflicts():
    user_id = str(uuid.uuid4())
    key = str(uuid.uuid4())
    payload = {"question": "같은 요청"}

    first = await _begin(user_id, key, payload)
    second = await _begin(user_id, key, payload)
    conflict = await _begin(user_id, key, {"question": "다른 요청"})

    assert first.kind == KIND_RESERVED
    assert second.kind == KIND_IN_PROGRESS
    assert second.operation_id == first.operation_id
    assert conflict.kind == KIND_CONFLICT

    async with AsyncSessionLocal() as session:
        balance = await session.scalar(
            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
        )
        operation_count = await session.scalar(
            select(func.count()).select_from(CreditOperation)
        )
        debit_count = await session.scalar(
            select(func.count())
            .select_from(CreditLedger)
            .where(CreditLedger.event_type == "DEBIT")
        )

    assert balance == 40
    assert operation_count == 1
    assert debit_count == 1

    async with AsyncSessionLocal() as session:
        completed = await finalize_success(
            session,
            operation_id=first.operation_id,
            fencing_token=first.fencing_token or "",
            response_snapshot={"session_id": "s-1", "user_facing_message": "완료"},
        )
    replay = await _begin(user_id, key, payload)

    assert completed.status == STATUS_SUCCEEDED
    assert replay.kind == KIND_REPLAY
    assert replay.status == STATUS_SUCCEEDED
    assert replay.response_snapshot == {
        "session_id": "s-1",
        "user_facing_message": "완료",
    }


@pytest.mark.asyncio
async def test_concurrent_profile_initialization_grants_welcome_once():
    user_id = str(uuid.uuid4())

    async def initialize():
        async with AsyncSessionLocal() as session:
            created = await ensure_user_profile(session, user_id)
            await session.commit()
            return created

    created = await asyncio.gather(*(initialize() for _ in range(8)))

    async with AsyncSessionLocal() as session:
        balance = await session.scalar(
            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
        )
        welcome_count = await session.scalar(
            select(func.count())
            .select_from(CreditLedger)
            .where(
                CreditLedger.user_id == user_id,
                CreditLedger.event_type == "WELCOME",
            )
        )

    assert created.count(True) == 1
    assert balance == 50
    assert welcome_count == 1


@pytest.mark.asyncio
async def test_reserved_request_does_not_hold_credit_lock():
    user_id = str(uuid.uuid4())
    first = await _begin(user_id, str(uuid.uuid4()), {"question": "첫 요청"})
    assert first.kind == KIND_RESERVED

    # 첫 operation은 pipeline 실행 중이라고 가정해 PROCESSING으로 남겨 둔다.
    # 예약 세션이 이미 닫혔으므로 같은 사용자에 대한 두 번째 예약은 DB lock을
    # 기다리지 않고 짧은 시간 안에 끝나야 한다.
    second = await asyncio.wait_for(
        _begin(user_id, str(uuid.uuid4()), {"question": "두 번째 요청"}),
        timeout=2,
    )
    assert second.kind == KIND_RESERVED

    async with AsyncSessionLocal() as session:
        balance = await session.scalar(
            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
        )
    assert balance == 30


@pytest.mark.asyncio
async def test_stale_recovery_and_late_finalize_have_one_terminal_result():
    user_id = str(uuid.uuid4())
    outcome = await _begin(
        user_id,
        str(uuid.uuid4()),
        {"question": "복구 경합"},
    )
    assert outcome.kind == KIND_RESERVED

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(CreditOperation)
            .where(CreditOperation.id == outcome.operation_id)
            .values(lease_expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()

    async def recover():
        async with AsyncSessionLocal() as session:
            operation = await load_owned_operation(
                session,
                user_id=user_id,
                operation_id=outcome.operation_id,
            )
            assert operation is not None
            return await recover_operation_if_stale(session, operation=operation)

    async def late_finalize():
        async with AsyncSessionLocal() as session:
            return await finalize_success(
                session,
                operation_id=outcome.operation_id,
                fencing_token=outcome.fencing_token or "",
                response_snapshot={"session_id": "late", "user_facing_message": "늦은 응답"},
            )

    await asyncio.gather(recover(), late_finalize())

    async with AsyncSessionLocal() as session:
        operation = await session.scalar(
            select(CreditOperation).where(CreditOperation.id == outcome.operation_id)
        )
        balance = await session.scalar(
            select(UserProfile.credit_balance).where(UserProfile.id == user_id)
        )
        events = (
            await session.scalars(
                select(CreditLedger.event_type).where(
                    CreditLedger.operation_id == outcome.operation_id
                )
            )
        ).all()

    assert operation is not None
    assert operation.status in {STATUS_SUCCEEDED, STATUS_RELEASED}
    assert events.count("DEBIT") == 1
    assert events.count("RELEASE") <= 1
    if operation.status == STATUS_SUCCEEDED:
        assert balance == 40
        assert events.count("RELEASE") == 0
    else:
        assert balance == 50
        assert events.count("RELEASE") == 1
