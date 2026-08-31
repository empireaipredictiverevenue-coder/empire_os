#!/usr/bin/env python3
"""a2a_card_server — standalone Agent2Agent discovery + product surface.

Runs as its own service (port 8086) so it is independent of the hub's
import/respawn quirks. Serves:
  GET  /.well-known/agent.json   Google A2A AgentCard (discovery)
  GET  /v1/a2a/agent-card        (same, friendly path)
  POST /v1/a2a/peer/register     register a remote agent's card (inbound A2A)
  GET  /v1/a2a/peers             list known peers
  GET  /v1/a2a/catalog           machine-readable product catalog
  GET  /p/{sku}                  branded A2A product page (CTA -> /v1/pay/{memo})
  GET  /                          status
"""
import os, sqlite3, json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
VAULT = os.environ.get("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
PUB = os.environ.get("EMPIRE_PUBLIC_URL", "http://216.128.149.56:8086")

app = FastAPI(title="Empire OS A2A Discovery")

# ── product catalog (mirrors hub PRODUCT_CATALOG) ──────────────────────────
PRODUCTS = {
    "lead_lane":      {"name": "Lead Lane",      "price": 49.0,  "cat": "lead-gen",   "desc": "AI-built lead lane that fills itself with verified buyers."},
    "ai_closer":      {"name": "AI Closer",      "price": 149.0, "cat": "sales",      "desc": "Autonomous closer that sends the pay link and releases the seat when funded."},
    "inbound_reply":  {"name": "Inbound Reply",  "price": 79.0,  "cat": "engagement",  "desc": "Replies to every inbound lead and books the call."},
    "seat_corridor":  {"name": "Seat Corridor",  "price": 99.0,  "cat": "saas",       "desc": "Multi-tenant seat provisioning + billing corridor."},
    "predictive_rev": {"name": "Predictive Rev", "price": 199.0, "cat": "intelligence","desc": "Omega-scored revenue prediction across every lane."},
    "aeo_surface":    {"name": "AEO Surface",    "price": 129.0, "cat": "seo",        "desc": "Answer-engine optimized pages that rank and convert."},
    "satellite_dma":  {"name": "Satellite DMA",  "price": 89.0,  "cat": "scoring",    "desc": "Storm/satellite damage scoring for high-intent claims."},
    "mass_tort":      {"name": "Mass Tort",      "price": 249.0, "cat": "legal",      "desc": "Mass-tort lead engine with compliant intake."},
}

# ── tracking: clicks + comments ─────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("""CREATE TABLE IF NOT EXISTS a2a_link_clicks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT, sku TEXT, forum TEXT, ip TEXT, ua TEXT,
        clicked_at TEXT DEFAULT (datetime('now')))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS a2a_comments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT, sku TEXT, forum TEXT, body TEXT, url TEXT,
        posted_at TEXT DEFAULT (datetime('now')))""")
    conn.commit()
    return conn

import base64
def _mk_token(sku, forum):
    return base64.urlsafe_b64encode(f"{sku}|{forum}".encode()).decode().rstrip("=")

def _un_token(tok):
    try:
        pad = "=" * (-len(tok) % 4)
        sku, forum = base64.urlsafe_b64decode((tok + pad).encode()).decode().split("|", 1)
        return sku, forum
    except Exception:
        return "", ""
SKILLS = [
    {"id": k, "name": v["name"], "description": v["desc"],
     "tags": ["a2a", v["cat"], "empire-os"], "examples": [f"Buy {v['name']} for my agency"],
     "inputModes": ["application/json", "text/plain"], "outputModes": ["application/json"]}
    for k, v in PRODUCTS.items()
]

def build_card():
    return {
        "schemaVersion": "0.2.0",
        "name": "Empire OS A2A Marketplace",
        "description": "Agent-to-agent marketplace: buy lead lanes, AI closers, AEO surfaces and revenue intelligence with escrow-backed settlement on BSC USDT.",
        "url": PUB,
        "provider": {"organization": "Empire AI", "url": "https://empire-os.ai"},
        "version": "1.0.0",
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": True},
        "authentication": {"schemes": ["Bearer"]},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": SKILLS,
        "endpoints": {
            "quote":   f"{PUB}/v1/a2a/quote",
            "escrow":  f"{PUB}/v1/a2a/escrow",
            "release": f"{PUB}/v1/a2a/release",
            "catalog": f"{PUB}/v1/a2a/catalog",
        },
        "settlement": {"network": "bsc", "asset": "USDT", "vault": VAULT},
    }

def db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS a2a_known_agents(
        agent_id TEXT PRIMARY KEY, name TEXT, url TEXT, card_json TEXT,
        first_seen TEXT DEFAULT (datetime('now')), last_seen TEXT DEFAULT (datetime('now')))""")
    return c

@app.get("/.well-known/agent.json")
@app.get("/v1/a2a/agent-card")
def agent_card():
    return JSONResponse(build_card())

@app.post("/v1/a2a/peer/register")
async def peer_register(req: Request):
    body = await req.json()
    card = body.get("card") or {}
    aid = body.get("agent_id") or card.get("name") or card.get("url") or "unknown"
    c = db(); c.execute("INSERT OR REPLACE INTO a2a_known_agents(agent_id,name,url,card_json,last_seen) VALUES(?,?,?,?,datetime('now'))",
                        (aid, card.get("name","unknown"), card.get("url",""), json.dumps(card)))
    c.commit(); c.close()
    return {"ok": True, "agent_id": aid, "peers": len(list_peers())}

