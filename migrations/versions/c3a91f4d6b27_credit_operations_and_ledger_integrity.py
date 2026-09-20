"""credit operations, ledger event identity and balance integrity

Revision ID: c3a91f4d6b27
Revises: d7f4a1c2e8b9

크레딧 예약을 상담 실행에서 떼어내기 위한 스키마다. 세 가지를 DB가 직접 막는다.

  · operation 하나당 debit/release 원장 이벤트 각각 최대 1건
  · 사용자당 웰컴 크레딧 1건
  · 잔액 음수

`profiles`와 `credit_ledger`는 원래 Supabase 쪽 SQL이 만든 테이블이라 alembic이
소유하지 않는다. 그래서 이 마이그레이션은 멱등 DDL(`IF NOT EXISTS`, `DO` 블록)로
'있으면 보강하고 없으면 만든다'를 표현한다. 런타임 inspection 대신 이렇게 쓴 이유는
`alembic upgrade --sql` 오프라인 모드에서도 그대로 검토 가능한 SQL이 나오게 하려는
것이다. 빈 PostgreSQL에 `alembic upgrade head`만 해도 이 스키마가 선다.

downgrade는 이번 마이그레이션이 더한 것만 되돌린다. `profiles`와 `credit_ledger`
테이블 자체와 그 안의 행은 건드리지 않는다 — 원래 우리 것이 아니었고, 지우면
잔액과 장부가 통째로 날아간다. 원장은 append-only라 되돌릴 때도 과거 입출금
기록은 그대로 읽을 수 있어야 한다.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c3a91f4d6b27"
down_revision: Union[str, Sequence[str], None] = "d7f4a1c2e8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. profiles — Supabase가 이미 만들었으면 건드리지 않고, 없으면 만든다.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id UUID PRIMARY KEY,
            email TEXT,
            nickname TEXT,
            avatar_url TEXT,
            credit_balance INTEGER NOT NULL DEFAULT 50,
            last_refilled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # 음수 잔액이 이미 있으면 조용히 고치지 않는다. 잔액을 임의로 끌어올리는 것은
    # 마이그레이션이 할 일이 아니다. 원인을 확인하고 보정한 뒤 다시 올리게 한다.
    op.execute(
        """
        DO $$
        DECLARE
            negative_count BIGINT;
        BEGIN
            SELECT count(*) INTO negative_count
            FROM profiles WHERE credit_balance < 0;

            IF negative_count > 0 THEN
                RAISE EXCEPTION
                    'credit_balance가 음수인 프로필 %건이 있어 CHECK 제약을 걸 수 '
                    '없습니다. 원인을 확인하고 보정한 뒤 다시 실행하십시오.',
                    negative_count;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_profiles_credit_balance_non_negative'
            ) THEN
                ALTER TABLE profiles
                ADD CONSTRAINT ck_profiles_credit_balance_non_negative
                CHECK (credit_balance >= 0);
            END IF;
        END $$
        """
    )

    # 2. credit_operations — 이번에 새로 생기는, alembic이 온전히 소유하는 표.
    #    한 번의 POST가 여기 한 행이고, 결제 의미는 이 행의 status 하나로 정해진다.
    op.execute(
        """
        CREATE TABLE credit_operations (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL
                REFERENCES profiles(id) ON DELETE CASCADE,
            endpoint VARCHAR(32) NOT NULL,
            idempotency_key VARCHAR(255) NOT NULL,
            request_hash VARCHAR(64) NOT NULL,
            status VARCHAR(16) NOT NULL,
            amount INTEGER NOT NULL,
            credit_delta INTEGER,
            fencing_token UUID NOT NULL,
            lease_expires_at TIMESTAMPTZ,
            response_snapshot JSONB,
            error_code VARCHAR(64),
            error_message TEXT,
            balance_snapshot INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_credit_operations_user_endpoint_key
                UNIQUE (user_id, endpoint, idempotency_key),
            CONSTRAINT ck_credit_operations_status
                CHECK (status IN ('PROCESSING', 'SUCCEEDED', 'RELEASED', 'REJECTED')),
            CONSTRAINT ck_credit_operations_amount_non_negative
                CHECK (amount >= 0)
        )
        """
    )
    op.execute("CREATE INDEX ix_credit_operations_user_id ON credit_operations (user_id)")
    # 만료된 예약을 찾는 복구 스캔용. 이미 종결된 행은 인덱스에 담지 않는다.
    op.execute(
        """
        CREATE INDEX ix_credit_operations_stale_lease
        ON credit_operations (lease_expires_at)
        WHERE status = 'PROCESSING'
        """
    )

    # 3. credit_ledger — operation/event 식별을 더한다.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL
                REFERENCES profiles(id) ON DELETE CASCADE,
            amount INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_ledger_user_id ON credit_ledger (user_id)")
    op.execute("ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS operation_id UUID")
    op.execute("ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS event_type VARCHAR(16)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_credit_ledger_operation_id'
            ) THEN
                ALTER TABLE credit_ledger
                ADD CONSTRAINT fk_credit_ledger_operation_id
                FOREIGN KEY (operation_id)
                REFERENCES credit_operations(id) ON DELETE CASCADE;
            END IF;
        END $$
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_credit_ledger_operation_id "
        "ON credit_ledger (operation_id)"
    )

    # 기존 행은 operation_id와 event_type이 모두 NULL이라 아래 두 partial 인덱스
    # 어디에도 들어가지 않는다. 과거 데이터가 있어도 인덱스 생성이 실패하지 않는다.
    #
    # operation 하나당 DEBIT 1건, RELEASE 1건까지. 늦은 응답과 lease 복구가
    # 동시에 환불을 시도해도 둘 중 하나만 성사된다.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_ledger_operation_event
        ON credit_ledger (operation_id, event_type)
        WHERE operation_id IS NOT NULL
        """
    )
    # 사용자당 웰컴 1건. 동시 가입 경합에서도 두 번 지급되지 않는다.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_ledger_welcome_per_user
        ON credit_ledger (user_id)
        WHERE event_type = 'WELCOME'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_credit_ledger_welcome_per_user")
    op.execute("DROP INDEX IF EXISTS uq_credit_ledger_operation_event")
    op.execute("DROP INDEX IF EXISTS ix_credit_ledger_operation_id")
    # 장부 행 자체는 남긴다. operation 연결 정보만 떼어낸다.
    op.execute(
        "ALTER TABLE IF EXISTS credit_ledger "
        "DROP CONSTRAINT IF EXISTS fk_credit_ledger_operation_id"
    )
    op.execute("ALTER TABLE IF EXISTS credit_ledger DROP COLUMN IF EXISTS event_type")
    op.execute("ALTER TABLE IF EXISTS credit_ledger DROP COLUMN IF EXISTS operation_id")

    op.execute("DROP INDEX IF EXISTS ix_credit_operations_stale_lease")
    op.execute("DROP INDEX IF EXISTS ix_credit_operations_user_id")
    op.execute("DROP TABLE IF EXISTS credit_operations")

    op.execute(
        "ALTER TABLE IF EXISTS profiles "
        "DROP CONSTRAINT IF EXISTS ck_profiles_credit_balance_non_negative"
    )
