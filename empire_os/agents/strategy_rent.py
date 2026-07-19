#!/usr/bin/env python3
"""
strategy_rent.py — RENT strategy (lead arbitrage / syndication).

Capture leads CHEAP (scrape funnel, ~2c/lead) and RENT them to buyers who
pay per-lead (si_subscription.per_lead_cents). The spread = arbitrage margin.

Flow per cheap lead:
  1. find_matching_buyers(lead)  -> buyers w/ per_lead_cents in that niche
  2. deliver_lead(buyer, lead)   -> webhook/email confirmed
  3. bill_on_delivery(buyer, lead) -> POST /v1/ppc/log_invoice (USDC)
  4. log arbitrage: acq_cost(2c) vs billed(per_lead_cents)

Only runs on funnels where cost < buyer's per_lead_cents (positive margin).
Wired into the LIVE per-lead billing loop (lead_deliverer). No fabrication:
if no buyer matches, lead is parked, not billed.
"""
from __future__ import annotations
import os, sqlite3, sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
# cost proxy per funnel (cents/lead)
ACQ_COST = {"scrape": 2, "aeo": 15, "cortex": 5, "referral": 8, "outreach": 120}


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_rent_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id TEXT, niche TEXT,
        buyer TEXT, acq_cost_cents INT, billed_cents INT, margin_cents INT,
        invoice_id TEXT, ts TEXT)""")
    return c


def run_rent(dry_run: bool = False, max_leads: int = 200) -> dict:
    """Syndicate cheap leads to per-lead buyers; bill on delivery."""
    import empire_os.agents.lead_deliverer_agent as LD
    import empire_os.agents.funnel_intake as FI
    c = _db()
    # hot niches from predictive_router signal (real engagement velocity)
    hot = set()
    try:
        hc = sqlite3.connect(DB, timeout=30)
        for (kw,) in hc.execute("SELECT DISTINCT niche FROM hot_targets").fetchall():
            hot.add((kw or "").lower().replace(" ", "_"))
        hc.close()
    except Exception:
        pass
    # pull cheap leads from scrape funnel not yet rented
    leads = c.execute(
        "SELECT id, email, niche, metro FROM si_intake_event "
        "WHERE funnel='scrape' AND niche != '' "
        "AND id NOT IN (SELECT CAST(lead_id AS INT) FROM strategy_rent_ledger) "
        "ORDER BY id DESC LIMIT ?", (max_leads,)).fetchall()
    if hot:
        # signal-driven priority: hot-niche leads first
        leads = sorted(leads, key=lambda r: 0 if FI.normalize_niche(r[2]) in hot else 1)
    stats = {"leads_seen": len(leads), "delivered": 0, "billed": 0,
             "margin_cents": 0, "no_buyer": 0}
    for lid, email, niche, metro in leads:
        lead = {"lead_id": lid, "email": email,
                "niche": FI.normalize_niche(niche), "metro": metro}
        buyers = LD.find_matching_buyers(lead)
        if not buyers:
            stats["no_buyer"] += 1
            continue
        for b in buyers:
            per_lead = int(b.get("per_lead_cents") or 0)
            acq = ACQ_COST.get("scrape", 2)
            if per_lead <= acq:
                continue  # negative margin -> skip (no rent)
            if dry_run:
                stats["delivered"] += 1
                stats["billed"] += 1
                stats["margin_cents"] += (per_lead - acq)
                continue
            ok = LD.deliver_lead(b, lead)
            if ok:
                inv = LD.bill_on_delivery(b, lead)
                margin = per_lead - acq
                c.execute(
                    "INSERT INTO strategy_rent_ledger "
                    "(lead_id,niche,buyer,acq_cost_cents,billed_cents,margin_cents,invoice_id,ts) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (str(lid), niche, b.get("tenant_id", ""),
                     acq, per_lead, margin, inv or "",
                     datetime.now(timezone.utc).isoformat()))
                c.commit()
                stats["delivered"] += 1
                stats["billed"] += 1
                stats["margin_cents"] += margin
    c.close()
    return stats


if __name__ == "__main__":
    print("🏠 RENT strategy (dry-run):")
    print(run_rent(dry_run=True, max_leads=100))
