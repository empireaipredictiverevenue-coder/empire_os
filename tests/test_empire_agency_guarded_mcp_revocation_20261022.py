"""New authentic WordPress/MariaDB guarded MCP receipt; never confuse fixture authority with live EmpireDB."""
import json
from pathlib import Path
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
MCP=ROOT/"prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio"
REC=ROOT/"docs/commercial/EMPIRE_AGENCY_GUARDED_MCP_WORDPRESS_REVOCATION_20261022.json"

def test_authentic_wordpress_backend_and_synthetic_revocation_truth():
    r=json.loads(REC.read_text())
    assert r["status"]=="REAL_WORDPRESS_MYSQL_GUARDED_MCP_SYNTHETIC_REVOCATION_PASS"
    assert r["native_mariadb_database"] is True
    assert r["native_wordpress_plugin_enabled"] is True
    assert r["loopback_http_only"] is True
    assert r["credential_revoked_after_test"] is True
    assert r["post_revocation_http_status"]==401
    assert r["membership_source"]=="synthetic_mutable_stage_fixture_not_canonical_empiredb"
    assert r["mcp_checks_passed"]==len(r["mcp_checks"])==9
    assert all(r["mcp_checks"].values())
    assert all(r["mcp_checks"][key] for key in [
        "mid_session_membership_revoked_denied_before_wordpress",
        "mid_session_site_grant_revoked_denied_before_wordpress",
        "mid_session_registry_revoked_denied_before_wordpress",
        "mid_session_credential_revoked_denied_before_wordpress",
        "closed_session_denied_before_wordpress",
        "authenticated_synthetic_inventory_real_mariadb"])
    assert r["production_changes"] is False
    assert r["crm_payments_outbound_activated"] is False
    assert r["secret_values_in_receipt"] is False

def test_exact_source_hashes_immutable_receipt():
    r=json.loads(REC.read_text())
    for rel,digest in r["source_sha256"].items():
        assert sha256((ROOT/rel).read_bytes()).hexdigest()==digest, rel

def test_guarded_wrapper_checks_each_tool_not_just_startup():
    guarded=(MCP/"revocation-guard.mjs").read_text()
    assert guarded.count("await verify(")==2
    assert "await freshAuthorizeRead(operation)" in guarded
    assert "createAgencyServer({" in guarded
    assert "require(" not in guarded
    assert "registerTool(" not in guarded
    assert "client_secret" not in guarded
    src=(ROOT/"scripts/agency_mcp_live_wp_e2e/guarded_real_wp.mjs").read_text()
    assert "InMemoryTransport" in src
    assert "synthetic_member_and_site_state:true" in src
    assert "canonical_empiredb_membership_queried:false" in src
    assert "memberActive=false" in src
    assert "siteActive=false" in src
    assert "registryActive=false" in src
    assert "credentialActive=false" in src

def test_authority_is_separate_from_historically_pinned_mcp_adapter():
    existing=(MCP/"server.mjs").read_bytes()
    pinned=json.loads((ROOT/"docs/commercial/EMPIRE_AGENCY_REST_MCP_STAGING_RUNTIME_20261022.json").read_text())
    key="prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/server.mjs"
    assert sha256(existing).hexdigest()==pinned["source_sha256"][key]

def test_docs_honestly_retain_owner_dependency():
    handoff=(ROOT/"docs/commercial/EMPIRE_AGENCY_GUARDED_MCP_REVOCATION_HANDOFF_20261022.md").read_text()
    assert "No live EmpireDB tenant membership was queried or revoked" in handoff
    assert "synthetic mutable authority state" in handoff
    assert "not a provisioned production vault" in handoff.lower()
