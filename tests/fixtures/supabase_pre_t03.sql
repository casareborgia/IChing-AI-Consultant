-- Synthetic Supabase-like PRE_T03 fixture for a disposable local database only.
-- No production identifiers or user content are present.

CREATE TABLE public.test_environment_marker (
    marker_key TEXT PRIMARY KEY,
    marker_value TEXT NOT NULL
);
INSERT INTO public.test_environment_marker(marker_key, marker_value)
VALUES ('purpose', 'ICHING_DISPOSABLE_TEST_DB_V1');

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END
$roles$;

CREATE SCHEMA auth;
CREATE FUNCTION auth.uid()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

CREATE TABLE auth.users (
    id UUID PRIMARY KEY,
    email TEXT,
    raw_user_meta_data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT,
    nickname TEXT,
    avatar_url TEXT,
    credit_balance INTEGER DEFAULT 50 CHECK (credit_balance >= 0),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_refilled_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE public.credit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.credit_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can view own credit ledger"
    ON public.credit_ledger FOR SELECT USING (auth.uid() = user_id);

GRANT ALL PRIVILEGES ON TABLE public.profiles TO anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON TABLE public.credit_ledger TO anon, authenticated, service_role;

CREATE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.profiles (id, email, nickname, credit_balance)
    VALUES (NEW.id, NEW.email, 'fixture-user', 50);
    INSERT INTO public.credit_ledger (user_id, amount, reason)
    VALUES (NEW.id, 50, '신규 가입 웰컴 크레딧');
    RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

CREATE FUNCTION public.deduct_credit(target_user_id UUID, deduct_amount INTEGER)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.profiles
    SET credit_balance = credit_balance - deduct_amount
    WHERE id = target_user_id AND credit_balance >= deduct_amount;
END;
$$;

CREATE FUNCTION public.rls_auto_enable()
RETURNS event_trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    NULL;
END;
$$;

CREATE FUNCTION public.match_chunks(
    query_embedding vector,
    match_threshold DOUBLE PRECISION DEFAULT 0.3,
    match_count INTEGER DEFAULT 5
)
RETURNS TABLE(id BIGINT)
LANGUAGE sql
STABLE
AS $$
    SELECT NULL::BIGINT WHERE false
$$;

GRANT EXECUTE ON FUNCTION public.deduct_credit(UUID, INTEGER)
    TO PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rls_auto_enable()
    TO PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.match_chunks(vector, DOUBLE PRECISION, INTEGER)
    TO PUBLIC, anon, authenticated, service_role;

INSERT INTO auth.users (id, email)
VALUES
    ('00000000-0000-4000-8000-000000000001', 'fixture-1@example.invalid'),
    ('00000000-0000-4000-8000-000000000002', 'fixture-2@example.invalid');
