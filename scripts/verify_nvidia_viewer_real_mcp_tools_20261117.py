"""NVIDIA native MCP read-only viewer acceptance via EXISTING approved OpenCode OAuth.

The OpenCode service owns and stores its OAuth grant. This bounded test reads
that pre-existing grant locally, never prints/transmits it elsewhere, and
sends it only to the existing localhost NVIDIA authorization/MCP endpoints.
Only synthetic data. No OAuth renewal, admin session, new identity or writes.
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
SQLITE = Path("/tmp/empire_opencode_v2_free_20261113/data/opencode/opencode.db")
OUT = ROOT / "nvidia_viewer_real_mcp_tools_20261117.json"
TARGET = "http://127.0.0.1:33013/mcp"
ISSUER = "http://localhost:33000/api/auth"
EXPECTED = {
    "check_readiness", "search_terms", "get_term", "get_term_columns",
    "get_term_sql_attributes", "get_sql_attribute", "describe_table",
    "check_answerable", "ask_question",
}

def load_existing_grant() -> str:
    config = dict(line.split("=", 1) for line in (ROOT/".env").read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    if config.get("CONNECTION_STRINGS") != "sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("synthetic source identity changed")
    with sqlite3.connect("file:" + str(SQLITE) + "?mode=ro", uri=True) as db:
        matches = db.execute(
            "SELECT value FROM credential WHERE label=? AND active=1",
            ("nvidia-auto-ontology",),
        ).fetchall()
    if len(matches) != 1:
        raise RuntimeError("one existing active OpenCode viewer grant required")
    cred = json.loads(matches[0][0])
    metadata = cred.get("metadata") or {}
    if (metadata.get("serverUrl") != TARGET or
        str(metadata.get("issuer", "")).rstrip("/") != ISSUER or
        not isinstance(cred.get("access"), str) or not cred["access"]):
        raise RuntimeError("OpenCode OAuth grant identity does not match NVIDIA")
    return cred["access"]

def content_summary(result):
    structured = getattr(result, "structuredContent", None)
    parts = getattr(result, "content", [])
    payloads = [item.text for item in parts if getattr(item, "type", "") == "text"]
    return {
        "mcp_is_error": bool(result.isError),
        "content_parts": len(parts),
        "structured_present": structured is not None,
        "text_nonempty": any(bool(x.strip()) for x in payloads),
        "text_lengths": [len(x) for x in payloads[:4]],
        "response_json_type": (
            type(structured).__name__ if structured is not None else None
        ),
    }

async def main():
    if OUT.exists():
        raise RuntimeError("immutable private acceptance receipt already exists")
    token = load_existing_grant()
    report = {
        "source": "EXISTING_OPENCODE_V2_AUTHORIZED_VIEWER_GRANT",
        "synthetic_only": True,
        "reused_identity": True,
        "token_disclosed": False,
        "new_credentials_created": False,
        "read_only": True,
        "production_data_sent": False,
    }
    async with httpx.AsyncClient(timeout=12, trust_env=False, follow_redirects=False) as http:
        r = await http.get(ISSUER + "/oauth2/userinfo", headers={"Authorization":"Bearer "+token})
        report["oauth_userinfo_http"] = r.status_code
        if r.status_code != 200:
            raise RuntimeError("existing viewer grant not accepted at userinfo")
        user = r.json()
        report["userinfo_has_subject"] = isinstance(user, dict) and bool(user.get("sub"))
        # Admin routes must not return any rows for this viewer bearer.
        admin = {}
        for label, path in (
            ("invitations", "/api/invitations"),
            ("user_admin", "/api/auth/admin/list-users?limit=1"),
        ):
            r = await http.get("http://localhost:33000" + path,
                headers={"Authorization":"Bearer "+token})
            admin[label] = {"http":r.status_code, "denied":r.status_code in (401,403)}
        report["admin_denials"] = admin
    async with streamablehttp_client(
        TARGET, headers={"Authorization": "Bearer " + token},
        timeout=30, sse_read_timeout=120
    ) as (reader, writer, _):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = (await client.list_tools()).tools
            names = {t.name for t in tools}
            report["tool_count"] = len(tools)
            report["curated_tool_set_exact"] = names == EXPECTED
            report["tool_input_shapes"] = {
                t.name: {
                    "required": list(t.inputSchema.get("required", [])),
                    "properties": sorted(t.inputSchema.get("properties", {}))
                } for t in tools if t.name in {"check_readiness","search_terms","ask_question"}
            }
            readiness = await client.call_tool("check_readiness", {})
            report["check_readiness"] = content_summary(readiness)
            # search_terms is a harmless semantic-glossary read.
            schema = next(t.inputSchema for t in tools if t.name=="search_terms")
            required = schema.get("required", [])
            args = {}
            for field in required:
                definition = schema.get("properties", {}).get(field, {})
                if definition.get("type") == "string":
                    args[field] = "buyer"
                else:
                    raise RuntimeError("search_terms has unfamiliar mandatory input: " + field)
            lookup = await client.call_tool("search_terms", args)
            report["search_terms"] = content_summary(lookup)
    report["viewer_readonly_mcp_acceptance"] = (
        report["oauth_userinfo_http"] == 200
        and report["userinfo_has_subject"]
        and all(d["denied"] for d in report["admin_denials"].values())
        and report["curated_tool_set_exact"]
        and not report["check_readiness"]["mcp_is_error"]
        and not report["search_terms"]["mcp_is_error"]
    )
    report["ask_question_not_yet_executed"] = True
    fd = os.open(OUT, os.O_EXCL|os.O_CREAT|os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as f: json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    if not report["viewer_readonly_mcp_acceptance"]:
        raise SystemExit(2)

if __name__ == "__main__":
    asyncio.run(main())
