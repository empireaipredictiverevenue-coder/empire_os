"""REV051 staged SQL safety and real PG18 isolated test harness invariants.

Running pytest never connects to EmpireDB or applies a migration. Actual
SQL semantics are separately tested using the opt-in ephemeral PostgreSQL
script with a private Unix socket and synthetic test-only rows.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/051_predictive_revenue_event_reader_held.sql"
CATALOG=ROOT/"scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql"
FIXTURE=ROOT/"scripts/test_predictive_revenue_event_reader_051_ephemeral.sh"


def test_staged_role_function_contract():
    text=MIGRATION.read_text()
    assert "STAGED ONLY" in text
    assert "REV051_PRIVILEGED_DBA_REQUIRED" in text
    assert "REV051_EXISTING_ROLE_REVIEW_BEFORE_CHANGE" in text
    assert "REV051_EXISTING_FUNCTION_REVIEW_BEFORE_CHANGE" in text
    assert text.startswith("-- EmpireDB 051")
    assert "BEGIN;" in text
    assert text.rstrip().endswith("COMMIT;")
    assert "SET LOCAL ROLE empiredb_migrator" in text
    assert "NOLOGIN NOINHERIT NOSUPERUSER" in text
    assert "SET search_path = ''" in text
    assert "SECURITY DEFINER" in text
    assert "REVOKE ALL ON FUNCTION" in text
    assert "GRANT EXECUTE ON FUNCTION" in text
    assert "TO empire_predictive_revenue_evidence_reader" in text
    assert "GRANT USAGE ON SCHEMA public" in text
    assert "CREATE LOGIN" not in text.upper()


def test_tenant_identity_bound_to_trusted_postgres_session():
    sql=MIGRATION.read_text()
    assert "event_buyer.org_id=public.empire_current_tenant_id()" in sql
    assert "p_tenant=public.empire_current_tenant_id()::text" in sql
    assert "event_buyer.org_id=order_buyer.org_id" in sql
    assert "e.buyer_id=o.buyer_id" in sql
    assert "o.id=e.fulfilment_order_id" in sql
    assert "e.product_id=o.product_id" in sql
    assert "e.amount_cents=o.price_cents" in sql
    assert "e.payload->>'actual_revenue'='true'" in sql
    assert "e.event_type='revenue_recognized'" in sql
    assert "o.state IN ('settled','outcome_captured')" in sql
    assert "o.settled_at IS NOT NULL" in sql
    assert "e.payload->'causal_lineage' IS NOT NULL" in sql
    assert "e.payload->'causal_lineage' <> '{}'::jsonb" in sql
    assert "e.payload->'causal_lineage'\n       IS NOT DISTINCT FROM o.commercial_payload->'causal_lineage'" in sql


def test_no_unapproved_login_access_or_financial_write_granted():
    sql=MIGRATION.read_text()
    for forbidden in (
        "GRANT empire_predictive_revenue_evidence_reader TO",
        "CREATE ROLE empire_predictive_revenue_evidence_reader LOGIN",
        "GRANT SELECT ON",
        "GRANT INSERT ON",
        "GRANT UPDATE ON",
        "GRANT DELETE ON",
        "GRANT ALL ON",
        "INSERT INTO public.commercial_events",
        "UPDATE public.commercial_events",
        "INSERT INTO public.fulfilment_orders",
        "UPDATE public.fulfilment_orders",
        "DROP TABLE",
        "TRUNCATE",
    ):
        assert forbidden not in sql
    assert "-- Deliberately DO NOT grant membership" in sql


def test_pg18_exact_locked_search_path_encoding_and_hold_semantics():
    sql=CATALOG.read_text()
    assert "proconfig=ARRAY['search_path=']::text[]" in sql
    assert '''proconfig=ARRAY['search_path=""']::text[]''' in sql
    assert "function_security_definer_stable_locked_path" in sql
    assert "CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN" in sql
    assert "HOLD_EVENT_READER_CATALOG_NOT_PROVEN" in sql
    assert "dedicated_login_member_exists" in sql
    assert "'customer_report_release_authorized',false" in sql


def test_isolated_fixture_is_not_a_prod_database_runner():
    script=FIXTURE.read_text()
    assert "mktemp -d /tmp/empire-rev051-fixture-" in script
    assert "listen_addresses=''" in script
    assert '-k $scratch/socket' in script
    assert "trap cleanup EXIT" in script
    assert "CREATE DATABASE empiredb OWNER fixture_admin" in script
    assert 'scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql' in script
    assert "tenant_alpha_cross=0" in script
    assert "direct_table_read=DENIED" in script
    assert "production=UNTOUCHED" in script
