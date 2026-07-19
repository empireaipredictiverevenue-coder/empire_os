#!/usr/bin/env python3
"""
revenue_reasoner.py — Empire OS predictive revenue AGI reasoning loop.

The missing piece: a closed-loop agent that READS live state -> REASONS via a
frontier model (OpenRouter tencent/hy3:free) -> ACTS on the hub's own endpoints
-> OBSERVES the result -> repeats. This is the "general AGI" for revenue,
built from our own infrastructure (hub + MCP + lane_router), not north-mini docs.

Loop:
  1. snapshot live metrics from the hub (/v1/leads/counts, lane occupancy,
     buy_signal distribution, a2a_mesh interest)
  2. send to OpenRouter with a system prompt defining the revenue AGI role
  3. parse the LLM's structured action JSON
  4. execute the action (route leads, adjust pricing, post to MCP mesh,
     pitch a lane to agent networks)
  5. sleep, repeat

Runs as a pm2 daemon. No external email/creds needed — uses the hub's
existing HTTP API + the live MCP supply layer.

Env: OPENROUTER_API_KEY (from /root/.empire_secrets/openrouter.env)
"""
import os, sys, json, time, urllib.request, urllib.error, sqlite3

sys.path.insert(0, "/root/empire_os")

def _load_openrouter_key():
    # prefer env, then container .env, then host secret path
    k = os.environ.get("OPENROUTER_API_KEY", "")
    if k:
        return k
    for p in ("/root/empire_os/.env", "/root/.empire_secrets/openrouter.env"):
        try:
            txt = open(p).read()
            if "OPENROUTER_API_KEY=" in txt:
                return txt.split("OPENROUTER_API_KEY=")[1].splitlines()[0].strip()
        except Exception:
            pass
    return ""

OPENROUTER_KEY = _load_openrouter_key()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("REASONER_MODEL", "tencent/hy3:free")
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
LOOP_SECONDS = int(os.environ.get("REASONER_LOOP", "300"))  # 5 min

SYSTEM = """You are the Empire OS Revenue AGI — an autonomous reasoning agent
for a lead-marketplace business. You operate a closed loop: observe live
metrics, decide the single highest-ROI action, output a structured command.

Available actions (return ONE as JSON, nothing else):
  {"action":"route_leads"}  -> route all valid-niche leads not yet in lanes
  {"action":"pitch_lane","niche":"<sub_niche>","metro":"<code>"} -> post that lane offer to a2a_mesh
  {"action":"adjust_price","sku":"<sku>","tier":"T1|T2|T3|T4","usdc":<float>} -> reprice a SKU tier
  {"action":"seed_mesh"} -> re-publish all occupied lanes to a2a_mesh for agent discovery
  {"action":"report"} -> emit a one-line strategic status (no side effects)

Context you receive each tick: live counts (crm_leads, valid_niche, lane_leads,
lanes_populated), buy_signal distribution, and recent a2a_mesh interest.

Rules:
- Prefer actions that increase monetizable inventory (route_leads, seed_mesh).
- Only adjust_price if lane occupancy is low (<30%) to stimulate demand.
- Never invent leads. Act only on real state given.
- Output valid JSON only. No prose, no markdown fences."""

def http_get(path, timeout=10):
    try:
        with urllib.request.urlopen(HUB + path, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:
        return 0, {"error": str(e)[:120]}

def http_post(path, payload, timeout=10):
    req = urllib.request.Request(HUB + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:160]
    except Exception as e:
        return 0, str(e)[:120]

def snapshot():
    """Read live state from the hub + db for the LLM context."""
    st, counts = http_get("/v1/leads/counts")
    bt = counts.get("by_table", {}) if st == 200 else {}
    # prefer hub values, but fall back to db (authoritative) if hub unavailable
    crm = lanes = 0
    try:
        con0 = sqlite3.connect("/root/empire_os/empire_os.db")
        con0.execute("PRAGMA busy_timeout=30000")
        if st != 200 or not bt:
            crm = con0.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0]
            lanes = con0.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0]
        else:
            crm = bt.get("crm_leads", con0.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0])
            lanes = bt.get("lane_leads", con0.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0])
        con0.close()
    except Exception:
        crm = bt.get("crm_leads", 0)
        lanes = bt.get("lane_leads", 0)
    # db-side detail (resilient: each query independent)
    valid = occupied = total_lanes = hi = 0
    try:
        con = sqlite3.connect("/root/empire_os/empire_os.db")
        con.execute("PRAGMA busy_timeout=30000")
        try:
            valid = con.execute("SELECT COUNT(*) FROM crm_leads WHERE niche IN "
                                "(SELECT DISTINCT sub_niche FROM lanes)").fetchone()[0]
        except Exception:
            pass
        try:
            occupied = con.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by "
                                   "IS NOT NULL").fetchone()[0]
        except Exception:
            pass
        try:
            total_lanes = con.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
        except Exception:
            pass
        try:
            hi = con.execute("SELECT COUNT(*) FROM crm_leads WHERE buy_signal_score "
                             ">0.5").fetchone()[0]
        except Exception:
            pass
        con.close()
    except Exception:
        pass
    # a2a mesh interest
    try:
        mesh = open("/root/feedback/a2a_mesh.jsonl").read().splitlines()
        mesh_intent = len([m for m in mesh if m.strip()])
    except Exception:
        mesh_intent = 0
    return {
        "crm_leads": crm, "valid_niche": valid, "lane_leads": lanes,
        "lanes_occupied": occupied, "lanes_total": total_lanes,
        "high_signal_leads": hi, "a2a_mesh_entries": mesh_intent,
    }

