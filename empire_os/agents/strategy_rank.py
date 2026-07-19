#!/usr/bin/env python3
"""
strategy_rank.py — RANK funnels/niches by ROI so we double down on winners.

ROI proxy per (funnel, niche):
    demand   = buyers subscribed w/ per_lead_cents in that niche  (paying demand)
    supply   = leads/events in that niche from the funnel
    value    = avg deal cents for that plan (silver/gold tier)
    cost     = acquisition cost proxy (scrape=low, aeo=mid, outreach=high)
    roi      = (demand * value) / max(cost * supply, 1)

Writes `strategy_rank(funnel, niche, demand, supply, roi, tier)` so the
orchestrator + cortex can see the ranked board. No fabricated revenue.
"""
from __future__ import annotations
import os, sqlite3, sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")

# acquisition cost proxy per funnel (cents per lead, conservative)
COST_PER_LEAD = {"scrape": 2, "aeo": 15, "outreach": 120, "cortex": 5, "referral": 8}
# plan value cents (from hybrid TIER_RATES)
PLAN_VALUE = {"bronze": 29900, "silver": 59900, "gold": 119900, "platinum": 239900}


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_rank (
        id INTEGER PRIMARY KEY AUTOINCREMENT, funnel TEXT, niche TEXT,
        demand INT, supply INT, roi REAL, tier TEXT, ts TEXT)""")
    return c


def compute() -> list:
    c = _db()
    # demand: subscriptions with per_lead_cents grouped by niche
    demand = dict(c.execute(
        "SELECT niche, COUNT(*) FROM si_subscription "
        "WHERE per_lead_cents > 0 GROUP BY niche").fetchall())
    # value per niche = max plan value among its subscribers
    plan_vals = dict(c.execute(
        "SELECT niche, plan FROM si_subscription WHERE plan IS NOT NULL").fetchall())
    # supply: events per (funnel, niche)
    supply = {}
    for funnel, niche, n in c.execute(
            "SELECT funnel, niche, COUNT(*) FROM si_intake_event "
            "WHERE niche != '' GROUP BY funnel, niche").fetchall():
        supply[(funnel, niche)] = n

    rows = []
    for (funnel, niche), supply_n in supply.items():
        d = demand.get(niche, 0)
        plan = plan_vals.get(niche, "silver")
        value = PLAN_VALUE.get(plan, 59900)
        cost = COST_PER_LEAD.get(funnel, 10)
        roi = (d * value) / max(cost * supply_n, 1)
        tier = ("A" if roi > 50 else "B" if roi > 10 else "C")
        rows.append({
            "funnel": funnel, "niche": niche, "demand": d,
            "supply": supply_n, "roi": round(roi, 2), "tier": tier})
    # persist
    c.execute("DELETE FROM strategy_rank")
    ts = datetime.now(timezone.utc).isoformat()
    for r in rows:
        c.execute("INSERT INTO strategy_rank (funnel,niche,demand,supply,roi,tier,ts) "
                  "VALUES (?,?,?,?,?,?,?)",
                  (r["funnel"], r["niche"], r["demand"], r["supply"],
                   r["roi"], r["tier"], ts))
    c.commit(); c.close()
    rows.sort(key=lambda x: x["roi"], reverse=True)
    return rows


if __name__ == "__main__":
    ranked = compute()
    print(f"RANKED {len(ranked)} (funnel,niche) combos by ROI:")
    for r in ranked[:12]:
        print(f"  [{r['tier']}] {r['funnel']:8} {r['niche']:12} "
              f"demand={r['demand']} supply={r['supply']} roi={r['roi']}")
