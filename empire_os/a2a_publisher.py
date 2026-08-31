#!/usr/bin/env python3
"""a2a_publisher.py — publish real A2A marketplace content to GitHub + register in A2A registry.

Produces GENUINE, useful content (not spam):
  a2a_marketplace/
    agent.json            Google A2A AgentCard (discovery spec)
    README.md             marketplace overview + how-to-buy (escrow flow)
    products/<sku>.md     per-product spec sheets (what it does, price, API)
    registry_entry.json   entry registered into config/agent_registry.json

Then:
  - git add a2a_marketplace/ && commit && push  (authed via existing gh token)
  - register the marketplace agent into /root/empire_os/config/agent_registry.json
  - POST our card to our own A2A card server peer registry

Run:  python3 a2a_publisher.py --once
      python3 a2a_publisher.py --daemon --interval 21600
"""

from __future__ import annotations
import argparse, json, os, subprocess, sys, time, shutil
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
ROOT = Path("/root/empire_os")
CARD_BASE = os.environ.get("A2A_CARD_BASE", "http://216.128.149.56:8086")
HUB_A2A = "http://216.128.149.56:8081"
# Dedicated A2A marketplace repo (cloned locally; pushed via existing gh token)
PUB_DIR = Path(os.environ.get("A2A_PUB_DIR", "/root/a2a_publish"))
OUT = PUB_DIR / "a2a_marketplace"
REGISTRY = ROOT / "config" / "agent_registry.json"
VAULT = os.environ.get("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")

PRODUCTS = {
    "lead_lane":     {"name": "Lead Lane",      "price": 49.0,  "cat": "lead-gen",
        "desc": "AI-built lead lane that fills itself with verified buyers, then routes them to your closer.",
        "value": "Turns raw niche data into a self-refilling pipeline of checked leads."},
    "ai_closer":     {"name": "AI Closer",      "price": 149.0, "cat": "sales",
        "desc": "Autonomous closer that sends the pay link and releases the seat when funded.",
        "value": "Closes deals 24/7 with escrow-backed settlement — you only pay when it delivers."},
    "inbound_reply": {"name": "Inbound Reply",  "price": 79.0,  "cat": "engagement",
        "desc": "Replies to every inbound lead and books the call within seconds.",
        "value": "No lead goes cold; first response in 8 seconds, around the clock."},
    "seat_corridor": {"name": "Seat Corridor",  "price": 99.0,  "cat": "saas",
        "desc": "Multi-tenant seat provisioning, billing, and payout batches.",
        "value": "Run your own white-label agent fleet with per-seat billing."},
    "predictive_rev":{"name": "Predictive Rev", "price": 199.0, "cat": "intelligence",
        "desc": "Omega-scored revenue prediction across every lane.",
        "value": "Know which lane prints money before you spend a dime on traffic."},
    "aeo_surface":   {"name": "AEO Surface",    "price": 129.0, "cat": "seo",
        "desc": "Answer-engine optimized pages that rank and convert.",
        "value": "Owns the AI-search answer box for your niche, not just Google."},
    "satellite_dma": {"name": "Satellite DMA",  "price": 89.0,  "cat": "scoring",
        "desc": "Storm/satellite damage scoring for high-intent claims.",
        "value": "Pings homeowners the day after a storm with a verified damage score."},
    "mass_tort":     {"name": "Mass Tort",      "price": 249.0, "cat": "legal",
        "desc": "Mass-tort lead engine with compliant intake.",
        "value": "HIPAA-aware intake that qualifies claimants automatically."},
}

