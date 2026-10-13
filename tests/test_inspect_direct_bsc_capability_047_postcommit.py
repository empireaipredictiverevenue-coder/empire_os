"""Migration 047 post-COMMIT forensics are strictly catalog-only.

The original transaction already COMMITTED. Never rerun the migration
to obtain additional diagnostic information.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERY = ROOT / "scripts/inspect_direct_bsc_capability_047_postcommit.sql"


def test_security_diagnostic_is_readonly_catalog_only():
    sql = QUERY.read_text()
    assert "BEGIN READ ONLY;" in sql
    assert "ROLLBACK;" in sql
    assert "SET LOCAL statement_timeout=" in sql
    assert "pg_catalog.pg_class" in sql
    assert "pg_catalog.pg_proc" in sql
    assert "pg_catalog.pg_policy" in sql
    assert "pg_catalog.pg_default_acl" in sql
    assert "pg_catalog.aclexplode" in sql
    assert "FROM public.direct_bsc_buyer_capabilities" not in sql
    for forbidden in (
        "CREATE TABLE ", "DROP TABLE ", "ALTER TABLE ",
        "GRANT SELECT", "REVOKE SELECT", "UPDATE public.",
        "INSERT INTO public.", "DELETE FROM public.",
        "ALTER ROLE ", "CREATE ROLE ", "COMMIT;", "pg_catalog.pg_authid",
        "pg_dump", "systemctl restart",
    ):
        assert forbidden not in sql


def test_all_nine_original_postcommit_checks_have_named_proof():
    sql = QUERY.read_text()
    for field in (
        "01_table_exists", "02_forced_rls",
        "03_app_select_denied", "04_payment_approver_select_denied",
        "05_bsc_verifier_select_denied", "06_zero_rls_policies",
        "07_guard_security_definer_owned_by_migrator",
        "08_guard_public_execute_denied", "09_bound_trigger_enabled",
    ):
        assert sql.count("'" + field + "'") == 1
    assert "CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END" in sql


def test_diagnostic_inspects_grants_without_exposing_buyer_records():
    sql = QUERY.read_text()
    assert "FROM pg_catalog.pg_default_acl" in sql
    assert "acl.privilege_type" in sql
    assert "c.relforcerowsecurity" in sql
    assert "granted_to" in sql
    assert "function_granted_to" in sql
    for private_field in ("token_fingerprint", "payer_address",
                          "email", "transaction_hash", "buyer_id"):
        assert private_field not in sql
