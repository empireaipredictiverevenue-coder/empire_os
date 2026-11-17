"""Existing OpenCode V2 / NVIDIA native MCP identity-bound integration checks."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
VERIFY=ROOT/"scripts/verify_nvidia_opencode_viewer_gate_20261117.py"
LOGIN=ROOT/"scripts/authorize_existing_nvidia_mcp_viewer_20261117.sh"
RECEIPT=ROOT/"runtime/nvidia_ontology_eval/nvidia_opencode_viewer_gate_20261117_v2.json"
PERSISTENT=Path("/home/ubuntu/.config/empire-opencode-v2/opencode/opencode.json")
BACKUP=PERSISTENT.with_name("opencode.pre-oauth-metadata-20261117.json")
ACTIVE=Path("/tmp/empire_opencode_v2_free_20261113/config/opencode/opencode.json")
EXPECTED={"type":"remote","url":"http://127.0.0.1:33013/mcp",
          "oauth":{"auth_server_metadata_url":"http://localhost:33000/api/auth/.well-known/oauth-authorization-server"}}


def test_login_helper_reuses_existing_viewer_oauth_without_bootstrap_admin():
    script=LOGIN.read_text()
    assert "mcp auth nvidia-auto-ontology" in script
    assert "opencode.exe" in script
    assert "OPEN_CODE_V2" in script or "OpenCode V2" in script
    assert "AUTO_ONTOLOGY_ADMIN_PASSWORD" in script
    assert "unset AUTO_ONTOLOGY_ADMIN_PASSWORD" in script
    assert "OPENROUTER_API_KEY" not in script
    assert "docker" not in script.lower()
    assert "sudo " not in script
    assert "systemctl restart" not in script
    assert "api/auth/sign-in/email" not in script
    assert "mcp logout" not in script


def test_live_identity_boundary_receipt_is_fail_closed():
    if not RECEIPT.exists():
        pytest.skip("live OpenCode V2 acceptance on EmpireOS only")
    assert RECEIPT.stat().st_mode & 0o077 == 0
    evidence=json.loads(RECEIPT.read_text())
    assert evidence["status"]=="OPENCODE_V2_MCP_BOUND_VIEWER_OAUTH_REQUIRED"
    assert evidence["mcp_endpoint"]==EXPECTED["url"]
    assert evidence["open_code_cli_listing_pass"] is True
    assert evidence["active_workspace_mcp_name_present_via_cli"] is True
    assert evidence["viewer_oauth_status"]=="needs_authentication"
    assert evidence["unauthenticated_vendor_mcp_http"]==401
    assert evidence["vendor_oauth_metadata_http"]==200
    assert evidence["nvidia_issuer_matched"] is True
    assert evidence["browser_oauth_stage_reached_without_schema_errors"] is True
    assert evidence["app_health"]=="ok"
    assert evidence["authenticated_viewer_tool_invocation"] is False
    assert evidence["tenant_isolation_verified"] is False
    assert evidence["restart_performed"] is False
    assert evidence["credential_or_token_disclosed"] is False


def test_existing_opencode_configuration_is_additive_and_concurrent_changes_preserved():
    if not all(p.is_file() for p in (PERSISTENT,BACKUP,ACTIVE)):
        pytest.skip("existing OpenCode V2 configuration not mounted")
    current=json.loads(PERSISTENT.read_text())
    original=json.loads(BACKUP.read_text())
    running=json.loads(ACTIVE.read_text())
    assert current["mcp"]=={"servers":{"nvidia-auto-ontology":EXPECTED}}
    assert running["mcp"]=={"servers":{"nvidia-auto-ontology":EXPECTED}}
    assert set(running)=={"$schema","mcp"}
    assert all(current.get(k)==v for k,v in original.items() if k!="mcp")
    for p in (PERSISTENT,BACKUP,ACTIVE):
        assert p.stat().st_mode & 0o077 == 0
