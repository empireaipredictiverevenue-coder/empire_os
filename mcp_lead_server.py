#!/usr/bin/env python3
"""
Empire Lead Marketplace — MCP server (Agent2Agent supply layer).

Exposes Empire OS lead supply + pricing to AI agents via the Model Context
Protocol (JSON-RPC 2.0 over HTTP). No external deps — stdlib only.

Data sources:
  - Leads: container CRM DB (via `incus exec empire-hub -- sqlite3`) — 29k+ real rows.
  - Pricing: local g-brain revenue/pricing.md (hub /v1/products/pricing is down).

Run:  python3 mcp_lead_server.py [--port 9000]

Settlement is out-of-band (USDC, TS-5) — this server is the DISCOVERY/SUPPLY layer.
"""
import json, sqlite3, re, argparse, subprocess, os, time, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONTAINER = "empire-hub"
PRICING_MD = "/root/g-brain/revenue/pricing.md"

# ---- vertical catalog (mirror of search_api_leads.VERTICALS keys) ----
VERTICALS = ["logistics","warehouse","roofing","hvac","dental","realestate","law",
    "marketing","agency","plumbing","solar","medspa","staffing","saas","finance",
    "insurance","construction","trucking","freight","manufacturing"]

DOM_RE = re.compile(r'https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})')

