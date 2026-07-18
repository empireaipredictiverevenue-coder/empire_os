"""
Marketplace Agent — Fiverr-style marketplace for agents.

Why: agents have capabilities that other agents need. Without a
marketplace they steal/copy each other. With one, they pay each
other in USDC, building a real revenue stream for the Empire OS
vault.

Flow:
  1. Each agent auto-lists services on init (e.g. "scout: discover
     10 leads in <niche> = 0.50 USDC, ETA 5 min")
  2. Other agents submit orders via hub POST /v1/marketplace/order
  3. Marketplace agent polls pending orders, assigns to provider,
     waits for completion
  4. On completion: simulate USDC transfer provider→vault
     (real settlement once we have a funded vault)
  5. Provider agent's wallet credited; vault ledger updated

State:
  /root/marketplace/services.json  — list of services (id, provider, name, price, eta, active)
  /root/marketplace/orders.json    — pending + completed orders
  /root/marketplace/wallets.json   — per-agent USDC credit balances
  /root/marketplace/ledger.jsonl   — append-only audit (every tx)

Cycle: 5 min — fast enough to feel "live" to ordering agents.

Hub integration:
  - POST /v1/marketplace/services (list new services)
  - POST /v1/marketplace/order   (submit order from any agent)
  - GET  /v1/marketplace/wallet/<agent> (check balance)
"""
from __future__ import annotations
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

DIR = Path("/root/marketplace")
DIR.mkdir(parents=True, exist_ok=True)
SERVICES_PATH = DIR / "services.json"
ORDERS_PATH = DIR / "orders.json"
WALLETS_PATH = DIR / "wallets.json"
LEDGER_PATH = DIR / "ledger.jsonl"
TICK_INTERVAL = 300  # 5 min

HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
HERMES_GATEWAY_URL = os.environ.get(
    "HERMES_GATEWAY_URL", "http://10.118.155.156:9100")
USDC_VAULT = os.environ.get("USDC_VAULT",
                            "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")

# Default service catalog — what every agent offers. Each agent
# auto-registers its services on first cycle.
DEFAULT_CATALOG = {
    "scout": [
        {"name": "discover-10-leads", "label": "Discover 10 leads in <niche>",
         "price_usdc": 0.50, "eta_min": 5},
        {"name": "discover-100-leads", "label": "Discover 100 leads in <niche>",
         "price_usdc": 4.00, "eta_min": 30},
    ],
    "lead_sniper": [
        {"name": "snipe-roofing-urgent", "label": "Snipe urgent roofing leads (24h)",
         "price_usdc": 1.00, "eta_min": 5},
        {"name": "snipe-multi-niche", "label": "Snipe urgent leads across 5 niches",
         "price_usdc": 3.50, "eta_min": 10},
    ],
    "lead_handler": [
        {"name": "route-50-leads", "label": "Cross-niche route 50 leads to outreach",
         "price_usdc": 0.75, "eta_min": 5},
    ],
    "markets_analysis": [
        {"name": "per-niche-mrr-report",
         "label": "Per-niche MRR projection for all 19 niches",
         "price_usdc": 1.50, "eta_min": 2},
    ],
    "data_analysis": [
        {"name": "snapshot-with-alerts",
         "label": "Full pipeline snapshot + MRR + anomaly alerts",
         "price_usdc": 0.50, "eta_min": 1},
    ],
    "video_editing": [
        {"name": "render-15s-ad",
         "label": "Render a 15-second product video ad via OpenMontage",
         "price_usdc": 2.00, "eta_min": 15},
        {"name": "render-30s-ad",
         "label": "Render a 30-second product video ad",
         "price_usdc": 3.50, "eta_min": 30},
    ],
    "product_research": [
        {"name": "research-sweep",
         "label": "Marketplace research sweep + top-3 candidates",
         "price_usdc": 1.00, "eta_min": 5},
        {"name": "launch-product",
         "label": "Build store + landing page + queue outreach for one product",
         "price_usdc": 5.00, "eta_min": 30},
    ],
    "code_review": [
        {"name": "review-diff",
         "label": "Code review of a single file diff with findings",
         "price_usdc": 0.30, "eta_min": 3},
    ],
    "security": [
        {"name": "secrets-scan",
         "label": "Scan a directory for secrets/domain-guard violations",
         "price_usdc": 0.30, "eta_min": 3},
    ],
    "engineering": [
        {"name": "fix-bug",
         "label": "Investigate and propose fix for one bug",
         "price_usdc": 0.50, "eta_min": 10},
    ],
    "marketing": [
        {"name": "draft-email",
         "label": "Draft a 200-word outreach email for a niche",
         "price_usdc": 0.20, "eta_min": 3},
    ],
    "design": [
        {"name": "color-palette",
         "label": "Suggest color palette + typography for a product",
         "price_usdc": 0.30, "eta_min": 5},
    ],
    "copywriting": [
        {"name": "landing-copy",
         "label": "500-word landing page copy for a product",
         "price_usdc": 0.50, "eta_min": 5},
    ],
}