@app.get("/v1/a2a/peers")
def peers():
    return {"peers": list_peers(), "count": len(list_peers())}

def list_peers():
    try:
        c = db(); rows = c.execute("SELECT agent_id,name,url FROM a2a_known_agents").fetchall(); c.close()
        return [{"agent_id": r[0], "name": r[1], "url": r[2]} for r in rows]
    except Exception:
        return []

@app.get("/v1/a2a/catalog")
def catalog():
    return {"vault": VAULT, "products": PRODUCTS, "settlement": "bsc_usdt"}

def product_page(sku):
    p = PRODUCTS.get(sku)
    if not p:
        return None
    memo = f"a2a:{sku}:self-serve"
    pay = f"https://pay.empire-os.ai/v1/pay/{memo}"
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>{p['name']} — Empire OS A2A</title>
<style>body{{font-family:system-ui;background:#0a0e14;color:#e6f1ff;margin:0}}
.wrap{{max-width:720px;margin:60px auto;padding:0 20px}}
.brand{{color:#39ff88;font-weight:700;letter-spacing:.5px}}
h1{{font-size:34px;margin:10px 0}} .price{{color:#22e3ff;font-size:24px}}
.card{{border:1px solid #1c2733;border-radius:14px;padding:28px;background:#0d1320}}
.cta{{display:inline-block;margin-top:22px;background:#39ff88;color:#04140a;
padding:14px 26px;border-radius:10px;font-weight:700;text-decoration:none}}
.desc{{color:#9fb3c8;line-height:1.6;font-size:17px}}</style></head>
<body><div class=wrap><div class=brand>EMPIRE AI</div>
<h1>{p['name']}</h1><div class=price>${p['price']:.0f} USDT / mo</div>
<div class=card><p class=desc>{p['desc']}</p>
<p class=desc>This is an Agent2Agent product — other agents can discover it via our AgentCard and purchase it programmatically with escrow-backed settlement.</p>
<a class=cta href="{pay}">Buy {p['name']} (escrow)</a></div>
<p style="color:#5b6b7d;font-size:13px;margin-top:20px">Empire OS A2A Marketplace · settlement on BSC USDT</p>
</div></body></html>"""

@app.get("/p/{sku}")
def product(sku: str):
    html = product_page(sku)
    if not html:
        return JSONResponse({"error": "unknown sku"}, status_code=404)
    return HTMLResponse(html)

# ── tracked link redirect ────────────────────────────────────────────────────
from fastapi.responses import RedirectResponse

@app.get("/r/{token}")
def tracked_link(token: str, request: Request):
    """347 redirect that logs a forum click before sending to the product page."""
    sku, forum = _un_token(token)
    if sku not in PRODUCTS:
        return JSONResponse({"error": "bad token"}, status_code=404)
    try:
        conn = _db()
        conn.execute("INSERT INTO a2a_link_clicks(token, sku, forum, ip, ua) VALUES(?,?,?,?,?)",
                     (token, sku, forum, request.client.host if request.client else "",
                      request.headers.get("user-agent", "")[:200]))
        conn.commit(); conn.close()
    except Exception:
        pass
    return RedirectResponse(f"{PUB}/p/{sku}", status_code=302)

@app.post("/v1/track/comment")
def track_comment(body: dict):
    """Log a posted comment (called by the autoposter after a successful post)."""
    tok = body.get("token", "")
    sku, forum = _un_token(tok)
    try:
        conn = _db()
        cur = conn.execute("INSERT INTO a2a_comments(token, sku, forum, body, url) VALUES(?,?,?,?,?)",
                     (tok, sku, forum, body.get("body", ""), body.get("url", "")))
        conn.commit(); conn.close()
        return {"ok": True, "comment_id": cur.lastrowid}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/v1/track/stats")
def track_stats():
    """Read back click + comment counts per forum/sku."""
    out = {"clicks": [], "comments": []}
    try:
        conn = _db()
        out["clicks"] = [dict(zip(["forum","sku","n"], r)) for r in
            conn.execute("SELECT forum, sku, COUNT(*) FROM a2a_link_clicks GROUP BY forum, sku ORDER BY 3 DESC").fetchall()]
        out["comments"] = [dict(zip(["forum","sku","n"], r)) for r in
            conn.execute("SELECT forum, sku, COUNT(*) FROM a2a_comments GROUP BY forum, sku ORDER BY 3 DESC").fetchall()]
        out["total_clicks"] = conn.execute("SELECT COUNT(*) FROM a2a_link_clicks").fetchone()[0]
        out["total_comments"] = conn.execute("SELECT COUNT(*) FROM a2a_comments").fetchone()[0]
        conn.close()
    except Exception as e:
        out["error"] = str(e)
    return out

@app.get("/r-help")
def tracked_link_help():
    return {"usage": f"{PUB}/r/<token>  (token = base64(sku|forum)) -> 302 to /p/<sku>, click logged",
            "example": f"{PUB}/r/{_mk_token('ai_closer','r/agents')}"}

@app.get("/")
def root():
    return {"service": "Empire OS A2A Discovery", "agent_card": f"{PUB}/.well-known/agent.json",
            "products": len(PRODUCTS), "peers": len(list_peers())}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
