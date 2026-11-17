"""Read-only live native MCP and OAuth boundary probe for isolated NVIDIA.

Runs with NVIDIA's own isolated MCP virtualenv. Does NOT mint, exchange, log
or store access tokens. Proves protected HTTP boundary and curated tool
descriptions, NOT a signed-in agent session or tenant authorization.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from fastmcp import Client

from auto_ontology_mcp.config import Settings, DEFAULT_SPEC_PATH
from auto_ontology_mcp.server import build_server
from auto_ontology_mcp.tools import CURATED

BASE = "http://127.0.0.1:33013"
MCP = BASE + "/mcp"
RESOURCE = BASE + "/.well-known/oauth-protected-resource/mcp"
APP = "http://localhost:33000"
RECEIPT = Path("/srv/empire_os/runtime/nvidia_ontology_eval/nvidia_mcp_live_auth_boundary_20261117.json")
PRIVATE_SOURCE = Path("/srv/empire_os/runtime/nvidia_ontology_eval/.env")
EXPECTED_TOOLS = {
    "search_terms", "get_term", "get_term_columns", "get_term_sql_attributes",
    "get_sql_attribute", "describe_table", "check_answerable",
    "ask_question", "check_readiness",
}


async def inspect() -> dict:
    if RECEIPT.exists():
        raise RuntimeError("existing private receipt must not be overwritten")
    if PRIVATE_SOURCE.stat().st_mode & 0o077:
        raise RuntimeError("synthetic application credentials not private")
    env = dict(row.split("=", 1) for row in PRIVATE_SOURCE.read_text().splitlines() if "=" in row)
    if env.get("CONNECTION_STRINGS") != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("not the isolated synthetic application")
    result = {
        "status": "NOT_VERIFIED",
        "source": "NVIDIA_PINNED_NATIVE_MCP_1_2_0",
        "mcp_url": MCP,
        "application_api": APP,
        "synthetic_only": True,
        "tokens_minted_or_saved": False,
        "admin_credentials_forwarded": False,
    }
    async with httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as http:
        unauthorized = await http.get(MCP)
        wrong_bearer = await http.get(
            MCP, headers={"Authorization": "Bearer invalid-opaque-evaluation-token"}
        )
        wrong_key = await http.get(
            MCP, headers={"X-API-Key": "invalid-key-not-a-credential"}
        )
        metadata_response = await http.get(RESOURCE)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        discovery = await http.get(APP + "/.well-known/oauth-authorization-server")
        discovery.raise_for_status()
        auth_data = discovery.json()
        user_info_invalid = await http.get(
            APP + "/api/auth/oauth2/userinfo",
            headers={"Authorization": "Bearer invalid-opaque-evaluation-token"},
        )

    result.update({
        "anonymous_http": unauthorized.status_code,
        "invalid_bearer_http": wrong_bearer.status_code,
        "wrong_api_key_http": wrong_key.status_code,
        "userinfo_invalid_bearer_http": user_info_invalid.status_code,
        "oauth_resource_metadata_http": metadata_response.status_code,
        "oauth_resource_id_exact": metadata.get("resource") == MCP,
        "oauth_issuer_discovered": (
            APP + "/" in (metadata.get("authorization_servers") or [])
        ),
        "oauth_registration_supported": bool(auth_data.get("registration_endpoint")),
        "openid_advertised": "openid" in (auth_data.get("scopes_supported") or []),
    })
    spec = Settings(
        api_url=APP,
        spec_path=DEFAULT_SPEC_PATH,
        host="127.0.0.1",
        port=33013,
        timeout_s=20,
        chat_timeout_s=180,
        public_url=BASE,
    )
    server, underlying_client = build_server(spec)
    try:
        async with Client(server) as session:
            tools = await session.list_tools()
    finally:
        await underlying_client.aclose()
    names = {t.name for t in tools}
    result.update({
        "advertised_tool_count": len(names),
        "curated_tools_exact": names == EXPECTED_TOOLS == (
            {item.name for item in CURATED} | {"ask_question", "check_readiness"}
        ),
        "advertised_tools": sorted(names),
        "tools_have_descriptions": all(bool(t.description and t.description.strip()) for t in tools),
        "live_authenticated_agent_call_verified": False,
        "tenant_isolation_verified": False,
    })
    passed = (
        unauthorized.status_code == 401
        and wrong_bearer.status_code == 401
        and wrong_key.status_code == 401
        and user_info_invalid.status_code == 401
        and metadata_response.status_code == 200
        and result["oauth_resource_id_exact"]
        and result["oauth_issuer_discovered"]
        and result["oauth_registration_supported"]
        and result["openid_advertised"]
        and result["advertised_tool_count"] == 9
        and result["curated_tools_exact"]
        and result["tools_have_descriptions"]
    )
    result["status"] = "MCP_AUTH_BOUNDARY_AND_TOOL_DISCOVERY_PASS" if passed else "MCP_SECURITY_BOUNDARY_FAILED"
    fd = os.open(RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, sort_keys=True)
    return result


if __name__ == "__main__":
    findings = asyncio.run(inspect())
    print(json.dumps(findings, indent=2, sort_keys=True))
    if findings["status"] != "MCP_AUTH_BOUNDARY_AND_TOOL_DISCOVERY_PASS":
        raise SystemExit(1)
