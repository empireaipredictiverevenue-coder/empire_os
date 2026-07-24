#!/usr/bin/env python3
"""pinecone_mcp_client.py — query Pinecone docs via MCP (no API key needed).

Uses npx -y @pinecone-database/mcp via JSON-RPC over stdio.

Usage:
  from pinecone_mcp_client import PineconeMCPClient
  client = PineconeMCPClient()
  result = client.search_docs("how do I create an index?")
  print(result)
"""
import json
import subprocess
from typing import Any, Optional


class PineconeMCPClient:
    """Minimal MCP client for Pinecone. Spawns npx mcp server, queries via stdio JSON-RPC."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.proc = None

    def _start(self):
        env = {}
        if self.api_key:
            env["PINECONE_API_KEY"] = self.api_key
        self.proc = subprocess.Popen(
            ["npx", "-y", "@pinecone-database/mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**__import__("os").environ, **env},
            text=True,
        )

    def _send(self, method: str, params: dict = None) -> dict:
        msg = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        return json.loads(line)

    def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools."""
        self._start()
        try:
            resp = self._send("tools/list")
            return resp.get("result", {}).get("tools", [])
        finally:
            if self.proc:
                self.proc.terminate()

    def search_docs(self, query: str) -> str:
        """Search Pinecone documentation."""
        self._start()
        try:
            resp = self._send("tools/call", {"name": "search_pinecone_docs", "arguments": {"query": query}})
            return json.dumps(resp.get("result", {}), indent=2)
        finally:
            if self.proc:
                self.proc.terminate()

    def close(self):
        if self.proc:
            self.proc.terminate()


if __name__ == "__main__":
    import sys
    client = PineconeMCPClient()
    print("=== Tools available without API key ===")
    try:
        tools = client.list_tools()
        for t in tools[:10]:
            print(f"  - {t.get('name', '?')}: {t.get('description', '')[:80]}")
    except Exception as e:
        print(f"Error: {e}")
