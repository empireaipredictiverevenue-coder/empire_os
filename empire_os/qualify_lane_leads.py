#!/usr/bin/env python3
"""qualify_lane_leads.py — pre-qualify existing lane_leads with lead_qualifier.

Reads lane_leads, scores each via LeadQualifier, writes HOT/WARM/COOL into
pre_qualified_leads table, updates omega_tier. Reports tier breakdown.
"""
import sqlite3, json
from pathlib import Path
import sys as _s
_s.path.insert(0, "/root/empire_os")
from empire_os.lead_qualifier import Qualifier, QLead

DB = "/root/empire_os/empire_os.db"


def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM lane_leads").fetchall()
    print(f"loaded {len(rows)} lane_leads")
    q = Qualifier(target_niche="", target_geo="")
    out = q.qualify([dict(r) for r in rows])
    m = out["metrics"]
    print(f"received={m['received']} rejected={m['rejected']} by_tier={m['by_tier']}")
    # persist
    conn.execute("""CREATE TABLE IF NOT EXISTS pre_qualified_leads (
        lead_ref TEXT PRIMARY KEY, name TEXT, phone TEXT, tier TEXT,
        score INTEGER, niche TEXT, source TEXT, created_at TEXT)""")
    for tier_key in ("hot", "warm", "cool"):
        for d in out[tier_key]:
            conn.execute(
                "INSERT OR REPLACE INTO pre_qualified_leads (lead_ref,name,phone,tier,score,niche,source,created_at) "
                "VALUES (?,?,?,?,?,?,?,datetime('now'))",
                (d.get("lead_ref") or d.get("name"), d.get("name"), d.get("phone"),
                 tier_key.upper(), d.get("score"), d.get("niche"), d.get("source")))
    conn.commit()
    conn.close()
    print(f"HOT={len(out['hot'])} WARM={len(out['warm'])} COOL={len(out['cool'])} -> pre_qualified_leads")


if __name__ == "__main__":
    main()