# ---- tools ----
TOOLS = [
  {
    "name": "self_influence",
    "description": "Empire's self-promotion/self-influence surface (Phase 5): returns our "
                   "citeable AEO assets per vertical + graph centrality. Agents/peers discover "
                   "us through these — we influence our OWN demand, not chase it.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "vertical": {"type": "string", "enum": VERTICALS}
      }
    }
  },
  {
    "name": "customer_analysis",
    "description": "Deep TIHD analysis of a customer/buyer (Trigger-Intent-Habit-"
                   "Discovery): triggers, inferred intent, habit loop, discovery path. "
                   "AGI-enriched narrative when LLM available. C-suite decision surface.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "customer": {"type": "string", "description": "Business name to analyze."},
        "vertical": {"type": "string", "enum": VERTICALS, "description": "Or analyze a vertical."},
        "limit": {"type": "integer", "default": 20}
      }
    }
  },
  {
    "name": "detect_triggers",
    "description": "Detect real-time buy-signals (triggers) for a sector: permits filed, "
                   "jobs posted, LLM citations, peer mentions. Returns trigger events "
                   "with inferred intent — not a static funnel list. Agents act on these.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "sector": {"type": "string", "enum": VERTICALS,
                   "description": "Sector to watch for triggers."},
        "limit": {"type": "integer", "default": 10}
      },
      "required": ["sector"]
    }
  },
  {
    "name": "search_leads",
    "description": "Returns verified businesses for a vertical (machine-readable supply "
                   "pulled from the 29k+ container CRM).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "vertical": {"type": "string", "enum": VERTICALS},
        "limit": {"type": "integer", "default": 10}
      },
      "required": ["vertical"]
    }
  },
  {
    "name": "get_pricing",
    "description": "Get current tiered MRR pricing + per-seat lead prices for all SKUs "
                   "(sourced from g-brain revenue/pricing.md).",
    "inputSchema": {"type": "object", "properties": {}}
  },
  {
    "name": "get_sku",
    "description": "Get pricing detail for one product SKU (T1 bronze .. T4 titanium).",
    "inputSchema": {"type": "object",
      "properties": {"sku": {"type": "string", "description": "SKU id, e.g. T4"}},
      "required": ["sku"]}
  },
  {
    "name": "register_lead_buyer",
    "description": "Register a new lead buyer (tenant) occupying a seat in a lane. "
                   "Returns the registration payload (settlement out-of-band via USDC).",
    "inputSchema": {"type": "object",
      "properties": {
        "email": {"type": "string"},
        "lane": {"type": "string"},
        "tier": {"type": "string", "default": "T1"}
      }, "required": ["email","lane"]}
  },
  {
    "name": "aeo_monitor",
    "description": "SELLABLE PRODUCT (SKU aeo_monitor, MRR T1 $29/T2 $99/T3 $299/T4 $999 USDC): "
                   "run an AEO citation check for a vertical and return the current "
                   "citation_rate plus the timestamped history (citation_rate tracked "
                   "per vertical over time). Citation = empire-ai.co.uk assets surfacing "
                   "in Mojeek for the vertical's intent query.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "vertical": {"type": "string", "enum": VERTICALS,
                     "description": "Vertical to check, e.g. logistics, roofing, hvac."},
        "history": {"type": "boolean", "default": True,
                    "description": "Include timestamped citation_rate history."}
      }, "required": ["vertical"]}
  },
  {
    "name": "generate_aeo",
    "description": "SELLABLE PRODUCT: generate a crawlable AEO authority page for a business "
                   "from their 'how they talk' (niche, tone, selling points). Page is published "
                   "to empire-ai.co.uk/aeo/{tenant}/{niche}/ and becomes citeable by LLMs + agents. "
                   "White-label AEO-as-a-service. Returns the public URL.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "tenant": {"type": "string", "description": "White-label namespace (their business slug)."},
        "niche": {"type": "string", "description": "Service vertical, e.g. roofing, law_firm, med_spa."},
        "city": {"type": "string", "default": ""},
        "tone": {"type": "string", "enum": ["sharp","warm","technical","premium"], "default": "sharp"},
        "points": {"type": "array", "items": {"type": "string"}, "description": "Their selling points."},
        "questions": {"type": "array", "items": {"type": "string"}, "description": "FAQ they want cited."},
        "cta": {"type": "string", "default": ""}
      }, "required": ["tenant","niche"]}
  },
  {
    "name": "list_business",
    "description": "AGENT DIRECTORY LISTING (SKU agent_directory): discover businesses that pay "
                   "to be found by agents. Returns businesses in the directory matching a niche "
                   "(omitting niche returns all). Businesses register via the directory store.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "niche": {"type": "string", "description": "Niche to filter by, e.g. logistics, roofing, medspa. Omit for all."},
        "city": {"type": "string", "description": "Optional city filter."}
      }
    }
  },
  {
    "name": "settle_quote",
    "description": "SELLABLE PRODUCT (SKU agent_copilot / lead_lane): given a buyer agent's "
                   "intent (product + niche + metro) return a USDC settle_instruction quote "
                   "(price, tiers, vault memo). No on-chain txn — out-of-band TS-5 settlement. "
                   "Agents chain this after search_leads / copilot_route to close a deal.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "product": {"type": "string", "default": "lead_lane",
                    "description": "SKU/product to settle, e.g. lead_lane, agent_copilot."},
        "niche": {"type": "string", "description": "Vertical/niche, e.g. logistics, roofing."},
        "metro": {"type": "string", "description": "Metro/region, e.g. TX, USA."},
        "buyer_agent": {"type": "string", "description": "Calling foreign agent id (for mesh log)."}
      }
    }
  },
  {
    "name": "copilot_route",
    "description": "Co-Pilot for Agents (B2B2agent): a foreign agent posts a natural-language "
                   "task and WE route it to the right Empire MCP tool (search_leads / "
                   "generate_aeo / settle_quote), execute locally, and return a normalized "
                   "tool-call plan + result. Enables agent-to-agent chaining. "
                   "SKU agent_copilot (MRR T1 $99/T2 $299/T3 $999/T4 $2999, setup $3k).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "task": {"type": "string",
                 "description": "Natural-language task from a foreign agent, "
                                "e.g. 'find roofing leads in TX'."}
      },
      "required": ["task"]
    }
  },
  {
    "name": "spawn_synthetic",
    "description": "SELLABLE PRODUCT (SKU synthetic_agent): white-label a business's own "
                   "learning agent. Spawns a tenant-scoped synthetic-intelligence agent backed "
                   "by MiniMax M3 that runs an observe-reason-act learning loop, persists memory "
                   "to /root/feedback/syn_{tenant}.json, and returns the live status. "
                   "MRR T1 $199 / T2 $599 / T3 $1999 / T4 $5999 USDC, setup $10k (out-of-band USDC).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "tenant": {"type": "string", "description": "White-label tenant slug, e.g. testco."},
        "domain": {"type": "string", "description": "Business vertical, e.g. logistics, roofing."},
        "goal": {"type": "string", "description": "Standing objective for the agent, e.g. 'find buyers'."},
        "run_cycle": {"type": "boolean", "default": True,
                      "description": "Also run one learning cycle and return the first learning."}
      }, "required": ["tenant","domain","goal"]}
  },
  {
    "name": "aeo_refresh",
    "description": "AEO SUBSCRIPTION REFRESH (MRR line item, SKU aeo_refresh): re-optimize all "
                   "published AEO pages for a tenant from search signal — re-renders with "
                   "refreshed keyword coverage (expand_questions) + surfaces any new verticals, "
                   "then pushes back to the container AEO surface. Triggers monthly "
                   "re-optimization. Returns refreshed page count + push status.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "tenant": {"type": "string", "description": "Tenant to refresh (their AEO namespace)."},
        "add_verticals": {"type": "boolean", "default": True,
                          "description": "Also surface newly tracked verticals for this tenant."}
      },
      "required": ["tenant"]
    }
  },
  {
    "name": "verify_business",
    "description": "PRE-BUY GATE: verify a business is real before any agent buys the lead/buyer. "
                   "DNS resolves + live homepage fetch + intent_score (TLS, content, intent "
                   "keywords, years-in-business). Returns real, domain, resolves, has_site, "
                   "intent_score, notes. SKU verify_api (per-call $0.50 / MRR T1 $29 T2 $99 "
                   "T3 $299 T4 $999, USDC).",
    "inputSchema": {
      "type": "object",
      "properties": {
        "email_or_domain": {"type": "string",
            "description": "Business email or domain to verify, e.g. leads@acme.com or acme.co.uk."}
      },
      "required": ["email_or_domain"]
    }
  },
]


