#!/usr/bin/env python3
"""
strategy_rolling_stones.py — "You can't always get what you want,
but if you try sometimes you get what you need."

The VOLUME tsunami play. Instead of waiting for perfectly-matched,
high-intent leads, we flood the top of EVERY funnel and lower the
match threshold so even low-conversion / non-ideal niches yield buyers.
Math: with N funnels x M leads and a baseline conversion c, total buyers
~ N*M*c. Lowering the bar from c_high to c_low multiplies yield.

This strategy:
  1. Reports funnel volume (the "flood").
  2. Runs a WIDE match (every niche with ANY subscriber) so no lead is wasted.
  3. Tracks "want vs need": ideal matches vs needs-met-from-off-niche.
  4. Logs the yield multiple vs the strict-threshold baseline.
"""
from __future__ import annotations
import os, sqlite3, sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS strategy_rolling_stones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, funnel TEXT, total_leads INT,
        wide_matches INT, ideal_matches INT, need_yield INT, ts TEXT)""")
    return c


def run(dry_run: bool = True, max_per_funnel: int = 500) -> dict:
    import empire_os.agents.lead_deliverer_agent as LD
    import empire_os.agents.funnel_intake as FI
    c = _db()
    # niches that HAVE any paying subscriber (demand exists)
    demand_niches = [r[0] for r in c.execute(
        "SELECT DISTINCT niche FROM si_subscription WHERE per_lead_cents > 0").fetchall()]
    report = {"flood_total": 0, "wide_matches": 0, "ideal_matches": 0,
              "need_yield": 0, "funnels": {}}
    for funnel, total in c.execute(
            "SELECT funnel, COUNT(*) FROM si_intake_event GROUP BY funnel").fetchall():
        # strict-threshold matches (ideal) vs wide (any demand niche)
        leads = c.execute(
            "SELECT id, email, niche, metro FROM si_intake_event "
            "WHERE funnel=? ORDER BY id DESC LIMIT ?", (funnel, max_per_funnel)).fetchall()
        ideal = wide = 0
        for lid, email, niche, metro in leads:
            lead = {"lead_id": lid, "email": email,
                    "niche": FI.normalize_niche(niche), "metro": metro}
            buyers = LD.find_matching_buyers(lead)
            if buyers:
                wide += 1
                if niche in demand_niches:
                    ideal += 1
        need = wide - ideal
        report["flood_total"] += len(leads)
        report["wide_matches"] += wide
        report["ideal_matches"] += ideal
        report["need_yield"] += need
        report["funnels"][funnel] = {"leads": len(leads), "wide": wide, "ideal": ideal}
        if not dry_run:
            c.execute("INSERT INTO strategy_rolling_stones "
                      "(funnel,total_leads,wide_matches,ideal_matches,need_yield,ts) "
                      "VALUES (?,?,?,?,?,?)",
                      (funnel, len(leads), wide, ideal, need,
                       datetime.now(timezone.utc).isoformat()))
    if not dry_run:
        c.commit()
    c.close()
    report["yield_multiple_vs_ideal"] = round(
        report["wide_matches"] / max(report["ideal_matches"], 1), 2)
    return report


if __name__ == "__main__":
    print("🎸 ROLLING STONES (volume tsunami, dry-run):")
    print(run(dry_run=True))
