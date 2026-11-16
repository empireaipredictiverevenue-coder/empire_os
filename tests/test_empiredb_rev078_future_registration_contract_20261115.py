"""REV078: prospective forecast only, tenant/private, no independent outcome claim."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "migrations/empiredb/078_predictive_future_forecast_registration_held.sql"
RUNNER = ROOT / "scripts/test_empiredb_rev077_ephemeral_20261115.sh"


def test_sql_has_release_guard_and_canonical_empiredb_only():
    source = SQL.read_text()
    assert source.startswith("-- EmpireDB REV078")
    assert "NOT approved for live apply" in source
    assert "current_database()<>'empiredb'" in source
    assert "pg_catalog.pg_is_in_recovery()" in source
    assert "public.empire_current_tenant_id()" in source
    assert "relforcerowsecurity" in source
    assert "REV078_ORIGINAL_RESTRICTED_REGISTRY_READER_REQUIRED" in source
    assert "supabase" not in source.lower()
    assert "SET LOCAL ROLE empiredb_migrator" in source
    assert "NOLOGIN NOINHERIT" in source
    assert "NOBYPASSRLS" in source


def test_forecast_time_is_generated_only_by_database():
    source = SQL.read_text()
    assert "clock_at := pg_catalog.clock_timestamp()" in source
    assert "p_observed_through>=utc_day" in source
    assert "target_day := utc_day+p_horizon_days" in source
    assert "p_observed_through+p_horizon_days<=utc_day" not in source
    assert "'horizon_basis','registration_utc_day'" in source
    assert "|| target_day::text || ':' || p_horizon_days::text" in source
    assert "|| p_observed_through::text || ':' || p_horizon_days::text" not in source
    assert "generated_at" in source
    assert "p_source_evidence_sha256" in source
    assert "p_predicted_value_cents<>pg_catalog.trunc(p_predicted_value_cents)" in source
    assert "'independent_timestamp_custody',false" in source
    assert "'original_source_authentication',false" in source
    assert "'independent_financial_actuals',false" in source
    assert "'calibration_authorized',false" in source


def test_business_role_never_gets_table_dml_or_membership():
    source = SQL.read_text()
    assert "GRANT EXECUTE ON FUNCTION public.register_predictive_revenue_forecast_v1" in source
    assert "TO empire_predictive_forecast_registrar" in source
    assert "GRANT INSERT ON TABLE" not in source
    assert "GRANT UPDATE ON TABLE" not in source
    assert "GRANT DELETE ON TABLE" not in source
    assert "GRANT empire_predictive_forecast_registrar TO" not in source
    assert "CREATE POLICY predictive_registry_prospective_insert" in source
    assert "WITH CHECK (" in source


def test_isolated_test_calls_original_readers_and_denials():
    runner = RUNNER.read_text()
    assert "078_predictive_future_forecast_registration_held.sql" in runner
    assert "FUTURE_ONLY_REGISTRATION_census_a" not in runner  # printed dynamically
    assert "FUTURE_ONLY_REGISTRATION_" in runner
    assert "REGISTRAR_DIRECT_WRITE_AND_REWRITE_DENIED" in runner
    assert "UNBOUND_TENANT_FORECAST_REFUSED" in runner
    assert "INTEGRATED_REGISTRY_CENSUS_STILL_NOT_CALIBRATION" in runner
    assert "psycopg.connect" in runner
    syntax = subprocess.run(["bash", "-n", str(RUNNER)],
                            capture_output=True, text=True, timeout=3)
    assert syntax.returncode == 0


def test_original_tenant_reader_filters_historical_as_of_at_database_source():
    from empire_os.predictive_revenue_tenant_registry_inspector import (
        SCOPED_SQL,
    )
    assert "AND generated_at <= %s" in SCOPED_SQL
    assert "WHERE dimension_key = %s AND metric = %s" in SCOPED_SQL
    assert "ORDER BY generated_at DESC,id DESC LIMIT %s" in SCOPED_SQL
