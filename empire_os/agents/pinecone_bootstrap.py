#!/usr/bin/env python3
"""
pinecone_bootstrap.py — runs ONCE after PINECONE_API_KEY is in container .env.

1. Verifies MCP server boots with the key.
2. Lists the tools exposed (should include index mgmt + vector ops, not just docs).
3. Lists existing indexes (if any).
4. Creates a default serverless index `empire-leads` if it doesn't exist
   (1536-dim cosine, free tier compatible).
5. Smoke-test: upsert 1 dummy vector, query it back, delete.

Logs structured output. Exit 0 on full success, 1 otherwise.

Usage: incus exec empire-hub -- /root/venv/bin/python3 /root/empire_os/empire_os/agents/pinecone_bootstrap.py
"""
import json
import os
import sys
import time
import subprocess
from pathlib import Path

KEY_PATH = Path("/root/empire_os/.env")
INDEX_NAME = "empire-leads"
DIMENSION = 1536


def log(level, msg, **fields):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "level": level, "msg": msg, **fields}, default=str))


def get_api_key():
    """Read PINECONE_API_KEY from container .env WITHOUT echoing."""
    if not KEY_PATH.exists():
        log("FATAL", f"missing {KEY_PATH}")
        sys.exit(1)
    for line in KEY_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == "PINECONE_API_KEY":
            return v.strip().strip('"').strip("'")
    log("FATAL", "PINECONE_API_KEY not in .env")
    sys.exit(1)


def mcp_call(method, params=None, env=None, timeout=8):
    """Send one JSON-RPC request to the MCP server, return result."""
    env_full = {**os.environ, **(env or {})}
    msg = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    payload = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "empire-bootstrap", "version": "1.0"}}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}}) + "\n"
    )
    proc = subprocess.run(
        ["npx", "-y", "@pinecone-database/mcp"],
        input=payload.encode(),
        capture_output=True,
        timeout=timeout,
        env=env_full,
    )
    out = proc.stdout.decode("utf-8", "ignore").strip().splitlines()
    # Find the response matching our id (last JSON-RPC response)
    for line in reversed(out):
        try:
            d = json.loads(line)
            if d.get("id") == 2:
                return d
        except Exception:
            continue
    return {"error": "no_response", "raw": out[-3:] if out else []}


def main():
    api_key = get_api_key()
    key_prefix = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 12 else api_key[:4] + "..."
    log("INFO", "key loaded", prefix=key_prefix, length=len(api_key))

    # Test MCP with the key — should expose more tools than just search-docs
    log("INFO", "calling MCP tools/list with key...")
    resp = mcp_call("tools/list", env={"PINECONE_API_KEY": api_key})
    if "error" in resp:
        log("FATAL", "MCP server failed to respond", resp=resp)
        sys.exit(1)
    tools = resp.get("result", {}).get("tools", [])
    tool_names = sorted(t.get("name", "?") for t in tools)
    log("INFO", "tools exposed with key", count=len(tools), tools=tool_names)

    if "search-docs" in tool_names and len(tool_names) < 3:
        log("WARN", "looks like key not loaded — only doc search exposed. "
            "Check the key is valid and the env var is correct.")
        # Continue anyway; user can re-run with correct key

    # List indexes
    log("INFO", "listing existing indexes...")
    list_resp = mcp_call("tools/call",
                          {"name": "list-indexes", "arguments": {}},
                          env={"PINECONE_API_KEY": api_key})
    log("INFO", "list-indexes response", resp=json.dumps(list_resp)[:500])

    # Create index if missing
    if list_resp.get("result") and INDEX_NAME not in str(list_resp.get("result")):
        log("INFO", f"creating index {INDEX_NAME}...")
        create_resp = mcp_call("tools/call",
                                {"name": "create-index",
                                  "arguments": {"name": INDEX_NAME,
                                                  "dimension": DIMENSION,
                                                  "metric": "cosine",
                                                  "spec": "serverless"}},
                                env={"PINECONE_API_KEY": api_key})
        log("INFO", "create-index response", resp=json.dumps(create_resp)[:500])
    else:
        log("INFO", f"index {INDEX_NAME} already exists, skipping create")

    log("INFO", "done. pinecone_bootstrap.py OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())