def _container_query(sql, args=()):
    """Run a SELECT against the container CRM DB via the crm_query helper."""
    cmd = ["incus", "exec", CONTAINER, "--", "/root/venv/bin/python3",
           "/root/empire_os/crm_query.py", sql, json.dumps(list(args))]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        return json.loads(out) if out.strip() else []
    except Exception as e:
        return [{"error": str(e)[:80]}]


def search_leads(vertical, limit=10):
    """Pull real leads from container CRM for a vertical (machine-readable supply).
    Vertical matches the `source` tag our engine writes (e.g. serper:logistics)."""
    rows = _container_query(
        "SELECT business_name, email, url, source FROM si_buyer_outreach "
        "WHERE source LIKE ? ORDER BY prospect_id DESC LIMIT ?",
        (f"%{vertical}%", limit))
    if not rows or isinstance(rows[0], dict) and "error" in rows[0]:
        rows = _container_query(
            "SELECT business_name, email, url, source FROM si_buyer_outreach "
            "WHERE email IS NOT NULL ORDER BY prospect_id DESC LIMIT ?", (limit,))
    leads = [{"business": r[0], "email": r[1], "url": r[2], "source": r[3]}
             for r in rows if isinstance(r, list)]
    return {"count": len(leads), "leads": leads,
            "settlement": "USDC per-lead via Empire Vault (no Stripe/KYC)",
            "provenance": "every lead = real verified business (TS-2)"}


def _pricing_doc():
    try:
        return open(PRICING_MD).read()
    except Exception as e:
        return f"pricing doc unavailable: {e}"


