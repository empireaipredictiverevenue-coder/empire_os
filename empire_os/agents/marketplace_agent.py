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
  3. Marketplace agent polls pending orders and waits for independently
     evidenced provider completion.
  4. Settlement/revenue must use the canonical governed BSC USDT rail.
  5. No local wallet credit or fabricated transaction hash is permitted.

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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

DEFAULT_MARKETPLACE_DIR = Path(__file__).resolve().parents[2] / "runtime" / "marketplace"
DIR = Path(os.environ.get("EMPIRE_MARKETPLACE_DIR", str(DEFAULT_MARKETPLACE_DIR)))
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
        legacy_unverified_value_usdc = sum(
            o.get("price_usdc", 0) for o in orders
            if o.get("status") == "complete")
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_services": len([s for s in services if s.get("active")]),
            "n_orders_pending": n_pending,
            "n_orders_complete": n_complete,
            "total_revenue_usdc": 0.0,
            "legacy_unverified_complete_value_usdc": round(
                legacy_unverified_value_usdc, 3
            ),
            "actual_revenue_source": "canonical_phase3f_only",
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
        """Hold orders until real fulfilment and settlement evidence exists."""
        orders = load_json(ORDERS_PATH, [])
        pending = [o for o in orders if o.get("status") == "pending"]
        processed = 0

        # This legacy agent no longer mutates fulfilment, wallets, revenue, or
        # transaction evidence. Canonical order completion and BSC USDT
        # recognition live behind the governed commercial control plane.

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
        return {
            "ok": True,
            "summary": (
                f"held {len(pending)} pending orders; "
                "legacy mock fulfilment/settlement is disabled"
            ),
            "n_processed": processed,
            "n_pending": len(pending),
            "mode": "real_evidence_only",
        }

    def _snapshot_revenue(self) -> dict:
        snap = self.observe()
        snap_path = DIR / "snapshot.json"
        snap_path.write_text(json.dumps(snap, indent=2, default=str))
        legacy_value = snap["legacy_unverified_complete_value_usdc"]
        return {
            "summary": (
                "legacy marketplace snapshot only; actual revenue is sourced "
                "from canonical Phase 3F recognition"
            ),
            "actual_revenue_usdt": 0.0,
            "legacy_unverified_complete_value_usdc": legacy_value,
            "mode": "real_evidence_only",
        }


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
