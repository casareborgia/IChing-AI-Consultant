"""Static safety contract for the Supabase credit hardening migration."""

import pathlib


_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "e8b72c4a91d0_supabase_credit_rls_and_welcome.py"
)
_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _source() -> str:
    return _MIGRATION.read_text(encoding="utf-8")


def test_migration_is_the_only_child_of_t03():
    source = _source()
    assert 'revision: str = "e8b72c4a91d0"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = "c3a91f4d6b27"' in source


def test_all_credit_tables_enable_rls():
    source = _source()
    for table in ("profiles", "credit_ledger", "credit_operations"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in source


def test_client_roles_have_no_direct_operation_access_or_write_access():
    source = _source()
    for role in ("anon", "authenticated"):
        assert (
            "REVOKE ALL PRIVILEGES ON TABLE public.credit_operations "
            f"FROM {role}"
        ) in source
    assert "GRANT SELECT ON TABLE public.profiles TO authenticated" in source
    assert "GRANT SELECT ON TABLE public.credit_ledger TO authenticated" in source
    assert "GRANT" not in "\n".join(
        line for line in source.splitlines()
        if "credit_operations TO authenticated" in line
    )


def test_service_role_gets_only_runtime_crud_subset():
    source = _source()
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.profiles TO service_role" in source
    assert "GRANT SELECT, INSERT ON TABLE public.credit_ledger TO service_role" in source
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE public.credit_operations TO service_role" in source
    assert "GRANT TRUNCATE" not in source
    assert "GRANT DELETE" not in source


def test_policies_are_owned_select_rules_for_authenticated_only():
    source = _source()
    assert "('profiles', 'credit_ledger', 'credit_operations')" in source
    assert "ON public.profiles FOR SELECT TO authenticated" in source
    assert "USING ((SELECT auth.uid()) = id)" in source
    assert "ON public.credit_ledger FOR SELECT TO authenticated" in source
    assert "USING ((SELECT auth.uid()) = user_id)" in source
    assert "CREATE POLICY" not in "\n".join(
        line for line in source.splitlines()
        if "credit_operations" in line
    )


def test_legacy_welcome_backfill_is_exact_and_fails_on_ambiguity():
    source = _source()
    assert "SET event_type = 'WELCOME'" in source
    assert "reason = '{_WELCOME_REASON}'" in source
    assert "AND amount = 50" in source
    assert "wrong_amount_count" in source
    assert "duplicate_user_count" in source


def test_signup_function_writes_welcome_event_and_has_safe_search_path():
    source = _source()
    assert "SET search_path = pg_catalog" in source
    assert "NEW.id, 50, '{_WELCOME_REASON}', 'WELCOME'" in source
    assert "'handle_new_user'" in source


def test_legacy_security_definer_and_unused_search_rpc_are_not_public():
    source = _source()
    for function_name in ("deduct_credit", "rls_auto_enable", "match_chunks"):
        assert f"'{function_name}'" in source
    assert "REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC" in source
    assert "ARRAY['anon', 'authenticated', 'service_role']" in source
    assert "ALTER FUNCTION %s SET search_path = pg_catalog" in source


def test_downgrade_does_not_relax_security_or_delete_credit_data():
    source = _source()
    downgrade = source[source.index("def downgrade()") :]
    for forbidden in (
        "DISABLE ROW LEVEL SECURITY",
        "GRANT ALL",
        "GRANT TRUNCATE",
        "DELETE FROM",
        "DROP TABLE",
        "DROP COLUMN",
    ):
        assert forbidden not in downgrade


def test_seed_paths_cannot_recreate_deprecated_credit_rpc_or_signup_function():
    for relative_path in (
        "scripts/export_production_seed.py",
        "scripts/supabase_production_seed.sql",
    ):
        source = (_ROOT / relative_path).read_text(encoding="utf-8")
        assert "CREATE OR REPLACE FUNCTION public.deduct_credit" not in source
        assert "CREATE OR REPLACE FUNCTION public.handle_new_user" not in source