def reason(ctx):
    """Ask the model for the next action given live context."""
    if not OPENROUTER_KEY:
        return {"action": "report"}  # safe fallback if no key
    prompt = (f"LIVE STATE: {json.dumps(ctx)}\n"
              "Decide the highest-ROI action now. Output JSON only.")
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(OPENROUTER_URL, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}",
                     "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode())
        content = out["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        return {"action": "report", "note": f"llm error: {str(e)[:80]}"}

def act(cmd, ctx):
    """Execute the LLM's chosen action via hub endpoints / db."""
    a = cmd.get("action")
    if a == "route_leads":
        # route all valid-niche leads not in lanes
        import sys as _s
        _s.path.insert(0, "/root/empire_os")
        from empire_os.lane_router import route_lead
        con = sqlite3.connect("/root/empire_os/empire_os.db")
        con.execute("PRAGMA busy_timeout=30000")
        rows = con.execute(
            "SELECT lead_uid,niche,metro,state FROM crm_leads WHERE niche IN "
            "(SELECT DISTINCT sub_niche FROM lanes) AND lead_uid NOT IN "
            "(SELECT prospect_id FROM lane_leads)").fetchall()
        n = 0
        for lid, nic, metro, state in rows:
            try:
                route_lead(con, lid, f"niche={nic}|metro={metro}", state=state)
                n += 1
            except Exception:
                pass
        con.commit(); con.close()
        return f"routed {n} leads into lanes"
    if a == "seed_mesh":
        # re-publish occupied lanes to a2a_mesh for agent discovery
        con = sqlite3.connect("/root/empire_os/empire_os.db")
        rows = con.execute(
            "SELECT sub_niche,metro FROM lanes WHERE occupied_by IS NOT NULL"
            ).fetchall()
        con.close()
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        seeded = 0
        with open("/root/feedback/a2a_mesh.jsonl", "a") as f:
            for sub, metro in rows:
                f.write(json.dumps({
                    "ts": now, "seller_agent": "empire-reasoner",
                    "wallet": "EmpireVaultUSDCSolana", "product": "lead_lane",
                    "quote": {"sku": f"lead_lane_{sub}_{metro}", "niche": sub,
                              "metro": metro, "price_usdc": 199.0,
                              "tiers": {"T1": 199.0, "T2": 499.0, "T3": 1499.0},
                              "memo": f"LANE_{sub.upper()}_{metro.upper()}",
                              "mcp": "https://empire-ai.co.uk/mcp",
                              "settle": "POST /v1/a2a/negotiate"}}) + "\n")
                seeded += 1
        return f"seeded {seeded} lane offers to a2a_mesh"
    if a == "pitch_lane":
        nic, metro = cmd.get("niche"), cmd.get("metro")
        # verify lane exists + occupied, then seed it specifically
        return act({"action": "seed_mesh"}, ctx)  # simplified: seed all
    if a == "adjust_price":
        return f"price adjust deferred (sku={cmd.get('sku')}) — manual review"
    # report / fallback
    return f"state: crm={ctx['crm_leads']} valid={ctx['valid_niche']} " \
           f"lanes={ctx['lane_leads']} mesh={ctx['a2a_mesh_entries']}"

def loop_once(iteration):
    ctx = snapshot()
    cmd = reason(ctx)
    result = act(cmd, ctx)
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] tick {iteration} | ctx={ctx} | cmd={cmd.get('action')} | {result}",
          flush=True)
    return ctx

def main():
    print(f"[reasoner] starting | model={MODEL} | loop={LOOP_SECONDS}s | "
          f"key={'set' if OPENROUTER_KEY else 'MISSING'}", flush=True)
    i = 0
    while True:
        try:
            i += 1
            loop_once(i)
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] tick {i} ERROR: {e}", flush=True)
        time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()
