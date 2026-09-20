-- Assertions for the disposable Supabase-like CYCLE-04 database fixture.
-- psql must run this file with ON_ERROR_STOP=1.

DO $assertions$
DECLARE
    bad_count BIGINT;
    function_sql TEXT;
BEGIN
    SELECT count(*) INTO bad_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname IN ('profiles', 'credit_ledger', 'credit_operations')
      AND NOT c.relrowsecurity;
    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'RLS disabled on % credit tables', bad_count;
    END IF;

    IF has_table_privilege('anon', 'public.profiles', 'SELECT')
       OR has_table_privilege('anon', 'public.credit_ledger', 'SELECT')
       OR has_table_privilege('anon', 'public.credit_operations', 'SELECT') THEN
        RAISE EXCEPTION 'anon unexpectedly has credit-table read access';
    END IF;

    IF NOT has_table_privilege('authenticated', 'public.profiles', 'SELECT')
       OR NOT has_table_privilege('authenticated', 'public.credit_ledger', 'SELECT') THEN
        RAISE EXCEPTION 'authenticated is missing intended own-row read grants';
    END IF;

    IF has_table_privilege('authenticated', 'public.profiles', 'INSERT,UPDATE,DELETE,TRUNCATE')
       OR has_table_privilege('authenticated', 'public.credit_ledger', 'INSERT,UPDATE,DELETE,TRUNCATE')
       OR has_table_privilege('authenticated', 'public.credit_operations', 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') THEN
        RAISE EXCEPTION 'authenticated unexpectedly has direct credit write/operation access';
    END IF;

    IF NOT has_table_privilege('service_role', 'public.profiles', 'SELECT,INSERT,UPDATE')
       OR NOT has_table_privilege('service_role', 'public.credit_ledger', 'SELECT,INSERT')
       OR NOT has_table_privilege('service_role', 'public.credit_operations', 'SELECT,INSERT,UPDATE')
       OR has_table_privilege('service_role', 'public.credit_operations', 'DELETE,TRUNCATE') THEN
        RAISE EXCEPTION 'service_role privilege set does not match the runtime contract';
    END IF;

    SELECT count(*) INTO bad_count
    FROM pg_policies
    WHERE schemaname = 'public'
      AND (
          (tablename = 'profiles' AND policyname = 'profiles_select_own'
           AND roles = ARRAY['authenticated']::name[] AND cmd = 'SELECT')
          OR
          (tablename = 'credit_ledger' AND policyname = 'credit_ledger_select_own'
           AND roles = ARRAY['authenticated']::name[] AND cmd = 'SELECT')
      );
    IF bad_count <> 2 THEN
        RAISE EXCEPTION 'expected exactly two authenticated own-row policies, got %', bad_count;
    END IF;

    SELECT count(*) INTO bad_count
    FROM public.credit_ledger
    WHERE reason = '신규 가입 웰컴 크레딧' AND event_type <> 'WELCOME';
    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'legacy welcome rows were not normalized';
    END IF;

    IF has_function_privilege('anon', 'public.handle_new_user()', 'EXECUTE')
       OR has_function_privilege('authenticated', 'public.handle_new_user()', 'EXECUTE')
       OR has_function_privilege('service_role', 'public.handle_new_user()', 'EXECUTE') THEN
        RAISE EXCEPTION 'signup trigger function is still directly executable';
    END IF;

    IF has_function_privilege(
           'anon', 'public.deduct_credit(uuid,integer)', 'EXECUTE'
       ) OR has_function_privilege(
           'authenticated', 'public.deduct_credit(uuid,integer)', 'EXECUTE'
       ) OR has_function_privilege(
           'service_role', 'public.deduct_credit(uuid,integer)', 'EXECUTE'
       ) OR has_function_privilege(
           'anon', 'public.rls_auto_enable()', 'EXECUTE'
       ) OR has_function_privilege(
           'authenticated', 'public.rls_auto_enable()', 'EXECUTE'
       ) OR has_function_privilege(
           'service_role', 'public.rls_auto_enable()', 'EXECUTE'
       ) OR has_function_privilege(
           'anon', 'public.match_chunks(vector,double precision,integer)', 'EXECUTE'
       ) OR has_function_privilege(
           'authenticated', 'public.match_chunks(vector,double precision,integer)', 'EXECUTE'
       ) OR has_function_privilege(
           'service_role', 'public.match_chunks(vector,double precision,integer)', 'EXECUTE'
       ) THEN
        RAISE EXCEPTION 'legacy SECURITY DEFINER or unused search RPC remains exposed';
    END IF;

    SELECT count(*) INTO bad_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname IN ('deduct_credit', 'match_chunks')
      AND p.proconfig IS NULL;
    IF bad_count <> 0 THEN
        RAISE EXCEPTION 'legacy functions still have mutable search_path';
    END IF;

    SELECT pg_get_functiondef('public.handle_new_user()'::regprocedure)
    INTO function_sql;
    IF function_sql NOT LIKE '%SET search_path TO ''pg_catalog''%'
       OR function_sql NOT LIKE '%event_type%WELCOME%' THEN
        RAISE EXCEPTION 'signup trigger function is not hardened or welcome-aware';
    END IF;
END
$assertions$;

-- A new synthetic auth row must produce one profile and one identified welcome row.
INSERT INTO auth.users (id, email)
VALUES ('00000000-0000-4000-8000-000000000003', 'fixture-3@example.invalid')
ON CONFLICT (id) DO NOTHING;

DO $trigger_assertion$
DECLARE
    profile_count BIGINT;
    welcome_count BIGINT;
BEGIN
    SELECT count(*) INTO profile_count
    FROM public.profiles
    WHERE id = '00000000-0000-4000-8000-000000000003';
    SELECT count(*) INTO welcome_count
    FROM public.credit_ledger
    WHERE user_id = '00000000-0000-4000-8000-000000000003'
      AND event_type = 'WELCOME'
      AND amount = 50;
    IF profile_count <> 1 OR welcome_count <> 1 THEN
        RAISE EXCEPTION 'signup trigger did not create one profile and one welcome event';
    END IF;
END
$trigger_assertion$;

-- RLS must expose only the authenticated user's own synthetic row.
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config(
    'request.jwt.claim.sub',
    '00000000-0000-4000-8000-000000000003',
    true
);
DO $rls_assertion$
DECLARE
    visible_profiles BIGINT;
    visible_ledger BIGINT;
BEGIN
    SELECT count(*) INTO visible_profiles FROM public.profiles;
    SELECT count(*) INTO visible_ledger FROM public.credit_ledger;
    IF visible_profiles <> 1 OR visible_ledger <> 1 THEN
        RAISE EXCEPTION
            'RLS own-row visibility mismatch: profiles %, ledger %',
            visible_profiles, visible_ledger;
    END IF;
END
$rls_assertion$;
ROLLBACK;