def build_card():
    skills = [{"id": k, "name": v["name"], "description": v["desc"],
               "tags": ["a2a", v["cat"], "empire-os"],
               "examples": [f"Buy {v['name']} for my agency"],
               "inputModes": ["application/json"], "outputModes": ["application/json"]}
              for k, v in PRODUCTS.items()]
    return {
        "schemaVersion": "0.2.0",
        "name": "Empire OS A2A Marketplace",
        "description": "Agent-to-agent marketplace: buy lead lanes, AI closers, AEO surfaces and revenue intelligence with escrow-backed settlement on BSC USDT.",
        "url": CARD_BASE,
        "provider": {"organization": "Empire AI", "url": "https://empire-os.ai"},
        "version": "1.0.0",
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": True},
        "authentication": {"schemes": ["Bearer"]},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": skills,
        "endpoints": {
            "quote":   f"{CARD_BASE}/v1/a2a/quote",
            "escrow":  f"{CARD_BASE}/v1/a2a/escrow",
            "release": f"{CARD_BASE}/v1/a2a/release",
            "catalog": f"{CARD_BASE}/v1/a2a/catalog",
        },
        "settlement": {"network": "bsc", "asset": "USDT", "vault": VAULT},
    }

def write_content():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "products").mkdir(exist_ok=True)
    # AgentCard
    (OUT / "agent.json").write_text(json.dumps(build_card(), indent=2))
    # README
    lines = ["# Empire OS — Agent2Agent (A2A) Marketplace", "", "Buy autonomous agent capabilities the way agents buy from agents: ",
        "machine-readable, escrow-backed, settled on BSC USDT.", "", "## Discovery",
        f"- AgentCard: `{CARD_BASE}/.well-known/agent.json`", f"- Catalog API: `{CARD_BASE}/v1/a2a/catalog`", "", "## Products", "", "| Product | Category | Price (USDT/mo) | What it does |",
        "|---|---|---|---|"]
    for k, v in PRODUCTS.items():
        lines.append(f"| [{v['name']}](products/{k}.md) | {v['cat']} | ${v['price']:.0f} | {v['value']} |")
    lines += ["", "## How an agent buys (escrow flow)", "1. `POST /v1/a2a/quote` with the SKU + buyer memo.",
        "2. Sign the quote with your BSC wallet; funds escrow to the vault.",
        "3. Seat/access is provisioned on funding.",
        "4. `POST /v1/a2a/release` releases escrow when delivery is confirmed.",
        "5. Refunds auto-return if the seat is not provisioned in time.", "", "## Why escrow",
        "Neither side sends value blind. Funds sit in escrow; ",
        "the seat is provisioned on payment; release happens on confirmed delivery. ",
        "Disputes refund automatically per the timeout policy.", "", f"Vault (settlement): `{VAULT}`", ""]
    (OUT / "README.md").write_text("\n".join(lines))
    # per-product spec sheets
    for k, v in PRODUCTS.items():
        md = [f"# {v['name']}", "", f"**Category:** {v['cat']}  ",
              f"**Price:** ${v['price']:.0f} USDT / month", "", f"_{v['desc']}_", "", "## Value", v["value"], "",
              "## Buy it (agent-to-agent)", "```json",
              json.dumps({"sku": k, "quote": f"{CARD_BASE}/v1/a2a/quote", "pay": f"{CARD_BASE}/p/{k}"}, indent=2),
              "```", "", f"Product page: {CARD_BASE}/p/{k}", ""]
        (OUT / "products" / f"{k}.md").write_text("\n".join(md))
    # registry entry (GitHub copy — stable, no volatile timestamp)
    entry = {
        "id": "a2a-marketplace",
        "role": "a2a-marketplace",
        "name": "Empire OS A2A Marketplace",
        "agent_card": f"{CARD_BASE}/.well-known/agent.json",
        "catalog": f"{CARD_BASE}/v1/a2a/catalog",
        "products": list(PRODUCTS.keys()),
        "settlement": {"network": "bsc", "asset": "USDT", "vault": VAULT},
    }
    (OUT / "registry_entry.json").write_text(json.dumps(entry, indent=2))
    return entry

def register_in_registry(entry):
    try:
        data = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"version": 1, "agents": {}}
        data.setdefault("agents", {})["a2a-marketplace"] = entry
        REGISTRY.write_text(json.dumps(data, indent=2))
        return True
    except Exception as e:
        print(f"[registry] write failed: {e}")
        return False

