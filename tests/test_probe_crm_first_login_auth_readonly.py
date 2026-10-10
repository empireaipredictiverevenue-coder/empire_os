"""Catalog-only founder CRM first-login preflight, no credential writes."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"scripts/probe_crm_first_login_auth_readonly.sql"
TESTER=ROOT/"scripts/test_crm_login_auth_preflight_isolated.sh"

def test_no_writes_secrets_or_contact_queries():
    source=SQL.read_text()
    assert source.startswith("-- EmpireDB founder CRM")
    assert "BEGIN TRANSACTION READ ONLY;" in source
    assert source.rstrip().endswith("ROLLBACK;")
    assert "pg_hba_file_rules" in source
    assert "DISTINCT ON (rolename)" in source
    assert "scram-sha-256" in source
    assert "first_login_auth_transport_preflight.v1" in source
    assert "active_founder_owner_verified" in source
    assert "PREPARE_EXACT_LOCAL_SCRAM_AUTH_RULES" in source
    assert "READY_FOR_APPROVED_THREE_LOGIN_PROVISIONING" in source
    assert "database_changes',false" in source
    assert "database_credentials_disclosed',false" in source
    for banned in ("ALTER ROLE", "CREATE ROLE", "DROP ROLE", "GRANT ", "REVOKE ",
                   "UPDATE public.", "INSERT INTO public.", "DELETE FROM public.",
                   "pg_reload_conf(", "ALTER SYSTEM", "COPY public."):
        assert banned not in source

def test_isolated_runner_refuses_non_ephemeral_cluster():
    text=TESTER.read_text()
    assert "pg_virtualenv -v 18" in text
    assert 'PGPORT' in text
    assert "/tmp/pg_virtualenv." in text
    assert "CRM_LOGIN_HBA_LIVE_DATABASE_TOUCHED=NO" in text
    r=subprocess.run(["bash","-n",str(TESTER)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
