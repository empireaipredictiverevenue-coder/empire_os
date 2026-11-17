"""Boundary contract for pinned NVIDIA native MCP isolated evaluation.

The MCP server is vendor-owned; these tests only guard EmpireOS's localhost
configuration and independently captured authorization/tool discovery receipt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy/systemd-user/empire-nvidia-ontology-mcp-eval.service"
PROBE = ROOT / "scripts/probe_nvidia_mcp_existing_20261117.py"
RECEIPT = ROOT / "runtime/nvidia_ontology_eval/nvidia_mcp_live_auth_boundary_20261117.json"
EXPECTED = {
    "ask_question", "check_answerable", "check_readiness",
    "describe_table", "get_sql_attribute", "get_term",
    "get_term_columns", "get_term_sql_attributes", "search_terms",
}


def test_native_mcp_is_loopback_and_no_shared_admin_identity():
    cfg = UNIT.read_text()
    assert "nvidia_mcp_verified_issuer_20261117.py" in cfg
    assert "AUTO_ONTOLOGY_API_URL=http://localhost:33000" in cfg
    assert "AUTO_ONTOLOGY_MCP_HOST=127.0.0.1" in cfg
    assert "AUTO_ONTOLOGY_MCP_PORT=33013" in cfg
    assert "AUTO_ONTOLOGY_MCP_PUBLIC_URL=http://127.0.0.1:33013" in cfg
    assert "NoNewPrivileges=yes" in cfg
    assert "ProtectSystem=strict" in cfg
    assert "ProtectHome=read-only" in cfg
    assert "Restart=on-failure" in cfg
    assert "MemoryMax=" in cfg
    assert "CPUQuota=" in cfg
    assert "AUTO_ONTOLOGY_ADMIN_PASSWORD" not in cfg
    assert "OPENROUTER_API_KEY" not in cfg
    assert "EMPIRE_OPS_MCP_BEARER_TOKEN" not in cfg
    assert "AUTO_ONTOLOGY_MCP_HOST=0.0.0.0" not in cfg
    assert "User=root" not in cfg
    assert "docker" not in cfg.lower()


def test_probe_never_promotes_auth_without_oauth_user_login():
    text = PROBE.read_text()
    assert '"live_authenticated_agent_call_verified": False' in text
    assert '"tenant_isolation_verified": False' in text
    assert "Bearer invalid-opaque-evaluation-token" in text
    assert "X-API-Key" in text
    assert "get_term" in text
    assert "ask_question" in text
    assert "os.O_EXCL" in text


def test_live_mcp_boundary_receipt():
    if not RECEIPT.is_file():
        pytest.skip("only on EmpireOS after live native MCP security verification")
    assert RECEIPT.stat().st_mode & 0o077 == 0
    data = json.loads(RECEIPT.read_text())
    assert data["status"] == "MCP_AUTH_BOUNDARY_AND_TOOL_DISCOVERY_PASS"
    assert data["mcp_url"] == "http://127.0.0.1:33013/mcp"
    assert data["application_api"] == "http://localhost:33000"
    assert data["synthetic_only"] is True
    assert data["admin_credentials_forwarded"] is False
    assert data["tokens_minted_or_saved"] is False
    assert data["oauth_resource_metadata_http"] == 200
    assert data["oauth_resource_id_exact"] is True
    assert data["oauth_issuer_discovered"] is True
    assert data["oauth_registration_supported"] is True
    assert data["openid_advertised"] is True
    for key in (
        "anonymous_http", "invalid_bearer_http",
        "wrong_api_key_http", "userinfo_invalid_bearer_http",
    ):
        assert data[key] == 401
    assert data["advertised_tool_count"] == 9
    assert set(data["advertised_tools"]) == EXPECTED
    assert data["curated_tools_exact"] is True
    assert data["tools_have_descriptions"] is True
    assert data["live_authenticated_agent_call_verified"] is False
    assert data["tenant_isolation_verified"] is False
