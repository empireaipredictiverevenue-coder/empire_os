"""Pin actual isolated PostgreSQL execution of unmodified canonical EmpireDB 041 membership."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/"docs/commercial/EMPIRE_AGENCY_CANONICAL_041_MEMBERSHIP_REUSE_HANDOFF_20261023.md"
REC=ROOT/"docs/commercial/EMPIRE_AGENCY_CANONICAL_041_POSTGRES_REVOCATION_FIXTURE_20261023.json"

def load():
    return json.loads(REC.read_text())

def test_postgresql_unmodified_canonical_041_executes_revocation_checks():
    r=load()
    assert r["status"]=="REAL_POSTGRES_CANONICAL_041_MEMBERSHIP_REVOCATION_FIXTURE_PASS"
    assert r["fixture_db"]=="crm_membership_fixture"
    assert r["canonical_source"]=="migrations/empiredb/041_crm_membership_authority.sql"
    assert r["dedicated_membership_login"]=="empire_crm_membership_login"
    assert r["real_postgresql_auth_and_membership_reader"] is True
    assert r["checks_passed"]==len(r["checks"])==14
    assert all(value is True for value in r["checks"].values())
    for name in (
      "dedicated_reader_denied_direct_member_table",
      "canonical_041_reader_active_owner",
      "canonical_041_reader_revoked_return_none",
      "agency_existing_session_revoked_after_pg_update",
      "agency_operator_cannot_inherit_owner_site_scope",
      "canonical_041_reader_denies_expired_membership",
      "cross_tenant_denied_by_approved_scope",
      "separate_site_grant_still_required",
      "separate_registry_approval_still_required"
    ):
        assert r["checks"][name] is True,name

def test_receipt_clearly_denies_live_db_revendication():
    r=load()
    assert r["live_empiredb_queried"] is False
    assert r["live_user_revoked"] is False
    assert r["production_changes"] is False
    assert r["real_client_credentials"] is False
    assert r["synthetic_site_and_registry_fixture"] is True
    text=DOC.read_text()
    assert "NOT a query or revocation against the live EmpireDB" in text
    assert "owner-approved" in text
    assert "do not authorise credential sharing" in text

def test_pinned_exact_canonical_migration_and_adapter():
    r=load()
    for path,expected in r["source_sha256"].items():
        file=ROOT/path
        assert file.is_file(),path
        assert sha256(file.read_bytes()).hexdigest()==expected,path
    migration=(ROOT/"migrations/empiredb/041_crm_membership_authority.sql").read_text()
    assert "session_user = 'empire_crm_membership_login'" in migration
    adapter=(ROOT/"empire_os/agency_canonical_membership.py").read_text()
    assert "EmpireDbCrmMembershipReader" in adapter
    assert "found.role in (" in adapter and '"owner", "admin"' in adapter
    assert "CREATE ROLE" not in adapter
    assert "psycopg.connect(" not in adapter

def test_runner_forbidden_to_touch_canonical_production():
    script=(ROOT/"scripts/agency_mcp_live_wp_e2e/run_canonical_041_revocation.sh").read_text()
    assert "mktemp -d /tmp/empire_agency_041_sql_" in script
    assert "listen_addresses=''" in script
    assert "crm_membership_fixture" in script
    assert "--auth-host=reject" in script
    assert "trap cleanup EXIT" in script
    assert "CREATE ROLE empire_crm_membership_login LOGIN" in script
    assert "sudo " not in script
    assert "psql -X -q -v ON_ERROR_STOP=1" in script
