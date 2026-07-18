#!/usr/bin/env python3
"""
Co-Pilot for Agents (B2B2agent) — routing + settlement layer.

A foreign (customer) agent posts a natural-language task, e.g.
    "find roofing leads in TX"
    "generate an AEO page for acme logistics"
    "quote a USDC settle for 50 logistics leads in USA"

`route(task)` maps it to the right Empire MCP tool (search_leads /
generate_aeo / settle_quote), executes it via a local MCP client call to
127.0.0.1:9000, and returns a normalized result:

    {
      "task": <str>,
      "plan": [{"tool": <name>, "arguments": {...}}],   # structured tool-call plan
      "tool": <name>,                                   # tool actually executed
      "arguments": {...},
      "result": <normalized mcp result>,                # real result from live MCP
      "status": "ok" | "error",
      "sku": "agent_copilot",
      "settlement": "MRR T1 $99/T2 $299/T3 $999/T4 $2999 USDC (setup $3k)"
    }

Stdlib only. No creds. The loopback MCP call exercises the LIVE server the
same way a remote agent would, so chains compose (an agent can call
copilot_route, then settle_quote on the result).

SKU agent_copilot pricing (g-brain/revenue/pricing.md):
  MRR  T1 $99 / T2 $299 / T3 $999 / T4 $2999
  setup $3,000  (USDC, TS-5 out-of-band)
"""

import json
import urllib.request
from http.server import BaseHTTPRequestHandler  # noqa: F401  (kept stdlib, no dep)

MCP_HOST = "127.0.0.1"
MCP_PORT = 9000
SKU = "agent_copilot"
SETTLEMENT = "MRR T1 $99/T2 $299/T3 $999/T4 $2999 USDC (setup $3k)"
TIERS = {"T1": 99, "T2": 299, "T3": 999, "T4": 2999}

# Vertical vocabulary (mirror of mcp_lead_server.VERTICALS) for intent mapping.
VERTICALS = ["logistics", "warehouse", "roofing", "hvac", "dental", "realestate",
             "law", "marketing", "agency", "plumbing", "solar", "medspa",
             "staffing", "saas", "finance", "insurance", "construction",
             "trucking", "freight", "manufacturing"]

_CITIES = ["TX", "USA", "US", "UK", "CA", "NY", "CA", "FL", "CANADA", "USA"]


# --------------------------------------------------------------------------
# MCP client (loopback) — same JSON-RPC 2.0 surface a remote agent uses.
# --------------------------------------------------------------------------
def _mcp_call(method, params=None, _id=1):
    """Call the local MCP server over JSON-RPC 2.0 and return the parsed result."""
    payload = json.dumps({"jsonrpc": "2.0", "id": _id,
                          "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(
        f"http://{MCP_HOST}:{MCP_PORT}",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode())
    except Exception as e:
        return {"error": f"mcp_call {method}: {str(e)[:120]}"}
    if "error" in body:
        return {"error": body["error"].get("message", "mcp error")}
    return body.get("result")


def _mcp_tool(name, arguments):
    """Invoke tools/call on the live MCP server."""
    return _mcp_call("tools/call",
                     {"name": name, "arguments": arguments})


# --------------------------------------------------------------------------
# Intent parsing — NL task -> (tool, arguments)
# --------------------------------------------------------------------------
def _detect_vertical(task):
    t = task.lower()
    for v in VERTICALS:
        if v in t:
            return v
    # light aliases
    alias = {"roofer": "roofing", "roofers": "roofing", "lawyer": "law",
             "attorney": "law", "dentist": "dental", "hvac": "hvac",
             "trucker": "trucking", "freight": "freight", "solar": "solar"}
    for k, v in alias.items():
        if k in t:
            return v
    return ""


def _detect_metro(task):
    t = task.upper()
    for c in ["TX", "USA", "US", "UK", "CANADA", "NY", "FL", "CA", "IL", "GA"]:
        if c in t.split():
            return c
    # also catch "in USA" style substrings
    for c in ["USA", "UK", "CANADA"]:
        if c in t:
            return c
    return ""


def _plan(task):
    """Map a natural-language task to a structured MCP tool-call plan."""
    t = task.lower()
    vertical = _detect_vertical(task)
    metro = _detect_metro(task)

    if "aeo" in t or "authority page" in t or "generate" in t and "page" in t:
        # generate_aeo needs tenant + niche at minimum
        slug = vertical or "logistics"
        return [{
            "tool": "generate_aeo",
            "arguments": {"tenant": slug, "niche": slug,
                          "city": metro, "tone": "sharp"}
        }]
    if "settle" in t or "quote" in t or "usdc" in t:
        return [{
            "tool": "settle_quote",
            "arguments": {"product": "lead_lane", "niche": vertical,
                          "metro": metro, "buyer_agent": "foreign_agent"}
        }]
    # default: lead discovery
    return [{
        "tool": "search_leads",
        "arguments": {"vertical": vertical or "logistics", "limit": 10}
    }]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def route(task):
    """Route a foreign agent's natural-language task to the right MCP tool,
    execute it on the live local MCP, and return a normalized result."""
    if not task or not task.strip():
        return {"task": task, "plan": [], "tool": None, "arguments": {},
                "result": {"error": "empty task"}, "status": "error",
                "sku": SKU, "settlement": SETTLEMENT}

    plan = _plan(task)
    step = plan[0]
    tool, arguments = step["tool"], step["arguments"]

    raw = _mcp_tool(tool, arguments)
    # MCP wraps tool output in {"content":[{"type":"text","text":...}]}
    result = raw
    if isinstance(raw, dict) and "content" in raw:
        try:
            result = json.loads(raw["content"][0]["text"])
        except Exception:
            result = raw

    status = "ok" if not (isinstance(result, dict) and "error" in result) else "error"
    return {
        "task": task,
        "plan": plan,
        "tool": tool,
        "arguments": arguments,
        "result": result,
        "status": status,
        "sku": SKU,
        "settlement": SETTLEMENT,
    }


def quote_settle(product="lead_lane", niche="", metro="", buyer_agent=""):
    """Standalone settlement-quote surface (mirrors MCP settle_quote tool).
    Returns a USDC settle_instruction quote. No on-chain tx — TS-5 out-of-band."""
    price = TIERS.get("T1", 99)
    return {
        "sku": SKU,
        "product": product,
        "niche": niche,
        "metro": metro,
        "buyer_agent": buyer_agent,
        "quote_usdc": {
            "t1": TIERS["T1"], "t2": TIERS["T2"],
            "t3": TIERS["T3"], "t4": TIERS["T4"],
        },
        "setup_fee_usdc": 3000,
        "token": "USDC",
        "settle_instruction": {
            "token": "USDC",
            "amount_usdc": price,
            "to": "Empire Vault (TS-5 listener)",
            "memo": f"SKU_{SKU.upper()}_{product.upper()}",
        },
        "settlement": "out-of-band USDC (TS-5) — no on-chain txn here",
        "note": "chain after search_leads / copilot_route to close a deal",
    }


if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "find logistics leads USA"
    print(json.dumps(route(task), indent=2))
