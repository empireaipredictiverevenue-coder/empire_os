#!/usr/bin/env python3
"""Empire OS — lead scoring (prioritize outbound by close-probability).

Derives a 0-100 lead_score + tier (hot/warm/cold) from data the sweep/enrich
already produces (omega_score, icp_fit_score, employee_count, revenue_est,
state, niche). No external model — deterministic, explainable, KISS.

Run: /root/venv/bin/python3 empire_os/lead_scoring.py   # scores + writes back
"""
import sqlite3, sys, json
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"

# niches with proven buyer demand (seated lanes exist) -> higher priority
HOT_NICHES = {
    "residential_roofing", "roof_repair", "commercial_roofing", "hvac",
    "plumbing", "water_damage", "fire_damage", "mold_remediation",
    "storm_damage", "sewage_cleanup", "electrical", "disaster_restoration",
    "legal_services", "mass_tort", "camp_lejeune", "roundup", "paraquat",
    "afff", "zantac", "dental", "accounting", "tax_prep", "real_estate",
    "insurance", "mortgage", "debt_relief", "pt_rehab", "vision",
    "addiction", "weight_loss", "hormone_therapy", "investing",
}


def score_lead(row: dict) -> tuple[int, str]:
    s = 0
    # signals the sweep/enrichment actually populate today
    s += min(int(float(row.get("omega_score") or 0)), 45)      # 0-45
    s += min(int(float(row.get("icp_fit_score") or 0)), 30)    # 0-30
    # firmographic (filled by later enrichment pass; 0 today is neutral, not penalizing)
    ec = int(row.get("employee_count") or 0)
    s += 10 if ec >= 50 else 5 if ec >= 10 else 0
    rev = (row.get("revenue_est") or "").replace("$", "").replace(",", "")
    try:
        s += 10 if float(rev) >= 1_000_000 else 5 if float(rev) >= 100_000 else 0
    except ValueError:
        pass
    # niche demand (proven seated-lane demand)
    if (row.get("niche") or "") in HOT_NICHES:
        s += 15
    s = max(0, min(100, s))
    tier = "hot" if s >= 60 else "warm" if s >= 30 else "cold"
    return s, tier


def run(write: bool = True) -> dict:
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    # add columns if missing (idempotent)
    for col in ("lead_score INTEGER DEFAULT 0", "lead_tier TEXT DEFAULT 'cold'"):
        try:
            c.execute(f"ALTER TABLE crm_leads ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # already exists
    rows = c.execute(
        "SELECT id, omega_score, icp_fit_score, enrichment_score, "
        "employee_count, revenue_est, niche FROM crm_leads"
    ).fetchall()
    counts = {"hot": 0, "warm": 0, "cold": 0}
    updated = 0
    for r in rows:
        sc, tier = score_lead(dict(r))
        counts[tier] += 1
        if write:
            c.execute(
                "UPDATE crm_leads SET lead_score=?, lead_tier=? WHERE id=?",
                (sc, tier, r["id"]),
            )
            updated += 1
    if write:
        c.commit()
    c.close()
    return {"scored": updated, "tiers": counts,
            "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    res = run(write=True)
    print(json.dumps(res, indent=2))
    print(f"\nScored {res['scored']} leads | "
          f"hot={res['tiers']['hot']} warm={res['tiers']['warm']} cold={res['tiers']['cold']}")
