"""Exact CRM database CONNECT grant release contract."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/grant_crm_three_logins_connect.sql"
FIXTURE=ROOT/"scripts/test_crm_three_connect_grant_isolated.sh"

def test_exact_three_connect_grants_and_fully_guarded_transaction():
    s=SOURCE.read_text()
    assert "BEGIN;" in s and "COMMIT;" in s
    assert "DO $before$" in s and "DO $after$" in s
    assert s.count("GRANT CONNECT ON DATABASE empiredb")==1
    assert "TO empire_crm_auth_login," in s
    assert "empire_crm_membership_login," in s
    assert "empire_crm_tenant_708efd4b53b2;" in s
    assert "CRM_CONNECT_BLOCKED_ALREADY_OR_PARTIALLY_GRANTED" in s
    assert "CRM_CONNECT_BLOCKED_FOUNDER_TENANT_BINDING" in s
    assert "CRM_CONNECT_BLOCKED_FOUNDER_MEMBERSHIP" in s
    assert "rolpassword LIKE 'SCRAM-SHA-256$%'" in s
    assert "pg_catalog.has_database_privilege" in s
    for prohibited in ("GRANT ALL", "GRANT CREATE", "GRANT TEMP",
                       "ALTER ROLE", "CREATE ROLE", "DROP ROLE", "INSERT INTO",
                       "DELETE FROM", "UPDATE public.", "CREATE TABLE",
                       "CREATE FUNCTION", "REVOKE CONNECT"):
        assert prohibited not in s

def test_fixture_hardcoded_to_disposable_pg18():
    s=FIXTURE.read_text()
    assert "pg_virtualenv -v 18" in s
    assert 'PGPORT' in s
    assert '/tmp/pg_virtualenv.' in s
    assert "RERUN_FAIL_CLOSED" in s
    assert "PRODUCTION_DATABASE_TOUCHED=NO" in s
    r=subprocess.run(["bash","-n",str(FIXTURE)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