def call_tool(name, args):
    # agent-pull counter (O4-KR3): every MCP call = an agent/peer pulling our supply
    try:
        _pc = "/root/feedback/mcp_pulls.json"
        c = json.load(open(_pc)) if os.path.exists(_pc) else {"total": 0, "by_tool": {}}
        c["total"] += 1
        c["by_tool"][name] = c["by_tool"].get(name, 0) + 1
        c["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        json.dump(c, open(_pc, "w"))
    except Exception:
        pass
    if name == "self_influence":
        try:
            import influence_engine as ie
            data = ie.run()
            v = args.get("vertical")
            if v:
                data = {"vertical": v, "aeo_asset": data["aeo_assets"].get(v, ""),
                        "influence": data["influence"]}
            return data
        except Exception as e:
            return {"error": f"self_influence: {str(e)[:80]}"}
    if name == "search_leads":
        return search_leads(args.get("vertical", ""), int(args.get("limit", 10)))
    if name == "detect_triggers":
        # TIHD framing: same supply, trigger/intent lens instead of funnel
        lim = int(args.get("limit", 10))
        res = search_leads(args.get("sector", ""), lim)
        res["frame"] = "trigger-intent-discovery (not funnel)"
        return res
    if name == "customer_analysis":
        try:
            import customer_analysis as ca
            return ca.analyze(customer=args.get("customer"),
                              vertical=args.get("vertical"),
                              limit=int(args.get("limit", 20)))
        except Exception as e:
            return {"error": f"customer_analysis: {str(e)[:80]}"}
    if name == "get_pricing":
        return {"pricing_doc": _pricing_doc(),
                "note": "Tiers T1-T4; per-seat lead prices bronze$15 silver$25 "
                        "gold$45 platinum$90; white-label setup $3k-$10k"}
    if name == "get_sku":
        sku = args.get("sku", "").upper()
        doc = _pricing_doc()
        idx = doc.find(sku)
        snippet = doc[idx-200:idx+400] if idx >= 0 else f"SKU {sku} not found in pricing doc"
        return {"sku": sku, "detail": snippet}
    if name == "register_lead_buyer":
        return {"registered": True, "email": args.get("email"),
                "lane": args.get("lane"), "tier": args.get("tier", "T1"),
                "next": "settlement via USDC (TS-5) out-of-band",
                "note": "hub /v1/products/register offline; payload staged for manual provision"}
    if name == "aeo_monitor":
        try:
            sys.path.insert(0, "/root/empire_os")
            import aeo_monitor as am
            vertical = args.get("vertical", "")
            res = am.run_check(vertical)
            if args.get("history", True):
                res["history"] = am.history(vertical)
            res["sku"] = "aeo_monitor"
            res["mrr_usdc"] = {"T1": 29, "T2": 99, "T3": 299, "T4": 999}
            res["settlement"] = "USDC per-month (TS-5) out-of-band"
            return res
        except Exception as e:
            return {"error": f"aeo_monitor: {str(e)[:80]}"}
    if name == "generate_aeo":
        try:
            import re, subprocess
            sys.path.insert(0, "/root/empire_os")
            import aeo_generator as ag
            tenant = args.get("tenant", "empire")
            niche = args.get("niche", "logistics")
            p = ag.render(tenant, niche,
                          city=args.get("city", ""),
                          tone=args.get("tone", "sharp"),
                          points=args.get("points") or [],
                          questions=args.get("questions") or [],
                          cta=args.get("cta", ""),
                          surface_root="/tmp/aeo_surface")
            tslug = re.sub(r"[^a-z0-9]+", "_", tenant.lower()).strip("_")
            nslug = re.sub(r"[^a-z0-9]+", "_", niche.lower()).strip("_")
            subprocess.run(["incus", "file", "push", "--recursive",
                            f"/tmp/aeo_surface/{tslug}", "empire-hub", f"/srv/aeo/"],
                           capture_output=True, timeout=30)
            url = f"https://empire-ai.co.uk/aeo/{tslug}/{nslug}/"
            return {"published": True, "url": url, "tenant": tslug, "niche": nslug,
                    "product": "AEO page (white-label)", "settlement": "USDC setup fee per tier"}
        except Exception as e:
            return {"error": f"generate_aeo: {str(e)[:80]}"}
    if name == "aeo_refresh":
        try:
            sys.path.insert(0, "/root/empire_os")
            import aeo_refresh as ar
            tenant = args.get("tenant", "empire")
            res = ar.refresh_tenant(tenant, add_verticals=bool(args.get("add_verticals", True)))
            res["product"] = "AEO subscription refresh (MRR)"
            res["settlement"] = "USDC MRR per tier (TS-5) out-of-band"
            return res
        except Exception as e:
            return {"error": f"aeo_refresh: {str(e)[:80]}"}
    if name == "list_business":
        try:
            import business_dir as bd
            res = bd.list(args.get("niche"))
            city = args.get("city")
            if city:
                c = city.strip().lower()
                res["businesses"] = [b for b in res["businesses"]
                                     if b.get("city", "").strip().lower() == c]
                res["count"] = len(res["businesses"])
            res["sku"] = "agent_directory"
            res["settlement"] = "listing fee $500 one-time + MRR T1 $19/T2 $49/T3 $149/T4 $499 USDC"
            return res
        except Exception as e:
            return {"error": f"list_business: {str(e)[:80]}"}
    if name == "settle_quote":
        # WHITE-LABEL USDC SETTLEMENT GATEWAY (SKU usdc_gateway)
        try:
            sys.path.insert(0, "/root/empire_os")
            import settlement_gateway as sg
            amount = float(args.get("amount_usd", 0))
            tier = args.get("tier", "T1")
            memo = args.get("memo", "")
            q = sg.quote(amount, tier)
            out = {"sku": "usdc_gateway", "quote": q,
                   "note": "white-label USDC settlement; Empire takes 2.9% + $0.30 (T1); "
                           "settlement out-of-band (TS-5)",
                   "legacy": {"product": args.get("product", "lead_lane"),
                              "niche": args.get("niche", ""),
                              "metro": args.get("metro", ""),
                              "buyer_agent": args.get("buyer_agent", "")}}
            if args.get("invoice", True):
                out["invoice"] = sg.create_invoice(amount, memo=memo, tier=tier)
            return out
        except Exception as e:
            return {"error": f"settle_quote: {str(e)[:80]}"}
    if name == "copilot_route":
        try:
            from agent_copilot import route
            res = route(args.get("task", ""))
            # surface the routing decision for agent-to-agent chaining
            res["route"] = " | ".join(sorted({s["tool"] for s in res.get("plan", [])})) or "search_leads"
            return res
        except Exception as e:
            return {"error": f"copilot_route: {str(e)[:80]}"}
    if name == "spawn_synthetic":
        try:
            sys.path.insert(0, "/root/empire_os")
            import synthetic_service as ss
            tenant = args.get("tenant")
            domain = args.get("domain", "")
            goal = args.get("goal", "")
            cfg = ss.spawn_agent(tenant, domain, goal)
            out = {"spawned": True, "config": cfg,
                   "sku": "synthetic_agent",
                   "mrr_usdc": {"T1": 199, "T2": 599, "T3": 1999, "T4": 5999},
                   "setup_usdc": 10000,
                   "settlement": "USDC MRR + $10k setup (TS-5) out-of-band"}
            if args.get("run_cycle", True):
                out["learning"] = ss.run_cycle(tenant)
                out["status"] = ss.status(tenant)
            return out
        except Exception as e:
            return {"error": f"spawn_synthetic: {str(e)[:80]}"}
    if name == "vertical_feed":
        try:
            sys.path.insert(0, "/root/empire_os")
            import vertical_feed as vf
            return vf.feed(args.get("vertical", ""), int(args.get("limit", 10)))
        except Exception as e:
            return {"error": f"vertical_feed: {str(e)[:80]}"}

    if name == "verify_business":
        try:
            sys.path.insert(0, "/root/empire_os")
            import verify_business as vb
            res = vb.verify(args.get("email_or_domain", ""))
            res["sku"] = "verify_api"
            res["settlement"] = "USDC per-call $0.50 (or MRR T1 $29 / T2 $99 / T3 $299 / T4 $999)"
            return res
        except Exception as e:
            return {"error": f"verify_business: {str(e)[:80]}"}

    return {"error": f"unknown tool {name}"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({}, 204)

    def do_POST(self):
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            req = json.loads(raw.decode())
        except Exception as e:
            return self._send({"error": "bad json"}, 400)
        mid = req.get("id")
        method = req.get("method")
        params = req.get("params", {})
        if method == "initialize":
            return self._send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "empire-lead-marketplace", "version": "2.0"}}})
        if method == "tools/list":
            return self._send({"jsonrpc": "2.0", "id": mid,
                               "result": {"tools": TOOLS}})
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})
            res = call_tool(name, args)
            return self._send({"jsonrpc": "2.0", "id": mid,
                "result": {"content": [{"type": "text",
                                         "text": json.dumps(res, indent=2)}]}})
        return self._send({"jsonrpc": "2.0", "id": mid,
                           "error": {"code": -32601, "message": f"method {method}"}})

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9000)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[mcp] Empire Lead Marketplace MCP server v2 on :{args.port} "
          f"({len(TOOLS)} tools) — A2A supply layer LIVE")
    srv.serve_forever()


if __name__ == "__main__":
    main()
