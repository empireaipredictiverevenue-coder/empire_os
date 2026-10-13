"""049 v2 SQL contract: isolated owner, no privilege broadening of existing roles."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql"


def test_new_owner_and_caller_are_nologin_and_disjoint():
    sql=SQL.read_text()
    for role in (
        "empire_direct_checkout_status_owner",
        "empire_direct_checkout_status_reader",
    ):
        assert "CREATE ROLE "+role in sql
    assert sql.count("NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE")==2
    assert "AND member.rolname='empiredb_migrator_login'" in sql
    assert "AND m.inherit_option AND m.set_option AND NOT m.admin_option" in sql
    assert "p.polroles=ARRAY[owner_oid]" in sql
    assert "m.member IN (owner_oid,reader_oid)" in sql
    assert "m.roleid IN (owner_oid,reader_oid)" in sql


def test_definition_not_owned_by_general_migrator_or_app():
    sql=SQL.read_text()
    assert "ALTER FUNCTION public.read_direct_bsc_buyer_status(text)" in sql
    assert "OWNER TO empire_direct_checkout_status_owner" in sql
    assert "SECURITY DEFINER SET search_path=''" in sql
    assert "REVOKE ALL ON FUNCTION public.read_direct_bsc_buyer_status(text)" in sql
    assert "FROM PUBLIC, empiredb_app, empiredb_readonly;" in sql
    assert "GRANT EXECUTE ON FUNCTION public.read_direct_bsc_buyer_status(text)" in sql
    assert "TO empire_direct_checkout_status_reader;" in sql
    assert "DIRECT049_UNEXPECTED_FUNCTION_EXECUTE_GRANT" in sql


def test_new_rls_policies_are_select_only_for_isolated_owner():
    sql=SQL.read_text()
    assert sql.count("CREATE POLICY direct_bsc_status_owner_")==4
    for table in (
        "public.direct_bsc_buyer_capabilities",
        "public.fulfilment_orders",
        "public.bsc_payment_requests",
        "public.bsc_payment_evidence",
    ):
        assert "ON "+table+"\n  FOR SELECT TO empire_direct_checkout_status_owner" in sql
    assert "DIRECT049_PARENT_POLICY_BASELINE_DRIFT" in sql
    assert "('fulfilment_orders',23)" in sql
    assert "('bsc_payment_requests',10)" in sql
    assert "('bsc_payment_evidence',9)" in sql
    for forbidden in (
        "ALTER DEFAULT PRIVILEGES", "REVOKE empiredb_migrator",
        "GRANT empiredb_migrator", "SET LOCAL ROLE empiredb_migrator",
        "GRANT SELECT ON TABLE public.", "CREATE LOGIN",
        "SET BYPASSRLS", "CREATE EXTENSION", "systemctl restart",
    ):
        assert forbidden not in sql


def test_column_scope_and_exact_buyer_and_terms_are_compulsory():
    sql=SQL.read_text()
    assert sql.count("GRANT SELECT (")==4
    for term in (
        "cap.token_fingerprint=p_digest",
        "p.fulfilment_order_id=o.id",
        "p.buyer_id=o.buyer_id",
        "p.amount_usdt = o.price_cents::numeric / 100",
        "p.commercial_terms_sha256",
        "e.fulfilment_order_id=o.id",
        "cap.revoked_at IS NULL",
        "cap.expires_at <= p.expires_at",
        "p.settlement_mode='direct'",
    ):
        assert term in sql


def test_migration_is_atomic_fail_close_and_still_unapproved():
    sql=SQL.read_text()
    assert sql.startswith("-- EmpireDB 049 v2 — STAGED, NOT APPROVED FOR PRODUCTION.")
    assert "\nBEGIN;\n" in sql
    assert sql.endswith("\nCOMMIT;\n")
    assert "DIRECT049_CAPABILITY_NOT_SEALED_AFTER_048" in sql
    assert "DIRECT049_UNEXPECTED_MIGRATOR_INCOMING_MEMBERSHIP" in sql
    assert "DIRECT049_READER_OBJECT_ALREADY_EXISTS_RECONCILE" in sql
    assert "DIRECT049_CAPABILITY_POLICY_COUNT_DRIFT" in sql
    assert "ALTER TABLE public.direct_bsc_buyer_capabilities OWNER TO" not in sql
    assert "INSERT INTO public." not in sql
    assert "UPDATE public." not in sql
