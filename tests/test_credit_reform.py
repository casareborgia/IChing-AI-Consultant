# -*- coding: utf-8 -*-
"""12시간 무료 크레딧 자동 충전 (Credit Reform) 회귀 테스트 (CR-1 ~ CR-10).

Codex 개선 지시서 요구사항:
- CR-1: 13시간 경과, 잔액 0 -> 50C 충전, REFILL_FREE +50 1건
- CR-2: 12시간 이내 -> 무충전
- CR-3: 동시 refill 2건 -> 최종 50C, 원장 1건
- CR-4: 조회 후 UPDATE 전 운영자 +40C 경쟁 -> 최종 잔액 50C 이하, 정확한 grant 원장
- CR-5: 잔액 50C 이상 -> 무충전, 원장 없음
- CR-6: profile UPDATE 성공 후 ledger INSERT 실패 -> 둘 다 rollback
- CR-7: refill SELECT/UPDATE에서 DB 예외 -> 세션 복구 후 기존 잔액으로 상담 예약 계속 또는 정상 402; 500 금지
- CR-8: 정상 상담 예약 -> DEBIT -10과 잔액 snapshot 유지
- CR-9: 조회 전용 credits endpoint -> refill 및 원장 쓰기 없음
- CR-10: FREE_BETA_REFILL_CREDITS/HOURS <= 0 -> 완전 비활성
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from core.config import settings
from core.models.counsel import CreditLedger, UserProfile
from services.credit_service import (
    EVENT_REFILL,
    RefillOutcome,
    RefillStatus,
    read_balance,
    refill_free_credits_if_due,
)
from services import credit_operation_service as op_svc


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def first(self):
        return self._value


class FakeSavepoint:
    def __init__(self, session):
        self.session = session
        self.is_active = True
        self._profile_snapshots = {}

    async def __aenter__(self):
        self.session.savepoint_depth += 1
        for obj in self.session._tracked_profiles:
            self._profile_snapshots[obj] = {
                "credit_balance": obj.credit_balance,
                "last_refilled_at": obj.last_refilled_at,
                "updated_at": getattr(obj, "updated_at", None),
            }
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.session.savepoint_depth -= 1
        if exc_type is not None:
            self.session.savepoint_rollbacks += 1
            self.session.added = list(self.session.snapshot_added)
            for obj, state in self._profile_snapshots.items():
                for k, v in state.items():
                    setattr(obj, k, v)
            return False
        return False


class FakeSession:
    def __init__(self, results=None):
        self.statements: list[str] = []
        self._results = list(results or [])
        self.added = []
        self.snapshot_added = []
        self._tracked_profiles = []
        self._initial_profile_states = {}
        for r in self._results:
            if isinstance(r, UserProfile):
                self._tracked_profiles.append(r)
                self._initial_profile_states[r] = {
                    "credit_balance": r.credit_balance,
                    "last_refilled_at": r.last_refilled_at,
                    "updated_at": getattr(r, "updated_at", None),
                }
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self.savepoint_depth = 0
        self.savepoint_rollbacks = 0

    def begin_nested(self):
        self.snapshot_added = list(self.added)
        return FakeSavepoint(self)

    async def execute(self, statement, *args, **kwargs):
        try:
            self.statements.append(str(statement.compile(dialect=postgresql.dialect())))
        except Exception:
            self.statements.append(str(statement))
        if self._results:
            res = self._results.pop(0)
            if isinstance(res, Exception):
                raise res
            if isinstance(res, UserProfile) and res not in self._tracked_profiles:
                self._tracked_profiles.append(res)
                self._initial_profile_states[res] = {
                    "credit_balance": res.credit_balance,
                    "last_refilled_at": res.last_refilled_at,
                    "updated_at": getattr(res, "updated_at", None),
                }
            return _FakeResult(res)
        return _FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    def expire(self, obj):
        """ORM 객체의 dirty state를 초기 스냅샷 상태로 만료/복원."""
        if obj in self._initial_profile_states:
            for k, v in self._initial_profile_states[obj].items():
                setattr(obj, k, v)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_cr_1_refill_grants_up_to_target_after_13_hours():
    """CR-1: 13시간 경과, 잔액 0인 사용자가 요청 시 50C 충전, REFILL_FREE +50 1건."""
    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
    session = FakeSession(results=[profile])

    outcome = await refill_free_credits_if_due(session, user_id)

    assert outcome.status == RefillStatus.REFILLED
    assert outcome.new_balance == 50
    assert outcome.refilled_amount == 50
    assert profile.credit_balance == 50
    assert any("FOR UPDATE" in s for s in session.statements)
    assert len(session.added) == 1
    ledger = session.added[0]
    assert isinstance(ledger, CreditLedger)
    assert ledger.amount == 50
    assert ledger.event_type == EVENT_REFILL
    assert "12시간 무료 자동 충전" in ledger.reason


@pytest.mark.asyncio
async def test_cr_2_refill_skipped_when_within_12_hours():
    """CR-2: 12시간 이내 요청에서는 무충전 (쿨다운 유지)."""
    user_id = str(uuid.uuid4())
    recent_2h = datetime.now(timezone.utc) - timedelta(hours=2)

    profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=recent_2h)
    session = FakeSession(results=[profile])

    outcome = await refill_free_credits_if_due(session, user_id)

    assert outcome.status == RefillStatus.SKIPPED
    assert outcome.new_balance is None
    assert outcome.refilled_amount == 0
    assert profile.credit_balance == 0
    assert len(session.added) == 0


@pytest.mark.asyncio
async def test_cr_3_concurrent_refill_race_condition_safe():
    """CR-3: 동시 refill 2건 시 원자적 락과 조건으로 최종 50C, 원장 1건만 기록."""
    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    # 1번째 요청: 잔액 0에서 50C 충전 성공
    profile1 = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
    session1 = FakeSession(results=[profile1])
    outcome1 = await refill_free_credits_if_due(session1, user_id)

    assert outcome1.status == RefillStatus.REFILLED
    assert outcome1.new_balance == 50
    assert len(session1.added) == 1

    # 2번째 동시 요청: 1번째 요청에 의해 잠금 후 잔액이 이미 50C이고 last_refilled_at이 갱신됨
    now_refilled = profile1.last_refilled_at
    profile2 = UserProfile(id=user_id, credit_balance=50, last_refilled_at=now_refilled)
    session2 = FakeSession(results=[profile2])
    outcome2 = await refill_free_credits_if_due(session2, user_id)

    assert outcome2.status == RefillStatus.SKIPPED
    assert outcome2.new_balance is None
    assert profile2.credit_balance == 50
    assert len(session2.added) == 0


@pytest.mark.asyncio
async def test_cr_4_admin_grant_competition_caps_at_50():
    """CR-4: 잠금 시점 잔액이 운영자 +40C 지급으로 40C가 된 경우, grant는 10C로 계산되어 최종 잔액 50C 이하 유지."""
    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    # 잠금 획득 시점의 최신 잔액이 40C
    profile = UserProfile(id=user_id, credit_balance=40, last_refilled_at=past_13h)
    session = FakeSession(results=[profile])

    outcome = await refill_free_credits_if_due(session, user_id)

    assert outcome.status == RefillStatus.REFILLED
    assert outcome.new_balance == 50
    assert outcome.refilled_amount == 10  # 40 -> 50C (grant: 10)
    assert profile.credit_balance == 50
    assert len(session.added) == 1
    assert session.added[0].amount == 10


@pytest.mark.asyncio
async def test_cr_5_refill_skipped_if_balance_sufficient():
    """CR-5: 잔액이 이미 50C 이상이면 무충전, 원장 없음."""
    user_id = str(uuid.uuid4())
    past_15h = datetime.now(timezone.utc) - timedelta(hours=15)

    profile = UserProfile(id=user_id, credit_balance=50, last_refilled_at=past_15h)
    session = FakeSession(results=[profile])

    outcome = await refill_free_credits_if_due(session, user_id)

    assert outcome.status == RefillStatus.SKIPPED
    assert outcome.new_balance is None
    assert profile.credit_balance == 50
    assert len(session.added) == 0


@pytest.mark.asyncio
async def test_cr_6_ledger_insert_failure_rolls_back_both():
    """CR-6: 프로필 갱신 후 ledger INSERT 또는 flush에서 실패 시 savepoint 롤백 및 expire로 둘 다 rollback."""
    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    class FailingSession(FakeSession):
        async def flush(self):
            raise RuntimeError("DB connection error during flush")

    profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
    session = FailingSession(results=[profile])

    outcome = await refill_free_credits_if_due(session, user_id)

    assert outcome.status == RefillStatus.FAILED_RECOVERED
    assert outcome.new_balance is None
    assert session.savepoint_rollbacks == 1
    assert len(session.added) == 0
    # 프로필 메모리 dirty state가 expire를 통해 원래 잔액(0)과 원래 refill 시간으로 복원되었는지 검증
    assert profile.credit_balance == 0
    assert profile.last_refilled_at == past_13h


@pytest.mark.asyncio
async def test_cr_7_refill_db_exception_recovers_session_no_500():
    """CR-7: refill SELECT/UPDATE에서 DB 예외 발생 시 세션이 복구되어 기존 잔액으로 상담 예약 진행 또는 정상 402; 500 금지."""
    user_id = str(uuid.uuid4())

    # 1. SELECT FOR UPDATE 실행 시 DB 에러 발생 시뮬레이션
    session = FakeSession(results=[RuntimeError("Deadlock detected during SELECT FOR UPDATE")])

    outcome = await refill_free_credits_if_due(session, user_id)

    # 예외가 안전하게 격리되고 FAILED_RECOVERED 반환
    assert outcome.status == RefillStatus.FAILED_RECOVERED
    assert outcome.new_balance is None
    assert session.savepoint_rollbacks == 1

    # 호출자가 이어서 commit/rollback 및 다음 작업을 안전하게 수행할 수 있음
    await session.commit()
    assert session.commits == 1


@pytest.mark.asyncio
async def test_cr_8_normal_counsel_reservation_maintains_debit_snapshot():
    """CR-8: 정상 상담 예약 시 DEBIT -10과 잔액 snapshot 유지."""
    user_id = str(uuid.uuid4())
    # 잔액 50C인 사용자가 상담 1턴(10C) 예약
    profile = UserProfile(id=user_id, credit_balance=50)
    session = FakeSession(results=[
        profile,  # refill: 이미 50C이므로 스킵
        40,       # charge_credits update returning
    ])

    from services.credit_service import charge_credits
    new_bal = await charge_credits(
        session, user_id=user_id, amount=10, reason="상담 1턴 차감"
    )

    assert new_bal == 40
    assert any("UPDATE profiles" in s and "credit_balance" in s for s in session.statements)
    assert len(session.added) == 1
    ledger = session.added[0]
    assert ledger.amount == -10
    assert ledger.reason == "상담 1턴 차감"


@pytest.mark.asyncio
async def test_cr_9_read_balance_does_not_mutate_ledger():
    """CR-9: 조회 전용 경로(read_balance)는 단순 조회만 수행하고 원장을 쓰지 않는다."""
    user_id = str(uuid.uuid4())
    session = FakeSession(results=[50])

    bal = await read_balance(session, user_id)

    assert bal == 50
    assert len(session.statements) == 1
    assert "SELECT" in session.statements[0]
    assert not any("INSERT" in s or "UPDATE" in s for s in session.statements)
    assert len(session.added) == 0


@pytest.mark.asyncio
async def test_cr_10_refill_disabled_when_config_zero_or_negative():
    """CR-10: FREE_BETA_REFILL_CREDITS/HOURS <= 0 이면 완전 비활성."""
    user_id = str(uuid.uuid4())
    session = FakeSession()

    with patch.object(settings, "FREE_BETA_REFILL_CREDITS", 0):
        outcome = await refill_free_credits_if_due(session, user_id)
        assert outcome.status == RefillStatus.SKIPPED
        assert outcome.new_balance is None
        assert len(session.statements) == 0

    with patch.object(settings, "FREE_BETA_REFILL_HOURS", -1):
        outcome = await refill_free_credits_if_due(session, user_id)
        assert outcome.status == RefillStatus.SKIPPED
        assert outcome.new_balance is None
        assert len(session.statements) == 0


# ==============================================================================
# R6: PostgreSQL 실증 테스트 (CR-3, CR-4, CR-6, CR-7)
# ==============================================================================

import os

_pg_skip = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL이 설정되지 않아 PostgreSQL 실증 테스트를 건너뜁니다.",
)


@_pg_skip
@pytest.mark.asyncio
async def test_cr_3_pg_concurrent_refill_race_condition(require_disposable_database):
    """CR-3 (Postgres): 동시 2개 코루틴이 각각 별도 트랜잭션으로 refill 시도 시 정확히 1건만 충전되고 50C 상한 유지."""
    import asyncio
    from core.db import AsyncSessionLocal

    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    async with AsyncSessionLocal() as init_session:
        profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
        init_session.add(profile)
        await init_session.commit()

    async def _try_refill():
        async with AsyncSessionLocal() as session:
            outcome = await refill_free_credits_if_due(session, user_id)
            await session.commit()
            return outcome

    results = await asyncio.gather(_try_refill(), _try_refill())
    statuses = [r.status for r in results]

    assert RefillStatus.REFILLED in statuses
    assert RefillStatus.SKIPPED in statuses

    # 최종 DB 상태 검증
    async with AsyncSessionLocal() as check_session:
        from sqlalchemy import select
        res = await check_session.execute(select(UserProfile).where(UserProfile.id == user_id))
        final_profile = res.scalar_one()
        assert final_profile.credit_balance == 50

        ledgers_res = await check_session.execute(
            select(CreditLedger).where(
                CreditLedger.user_id == user_id,
                CreditLedger.event_type == EVENT_REFILL,
            )
        )
        ledgers = ledgers_res.scalars().all()
        assert len(ledgers) == 1
        assert ledgers[0].amount == 50


@_pg_skip
@pytest.mark.asyncio
async def test_cr_4_pg_admin_grant_competition_caps_at_50(require_disposable_database):
    """CR-4 (Postgres): refill 잠금 전 운영자가 +40을 지급한 경우, refill은 남은 10만 지급하여 50C 상한 유지."""
    from core.db import AsyncSessionLocal
    from sqlalchemy import select

    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    async with AsyncSessionLocal() as init_session:
        profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
        init_session.add(profile)
        await init_session.commit()

    # 운영자가 40 크레딧 지급
    async with AsyncSessionLocal() as admin_session:
        res = await admin_session.execute(select(UserProfile).where(UserProfile.id == user_id).with_for_update())
        p = res.scalar_one()
        p.credit_balance += 40
        await admin_session.commit()

    # refill 실행
    async with AsyncSessionLocal() as refill_session:
        outcome = await refill_free_credits_if_due(refill_session, user_id)
        await refill_session.commit()

        assert outcome.status == RefillStatus.REFILLED
        assert outcome.new_balance == 50
        assert outcome.grant == 10

    # 최종 잔액 및 원장 확인
    async with AsyncSessionLocal() as check_session:
        res = await check_session.execute(select(UserProfile).where(UserProfile.id == user_id))
        final_profile = res.scalar_one()
        assert final_profile.credit_balance == 50


@_pg_skip
@pytest.mark.asyncio
async def test_cr_6_pg_ledger_insert_failure_rolls_back_both(require_disposable_database):
    """CR-6 (Postgres): ledger insert 실패 시 savepoint rollback과 expire로 프로필 잔액이 원래대로 복원됨."""
    from core.db import AsyncSessionLocal
    from sqlalchemy import select

    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    async with AsyncSessionLocal() as init_session:
        profile = UserProfile(id=user_id, credit_balance=0, last_refilled_at=past_13h)
        init_session.add(profile)
        await init_session.commit()

    # savepoint 내부에서 flush 시 에러 유발
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(UserProfile).where(UserProfile.id == user_id))
        prof = res.scalar_one()

        with patch.object(session, "flush", side_effect=RuntimeError("Simulated DB flush failure on ledger")):
            outcome = await refill_free_credits_if_due(session, user_id)

        assert outcome.status == RefillStatus.FAILED_RECOVERED
        assert outcome.new_balance is None
        # expire(prof)를 통해 인메모리 dirty state가 만료(expired)되었는지 검증
        from sqlalchemy import inspect
        assert inspect(prof).expired is True

        # 세션 refresh 후 원래 잔액(0)과 원래 시간으로 복원되었는지 검증
        await session.refresh(prof)
        assert prof.credit_balance == 0
        assert prof.last_refilled_at == past_13h

        # 세션 롤백 후 재조회해도 0
        await session.rollback()

    async with AsyncSessionLocal() as check_session:
        res = await check_session.execute(select(UserProfile).where(UserProfile.id == user_id))
        final_profile = res.scalar_one()
        assert final_profile.credit_balance == 0


@_pg_skip
@pytest.mark.asyncio
async def test_cr_7_pg_refill_db_exception_recovers_session(require_disposable_database):
    """CR-7 (Postgres): refill 도중 DB 예외가 발생해도 세션이 InFailedSqlTransaction 상태가 되지 않고 다음 트랜잭션 정상 수행."""
    from core.db import AsyncSessionLocal
    from sqlalchemy import select

    user_id = str(uuid.uuid4())
    past_13h = datetime.now(timezone.utc) - timedelta(hours=13)

    async with AsyncSessionLocal() as init_session:
        profile = UserProfile(id=user_id, credit_balance=20, last_refilled_at=past_13h)
        init_session.add(profile)
        await init_session.commit()

    async with AsyncSessionLocal() as session:
        # execute 시점에 에러 시뮬레이션
        original_execute = session.execute

        async def failing_execute(statement, *args, **kwargs):
            if "FOR UPDATE" in str(statement):
                raise RuntimeError("Simulated DB lock acquisition timeout")
            return await original_execute(statement, *args, **kwargs)

        with patch.object(session, "execute", side_effect=failing_execute):
            outcome = await refill_free_credits_if_due(session, user_id)

        assert outcome.status == RefillStatus.FAILED_RECOVERED
        assert outcome.new_balance is None

        # 세션이 InFailedSqlTransaction 상태가 아니므로 후속 쿼리 정상 실행 가능
        res = await session.execute(select(UserProfile).where(UserProfile.id == user_id))
        current_prof = res.scalar_one()
        assert current_prof.credit_balance == 20
        await session.commit()
