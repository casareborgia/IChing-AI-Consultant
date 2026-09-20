"""Supabase credit tables: least privilege, RLS, and welcome normalization.

Revision ID: e8b72c4a91d0
Revises: c3a91f4d6b27

This migration is intentionally safe for both vanilla PostgreSQL and Supabase:
Supabase-specific roles and the auth trigger are changed only when they exist.
It does not create users or expose rows.  Existing legacy welcome rows are
identified only by the exact historical reason and amount before they receive
the event identity required by the T03 ledger contract.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "e8b72c4a91d0"
down_revision: Union[str, Sequence[str], None] = "c3a91f4d6b27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_WELCOME_REASON = "신규 가입 웰컴 크레딧"


def _install_supabase_signup_function(*, include_event_type: bool) -> None:
    """Replace the existing Supabase signup function without creating one elsewhere."""
    ledger_columns = "user_id, amount, reason, event_type" if include_event_type else "user_id, amount, reason"
    ledger_values = (
        f"NEW.id, 50, '{_WELCOME_REASON}', 'WELCOME'"
        if include_event_type
        else f"NEW.id, 50, '{_WELCOME_REASON}'"
    )

    op.execute(
        f"""
        DO $migration$
        BEGIN
            IF to_regclass('auth.users') IS NOT NULL
               AND to_regprocedure('public.handle_new_user()') IS NOT NULL THEN
                EXECUTE $function$
                    CREATE OR REPLACE FUNCTION public.handle_new_user()
                    RETURNS trigger
                    LANGUAGE plpgsql
                    SECURITY DEFINER
                    SET search_path = pg_catalog
                    AS $body$
                    DECLARE
                        user_nickname TEXT;
                        user_avatar TEXT;
                    BEGIN
                        user_nickname := COALESCE(
                            NEW.raw_user_meta_data->>'full_name',
                            NEW.raw_user_meta_data->>'name',
                            NEW.raw_user_meta_data->>'nickname',
                            NEW.raw_user_meta_data->>'preferred_username',
                            NEW.raw_user_meta_data->>'user_name',
                            '내담자'
                        );
                        user_avatar := COALESCE(
                            NEW.raw_user_meta_data->>'avatar_url',
                            NEW.raw_user_meta_data->>'picture',
                            NEW.raw_user_meta_data->>'profile_image_url',
                            NULL
                        );

                        INSERT INTO public.profiles
                            (id, email, nickname, avatar_url, credit_balance)
                        VALUES
                            (NEW.id, NEW.email, user_nickname, user_avatar, 50)
                        ON CONFLICT (id) DO UPDATE SET
                            email = COALESCE(EXCLUDED.email, public.profiles.email),
                            nickname = COALESCE(EXCLUDED.nickname, public.profiles.nickname),
                            avatar_url = COALESCE(EXCLUDED.avatar_url, public.profiles.avatar_url),
                            updated_at = NOW();

                        INSERT INTO public.credit_ledger ({ledger_columns})
                        VALUES ({ledger_values})
                        ON CONFLICT DO NOTHING;

                        RETURN NEW;
                    EXCEPTION
                        WHEN OTHERS THEN
                            RAISE WARNING 'handle_new_user failed (SQLSTATE=%)', SQLSTATE;
                            RETURN NEW;
                    END;
                    $body$
                $function$;
            END IF;
        END
        $migration$;
        """
    )


def _set_role_grants() -> None:
    """Apply least-privilege grants only for roles present in Supabase."""
    for table in ("profiles", "credit_ledger", "credit_operations"):
        op.execute(
            f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC"
        )
    op.execute(
        """
        DO $roles$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.profiles FROM anon;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_ledger FROM anon;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_operations FROM anon;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.profiles FROM authenticated;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_ledger FROM authenticated;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_operations FROM authenticated;
                GRANT SELECT ON TABLE public.profiles TO authenticated;
                GRANT SELECT ON TABLE public.credit_ledger TO authenticated;
            END IF;

            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                REVOKE ALL PRIVILEGES ON TABLE public.profiles FROM service_role;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_ledger FROM service_role;
                REVOKE ALL PRIVILEGES ON TABLE public.credit_operations FROM service_role;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.profiles TO service_role;
                GRANT SELECT, INSERT ON TABLE public.credit_ledger TO service_role;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.credit_operations TO service_role;
            END IF;
        END
        $roles$;
        """
    )


def _normalize_read_policies() -> None:
    """Replace only the known historical policies; reject unknown policy drift."""
    op.execute(
        """
        DO $policies$
        DECLARE
            unexpected_count BIGINT;
        BEGIN
            SELECT count(*) INTO unexpected_count
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename IN ('profiles', 'credit_ledger', 'credit_operations')
              AND policyname NOT IN (
                  'Users can view own profile',
                  'Users can view own credit ledger',
                  '자신의 프로필만 조회 가능',
                  '자신의 크레딧 내역만 조회 가능',
                  'profiles_select_own',
                  'credit_ledger_select_own'
              );

            IF unexpected_count > 0 THEN
                RAISE EXCEPTION
                    '알 수 없는 credit-table RLS 정책 %건이 있어 중단합니다.',
                    unexpected_count;
            END IF;
        END
        $policies$;
        """
    )
    op.execute('DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles')
    op.execute('DROP POLICY IF EXISTS "자신의 프로필만 조회 가능" ON public.profiles')
    op.execute("DROP POLICY IF EXISTS profiles_select_own ON public.profiles")
    op.execute(
        'DROP POLICY IF EXISTS "Users can view own credit ledger" '
        "ON public.credit_ledger"
    )
    op.execute(
        'DROP POLICY IF EXISTS "자신의 크레딧 내역만 조회 가능" '
        "ON public.credit_ledger"
    )
    op.execute("DROP POLICY IF EXISTS credit_ledger_select_own ON public.credit_ledger")
    op.execute(
        """
        DO $create_policies$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
               AND to_regprocedure('auth.uid()') IS NOT NULL THEN
                EXECUTE 'CREATE POLICY profiles_select_own '
                        'ON public.profiles FOR SELECT TO authenticated '
                        'USING ((SELECT auth.uid()) = id)';
                EXECUTE 'CREATE POLICY credit_ledger_select_own '
                        'ON public.credit_ledger FOR SELECT TO authenticated '
                        'USING ((SELECT auth.uid()) = user_id)';
            END IF;
        END
        $create_policies$;
        """
    )


def upgrade() -> None:
    # A legacy trigger created these rows before event_type existed.  Reject
    # ambiguous data instead of guessing which duplicate or amount is valid.
    op.execute(
        f"""
        DO $welcome$
        DECLARE
            wrong_amount_count BIGINT;
            duplicate_user_count BIGINT;
        BEGIN
            SELECT count(*) INTO wrong_amount_count
            FROM public.credit_ledger
            WHERE event_type IS NULL
              AND reason = '{_WELCOME_REASON}'
              AND amount <> 50;

            IF wrong_amount_count > 0 THEN
                RAISE EXCEPTION
                    '금액이 50이 아닌 기존 웰컴 원장 %건이 있어 중단합니다.',
                    wrong_amount_count;
            END IF;

            SELECT count(*) INTO duplicate_user_count
            FROM (
                SELECT user_id
                FROM public.credit_ledger
                WHERE event_type = 'WELCOME'
                   OR (
                       event_type IS NULL
                       AND reason = '{_WELCOME_REASON}'
                       AND amount = 50
                   )
                GROUP BY user_id
                HAVING count(*) > 1
            ) duplicates;

            IF duplicate_user_count > 0 THEN
                RAISE EXCEPTION
                    '중복된 기존 웰컴 원장 사용자 %명이 있어 중단합니다.',
                    duplicate_user_count;
            END IF;
        END
        $welcome$;
        """
    )
    op.execute(
        f"""
        UPDATE public.credit_ledger
        SET event_type = 'WELCOME'
        WHERE event_type IS NULL
          AND reason = '{_WELCOME_REASON}'
          AND amount = 50
        """
    )

    op.execute("ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.credit_ledger ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.credit_operations ENABLE ROW LEVEL SECURITY")
    _set_role_grants()
    _normalize_read_policies()
    _install_supabase_signup_function(include_event_type=True)

    # These legacy helpers are not application RPCs.  T03 performs credit writes
    # through the backend operation service and RAG uses direct parameterized SQL.
    # Keep database objects for compatibility, but remove every Data API execute
    # path.  Also pin search_path on the two functions not replaced above.
    op.execute(
        """
        DO $function_grants$
        DECLARE
            target RECORD;
            role_name TEXT;
        BEGIN
            FOR target IN
                SELECT p.oid::regprocedure AS signature, p.proname
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND p.proname IN (
                      'handle_new_user',
                      'deduct_credit',
                      'rls_auto_enable',
                      'match_chunks'
                  )
            LOOP
                EXECUTE format(
                    'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC',
                    target.signature
                );
                FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated', 'service_role']
                LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                        EXECUTE format(
                            'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM %I',
                            target.signature,
                            role_name
                        );
                    END IF;
                END LOOP;

                IF target.proname = 'deduct_credit' THEN
                    EXECUTE format(
                        'ALTER FUNCTION %s SET search_path = pg_catalog',
                        target.signature
                    );
                ELSIF target.proname = 'match_chunks' THEN
                    EXECUTE format(
                        'ALTER FUNCTION %s SET search_path = pg_catalog, public',
                        target.signature
                    );
                END IF;
            END LOOP;
        END
        $function_grants$;
        """
    )


def downgrade() -> None:
    # Security grants and RLS stay hardened on an isolated downgrade.  Regranting
    # TRUNCATE/write or disabling RLS would make rollback less safe.  The earlier
    # C3 downgrade subsequently drops credit_operations and the event columns.
    # Restore only trigger compatibility with the C3 schema before that happens.
    _install_supabase_signup_function(include_event_type=False)