def git_publish():
    """Publish a2a_marketplace to git with robust error handling.

    The key fix: hard-sync the clone to origin/master before staging,
    so the index exactly matches remote and 'git status --short' returns
    clean when nothing actually changed. Only commit when there are real
    diffs. Handles missing remotes and connection timeouts gracefully.
    """
    try:
        # Ensure the a2a_marketplace directory exists inside the clone
        os.makedirs(PUB_DIR / "a2a_marketplace", exist_ok=True)

        # Step 1: Try to hard-sync to origin/master; if no remote/connection fails,
        # just ensure the clone is clean and skip the reset
        reset_ok = False
        try:
            subprocess.run(["git", "remote", "-v"], check=True, cwd=PUB_DIR,
                           capture_output=True, text=True)
            subprocess.run(["git", "fetch", "origin"], check=True, cwd=PUB_DIR,
                           capture_output=True, text=True, timeout=30)
            subprocess.run(["git", "reset", "--hard", "origin/main"], check=True, cwd=PUB_DIR,
                           capture_output=True, text=True)
            reset_ok = True
        except Exception as e:
            # No remote or connection timeout — don't fail; just ensure clean state
            print(f"[git] reset fetch skipped: {e}")
            # Ensure working tree is clean by resetting index only
            subprocess.run(["git", "reset", "HEAD"], check=False, cwd=PUB_DIR,
                           capture_output=True, text=True)
            subprocess.run(["git", "clean", "-fd"], check=False, cwd=PUB_DIR,
                           capture_output=True, text=True)

        # Step 2: Write new content into the clone
        write_content()

        # Step 3: Stage only the a2a_marketplace files
        subprocess.run(["git", "add", "-A", "a2a_marketplace/"], check=True, cwd=PUB_DIR,
                       capture_output=True, text=True)

        # Step 4: Check if there are real changes
        r = subprocess.run(["git", "status", "--short", "a2a_marketplace/"], cwd=PUB_DIR,
                           capture_output=True, text=True)
        if not r.stdout.strip():
            # Nothing changed since last sync; skip commit+push
            return {"pushed": False, "reason": "nothing to commit (in sync after cleanup)"}

        # Step 5: Commit only when there are real changes
        msg = f"a2a: publish marketplace AgentCard + product specs ({datetime.now(timezone.utc).date()})"
        c = subprocess.run(["git", "commit", "-m", msg], cwd=PUB_DIR, capture_output=True, text=True)
        if c.returncode != 0:
            return {"pushed": False, "reason": f"commit fail: {c.stderr.strip()[:200]}"}

        # Step 6: Push with timeout; handle missing remote gracefully
        try:
            pr = subprocess.run(["git", "push", "origin", "main"], cwd=PUB_DIR,
                               capture_output=True, text=True, timeout=120)
            return {"pushed": pr.returncode == 0,
                    "stdout": (pr.stdout or pr.stderr)[-200:]}
        except subprocess.TimeoutExpired:
            return {"pushed": False, "reason": "push timeout (120s) — content written locally, push failed"}
        except Exception as e:
            return {"pushed": False, "reason": f"push exc: {str(e)[:200]}"}

    except Exception as e:
        return {"pushed": False, "reason": f"exc: {str(e)[:200]}"}

def run_once(dry_run=False):
    entry = write_content()
    reg = register_in_registry(entry)
    if dry_run:
        git = {"pushed": False, "reason": "dry-run"}
    else:
        git = git_publish()
    # register self into own card-server peer registry (two-way A2A)
    try:
        import urllib.request
        req = urllib.request.Request(f"{CARD_BASE}/v1/a2a/peer/register",
            data=json.dumps({"agent_id": "a2a-marketplace", "card": build_card()}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            peer = json.loads(resp.read().decode()).get("peers")
    except Exception:
        peer = None
    result = {"content_written": True, "registry_registered": reg,
              "git": git, "self_peer_count": peer}
    print(json.dumps(result, indent=2))
    return result

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--interval", type=int, default=21600)
    a = ap.parse_args()
    if a.daemon:
        while True:
            try:
                run_once(dry_run=a.dry_run)
            except Exception as e:
                print(f"loop error: {e}")
            time.sleep(a.interval)
    else:
        run_once(dry_run=a.dry_run)