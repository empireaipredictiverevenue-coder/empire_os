"""Static invariants of the staged, dedicated consumer-only writer role.

The real PostgreSQL 18 lifecycle/proof runs separately with pg_virtualenv.
No production connection or privileged role creation is made by these tests.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"migrations/empiredb/058_consumer_optin_private_role_staged_20261020.sql"
FIXTURE=ROOT/"scripts/consumer_optin_ephemeral_db_fixture_20261020.sh"
PROBE=ROOT/"scripts/probe_consumer_optin_ephemeral_db_20261020.py"


def test_role_migration_fails_closed_without_nologin_noinherit_preparation():
    s=SQL.read_text()
    assert "CONSUMER058_WRONG_DATABASE" in s
    assert "CONSUMER058_PRIVATE_NOLOGIN_ROLE_NOT_PREPARED" in s
    assert "NOT rolcanlogin AND NOT rolinherit" in s
    assert "NOT rolsuper AND NOT rolbypassrls" in s
    assert "CONSUMER058_EXACT_FIVE_ENFORCED_TABLES_REQUIRED" in s
    assert "CONSUMER058_EXISTING_POLICIES_REQUIRE_MANUAL_REVIEW" in s


def test_public_web_and_business_crm_roles_never_receive_grants():
    s=SQL.read_text()
    assert "SET LOCAL ROLE empiredb_migrator" in s
    assert "TO empire_consumer_optin_writer" in s
    assert "CREATE ROLE empire_consumer_optin_writer" not in s
    assert "GRANT empire_consumer_optin_writer TO" not in s
    assert "TO PUBLIC" not in s
    assert "TO empiredb_app" not in s
    assert "TO founder" not in s
    assert "LOGIN PASSWORD" not in s
    assert s.count("CREATE POLICY consumer_writer_")==5


def test_no_export_delete_or_log_rewrite_permissions():
    s=SQL.read_text()
    assert "GRANT SELECT, INSERT ON TABLE\n  public.empire_consumer_consent_events" in s
    assert "GRANT SELECT, INSERT ON TABLE\n  public.empire_consumer_email_suppressions" in s
    assert "GRANT SELECT, INSERT, UPDATE ON TABLE\n  public.empire_consumer_one_time_tokens" in s
    assert "GRANT DELETE" not in s
    assert "GRANT TRUNCATE" not in s
    assert "GRANT REFERENCES" not in s
    assert "GRANT TRIGGER" not in s


def test_fixture_isolated_role_and_real_db_lifecycle_are_consistent():
    f=FIXTURE.read_text()
    p=PROBE.read_text()
    assert "pg_virtualenv" in (ROOT/"scripts/run_consumer_optin_ephemeral_db_probe_20261020.sh").read_text()
    assert "empire_consumer_optin_fixture" in f
    assert "CREATE ROLE empire_consumer_optin_writer NOLOGIN NOINHERIT" in f
    assert "058_consumer_optin_private_role_staged_20261020.sql" in f
    assert "PUBLIC_OR_APP_CAN_SELECT" in f
    assert "NO_PUBLIC_INSERT" in f
    assert "WRITER_NOLOGIN" in f
    assert 'TEST_ROLE="empire_consumer_optin_writer"' in p
    assert "REAL_POSTGRES_SYNTHETIC_LIFECYCLE_PASS" in p
