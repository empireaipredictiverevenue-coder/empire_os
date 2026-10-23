"""Immutable proof of joined canonical 041 -> guard -> WordPress/MariaDB fixture."""
from hashlib import sha256
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
RECEIPT=ROOT/"docs/commercial/EMPIRE_AGENCY_COMBINED_PG041_MCP_WORDPRESS_REVOCATION_20261023.json"
RUNNER=ROOT/"scripts/agency_mcp_live_wp_e2e/run_combined_pg_wp_mcp_e2e.sh"

def read():
    return json.loads(RECEIPT.read_text())

def test_joined_pg_mcp_wordpress_mariadb_in_single_session():
    r=read()
    assert r["status"]=="COMBINED_REAL_POSTGRES_041_MCP_WORDPRESS_MARIADB_REVOCATION_PASS"
    assert r["checks_passed"]==len(r["tests"])==8
    assert all(r["tests"].values())
    assert r["native_postgresql_041"] is True
    assert r["native_wordpress_mariadb"] is True
    assert r["same_mcp_session_proved_revocation"] is True
    for name in (
        "canonical_pg_membership_authorizes_real_wp_capability",
        "canonical_pg_membership_authorizes_real_mariadb_inventory",
        "actual_041_membership_revoked_mid_mcp_session",
        "revoked_sql_member_prevented_all_wordpress_reads",
        "capabilities_still_denied_after_real_pg_revocation",
        "closed_guard_stops_access_after_revocation",
    ):
        assert r["tests"][name] is True,name

def test_no_commercial_or_production_authority_claims():
    r=read()
    assert r["production_empiredb_accessed"] is False
    assert r["real_user_revoked"] is False
    assert r["real_client_or_crm_data_accessed"] is False
    assert r["production_changes"] is False
    assert r["public_booking_payments_or_outbound"] is False
    assert r["site_grants"]=="synthetic_fixture_not_canonical_site_registry"
    assert r["issuer"]=="ephemeral_test_only_ed25519"
    assert r["secret_storage"]=="owner_only_temp_file_not_managed_vault"
    assert r["original_wordpress_app_password_revoked"] is True
    assert r["revoked_wp_auth_response"]==401
    assert r["wordpress_api_origin"]=="127.0.0.1_loopback_only"
    assert r["postgresql_transport"]=="private_unix_socket_no_tcp"
    assert r["mariadb_transport"]=="private_unix_socket_no_tcp"

def test_exact_pinned_source_and_unmodified_canonical_db_migration():
    r=read()
    assert len(r["source_sha256"])>=10
    for rel,expected in r["source_sha256"].items():
        path=ROOT/rel
        assert path.is_file(),rel
        assert sha256(path.read_bytes()).hexdigest()==expected,rel
    migration=(ROOT/"migrations/empiredb/041_crm_membership_authority.sql").read_text()
    assert "session_user = 'empire_crm_membership_login'" in migration
    assert "SET LOCAL ROLE empiredb_migrator" in migration

def test_disposable_runner_no_tcp_or_live_tenant():
    s=RUNNER.read_text()
    assert "mktemp -d /tmp/empire_agency_combined_" in s
    assert "listen_addresses=''" in s
    assert "--skip-networking" in s
    assert '"127.0.0.1:$port"' in s
    assert "crm_membership_fixture" in s
    assert "EMPIRE_AGENCY_COMBINED_PG041_MCP_WORDPRESS_REVOCATION_20261023.json" in s
    assert "trap cleanup EXIT" in s
    assert "YARD_COMBINED_ROOT" in s
    assert "sudo " not in s
    src=(ROOT/"scripts/agency_mcp_live_wp_e2e/combined_real_wp_mcp_pg.mjs").read_text()
    assert "execFileSync('/usr/bin/psql'" in src
    assert "SET status='disabled'" in src
    assert "production_empiredb:false" in src
    assert "createRevocationGuardedAgencyServer" in src
    bridge=(ROOT/"scripts/agency_mcp_live_wp_e2e/combined_authority_bridge.py").read_text()
    assert "AgencyCanonicalMembershipReader" in bridge
    assert "prepare_agency_read_session" in bridge
    assert "revalidate_agency_read_operation" in bridge
    assert "return None" in bridge