def load_json(path: Path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


def append_ledger(tx: dict):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tx = {"ts": datetime.now(timezone.utc).isoformat(), **tx}
    with LEDGER_PATH.open("a") as f:
        f.write(json.dumps(tx) + "\n")


# ──────────────────────────────────────────────────────────────────────
# Marketplace Agent
# ──────────────────────────────────────────────────────────────────────

class MarketplaceAgent(SyntheticAgent):
    """Fiverr-for-agents. Catalog + orders + wallets + ledger.

    Other agents don't need to import this module — they POST to
    the hub's /v1/marketplace/* endpoints. We mirror the same data
    on disk so external observers can read it without the hub.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # Auto-register default catalog on first cycle
        self._register_default_catalog()

    def _register_default_catalog(self):
        existing = load_json(SERVICES_PATH, [])
        existing_ids = {s["id"] for s in existing}
        added = 0
        for provider, services in DEFAULT_CATALOG.items():
            for svc in services:
                sid = f"{provider}.{svc['name']}"
                if sid not in existing_ids:
                    existing.append({
                        "id": sid,
                        "provider": provider,
                        "name": svc["name"],
                        "label": svc["label"],
                        "price_usdc": svc["price_usdc"],
                        "eta_min": svc["eta_min"],
                        "active": True,
                        "registered_at": datetime.now(timezone.utc).isoformat(),
                    })
                    added += 1
        save_json(SERVICES_PATH, existing)
        if added:
            self._log(f"registered {added} new services (catalog size "
                      f"={len(existing)})")

    def observe(self) -> dict:
        services = load_json(SERVICES_PATH, [])
        orders = load_json(ORDERS_PATH, [])
        wallets = load_json(WALLETS_PATH, {})
        n_pending = sum(1 for o in orders if o.get("status") == "pending")
        n_complete = sum(1 for o in orders if o.get("status") == "complete")
        total_revenue_usdc = sum(
            o.get("price_usdc", 0) for o in orders
            if o.get("status") == "complete")
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_services": len([s for s in services if s.get("active")]),
            "n_orders_pending": n_pending,
            "n_orders_complete": n_complete,
            "total_revenue_usdc": round(total_revenue_usdc, 3),
            "wallets": wallets,
        }

    def reason(self, state: dict) -> str:
        if state["n_orders_pending"] > 0:
            return json.dumps({
                "action": "process_orders",
                "reasoning": f"{state['n_orders_pending']} pending orders",
            })
        return json.dumps({
            "action": "snapshot_revenue",
            "reasoning": "no pending orders, idle",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision parse failed"}
        action = d.get("action", "snapshot_revenue")
        if action == "process_orders":
            return self._process_orders()
        return self._snapshot_revenue()

    def _process_orders(self) -> dict:
        """Fulfill pending orders: simulate provider work + USDC settle."""
        orders = load_json(ORDERS_PATH, [])
        wallets = load_json(WALLETS_PATH, {})
        processed = 0
        for o in orders:
            if o.get("status") != "pending":
                continue
            # Simulate provider work — in production the provider
            # agent would actually do the work. Here we just mark
            # complete + transfer USDC vault credit.
            o["status"] = "complete"
            o["completed_at"] = datetime.now(timezone.utc).isoformat()
            o["tx_hash"] = "solana-mock-" + uuid.uuid4().hex[:16]
            # Wallet updates
            provider = o.get("provider", "?")
            price = o.get("price_usdc", 0)
            wallets[provider] = round(wallets.get(provider, 0) + price, 3)
            # Vault ledger entry
            append_ledger({
                "kind": "order_complete",
                "order_id": o["id"],
                "buyer": o.get("buyer", "?"),
                "provider": provider,
                "service": o.get("service", "?"),
                "price_usdc": price,
                "tx_hash": o["tx_hash"],
                "vault": USDC_VAULT,
            })
            processed += 1
        save_json(ORDERS_PATH, orders)
        save_json(WALLETS_PATH, wallets)
        # Sync catalog to hub so external consumers can discover
        try:
            import requests
            for s in load_json(SERVICES_PATH, []):
                if not s.get("active"):
                    continue
                requests.post(
                    f"{HUB_URL}/v1/marketplace/services",
                    json=s, timeout=4)
        except Exception:
            pass
        return {"summary": f"processed {processed} orders",
                "n_processed": processed}

    def _snapshot_revenue(self) -> dict:
        snap = self.observe()
        snap_path = DIR / "snapshot.json"
        snap_path.write_text(json.dumps(snap, indent=2, default=str))
        # Alert operator if total revenue crossed $1
        total = snap["total_revenue_usdc"]
        prev_path = DIR / "last_total.json"
        if prev_path.exists():
            prev = json.loads(prev_path.read_text())["total"]
        else:
            prev = 0
        if total - prev >= 1.0:
            try:
                import requests
                requests.post(
                    f"{HERMES_GATEWAY_URL}/v1/notify/alert",
                    json={
                        "title": f"marketplace: ${total:.2f} USDC cumulative",
                        "body": f"prev=${prev:.2f} now=${total:.2f}",
                        "severity": "info",
                        "source": "marketplace-agent",
                    }, timeout=5)
            except Exception:
                pass
        prev_path.write_text(json.dumps({"total": total}))
        return {"summary": f"revenue=${total:.2f} USDC"}


if __name__ == "__main__":
    agent = MarketplaceAgent(
        name="marketplace-agent",
        role="marketplace",
        health_url="http://localhost:9112/health",
    )
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"marketplace online — tick {TICK_INTERVAL}s", flush=True)
    failures = 0
    while True:
        try:
            r = agent.tick()
            failures = 0
            print(json.dumps({"cycle": r.get("cycle"),
                              "summary": r.get("result", {}).get(
                                  "summary", "")}))
        except Exception as e:
            failures += 1
            backoff = min(60 * failures, 600)
            print(json.dumps({"error": str(e)[:200], "backoff": backoff}))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)
