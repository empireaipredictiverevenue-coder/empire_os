#!/usr/bin/env python3
"""
Empire OS — Market Sweep Ingest Engine (sweep_ingest.py)
=======================================================
Ingests a full multi-niche / multi-metro market-sweep JSON into:
  1. local crm_leads (SQLite empire_os.db)
  2. Supabase prospects table (via empire_os.sb)
  3. outreach queue (outreach_tasks) for the SI Brain to action

Expected input JSON shape (per your sweep export):
{
  "phase": 1,
  "summary": { "metros_scanned": 8, "total_companies": 3856,
               "total_daily_leak": ..., "total_annual_leak": ..., ... },
  "metros": [
    {
      "metro": "Phoenix, AZ", ...,
      "whale_companies": [
        { "id","name","metro","niche","fleet_size","daily_leak",
          "annual_leak","recovery_potential","ceo_name","phone","email",
          "website","efficiency_score","ai_adoption","tech_stack","confidence" }, ...
      ]
    }, ...
  ]
}

Run:
  python3 sweep_ingest.py /path/to/sweep.json
"""

import sys
import json
import os
import sqlite3
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
EMPIRE_OS = "/root/empire_os"


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def _whale_tier(fleet_size: int, recovery: float) -> str:
    if fleet_size >= 30 or recovery >= 3_000_000:
        return "WHALE"
    if fleet_size >= 15 or recovery >= 1_000_000:
        return "STRIKE"
    return "standard"


def ensure_outreach_table(c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS outreach_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_uid TEXT,
            metro TEXT,
            niche TEXT,
            business_name TEXT,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            channel TEXT DEFAULT 'email',
            status TEXT DEFAULT 'queued',
            priority INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
        )
    """)


def upsert_lead(c, comp: dict, metro: str) -> str:
    uid = comp.get("id") or f"{metro}__{comp.get('name','')}"
    name = comp.get("name", "")
    niche = comp.get("niche", "")
    fleet = int(comp.get("fleet_size", 0) or 0)
    recovery = float(comp.get("recovery_potential", 0) or 0)
    tier = _whale_tier(fleet, recovery)
    email = (comp.get("email") or "").strip().lower()
    phone = (comp.get("phone") or "").strip()
    website = (comp.get("website") or "").strip()
    ceo = comp.get("ceo_name", "")
    eff = int(comp.get("efficiency_score", 0) or 0)
    conf = float(comp.get("confidence", 0) or 0)

    c.execute("""
        INSERT INTO crm_leads
          (lead_uid, source, business_name, contact_name, email, phone,
           metro, niche, website, employee_count, revenue_est,
           omega_score, omega_tier, enrichment_score, status,
           fleet_size, whale_tier, tags_json, notes)
        VALUES (?, 'market_sweep', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'raw',
                ?, ?, ?, ?)
        ON CONFLICT(lead_uid) DO UPDATE SET
          business_name=excluded.business_name,
          contact_name=excluded.contact_name,
          email=excluded.email,
          phone=excluded.phone,
          metro=excluded.metro,
          niche=excluded.niche,
          website=excluded.website,
          fleet_size=excluded.fleet_size,
          whale_tier=excluded.whale_tier,
          notes=excluded.notes,
          updated_at=strftime('%Y-%m-%dT%H:%M:%f','now')
    """, (
        uid, name, ceo, email, phone, metro, niche, website,
        fleet, int(recovery),
        conf * 100, tier, eff,
        fleet, tier,
        json.dumps(["market_sweep", niche, tier]),
        f"fleet={fleet} recovery={recovery:.0f} eff={eff} ai={comp.get('ai_adoption','')}",
    ))
    return uid


def queue_outreach(c, uid: str, comp: dict, metro: str):
    c.execute("""
        INSERT INTO outreach_tasks
          (lead_uid, metro, niche, business_name, contact_name, email, phone, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid, metro, comp.get("niche", ""), comp.get("name", ""),
        comp.get("ceo_name", ""), (comp.get("email") or "").strip().lower(),
        (comp.get("phone") or "").strip(),
        2 if comp.get("whale_tier", "") == "WHALE" else 1,
    ))


def push_supabase(rows: list):
    """Push ingested leads to Supabase. Returns (ok, n, err)."""
    try:
        import sys as _s
        _s.path.insert(0, EMPIRE_OS)
        from empire_os import sb
        if rows:
            sb.table("prospects").upsert(rows, on_conflict="id").execute()
        return True, len(rows), None
    except Exception as e:
        return False, 0, str(e)


def ingest(path: str):
    with open(path) as f:
        data = json.load(f)

    c = _db()
    ensure_outreach_table(c)

    rows = []
    total = 0
    whales = 0
    metros_seen = set()
    for metro_block in data.get("metros", []):
        metro = metro_block.get("metro", "")
        metros_seen.add(metro)
        for comp in metro_block.get("whale_companies", []):
            uid = upsert_lead(c, comp, metro)
            queue_outreach(c, uid, comp, metro)
            tier = comp.get("whale_tier") or _whale_tier(
                int(comp.get("fleet_size", 0) or 0),
                float(comp.get("recovery_potential", 0) or 0))
            if tier == "WHALE":
                whales += 1
            rows.append({
                "id": uid,
                "business_name": comp.get("name", ""),
                "metro": metro,
                "niche": comp.get("niche", ""),
                "contact_name": comp.get("ceo_name", ""),
                "email": (comp.get("email") or "").strip().lower(),
                "phone": (comp.get("phone") or "").strip(),
                "website": (comp.get("website") or "").strip(),
                "fleet_size": int(comp.get("fleet_size", 0) or 0),
                "recovery_potential": float(comp.get("recovery_potential", 0) or 0),
                "whale_tier": tier,
                "source": "market_sweep",
            })
            total += 1
    c.commit()

    # supabase push (best-effort)
    sb_ok, sb_n, sb_err = push_supabase(rows)

    c.close()
    return {
        "total": total,
        "whales": whales,
        "metros": len(metros_seen),
        "supabase": {"ok": sb_ok, "n": sb_n, "err": sb_err},
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: sweep_ingest.py /path/to/sweep.json")
        sys.exit(1)
    r = ingest(sys.argv[1])
    print(json.dumps(r, indent=2))
