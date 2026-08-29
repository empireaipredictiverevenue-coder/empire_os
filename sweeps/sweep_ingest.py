#!/usr/bin/env python3
"""
Empire OS — Multi-Niche Market Sweep Ingestor (sweep_ingest.py)
==============================================================
Ingests a Phase-1 market sweep JSON (the 8-metro leak-recovery model)
into the revenue loop:

  1. crm_leads  (local SQLite)  — dedup by lead_uid = sweep id
  2. Supabase    (crm_leads mirror) — if configured
  3. outreach queue (lane_leads / crm_lead_tags) — status='raw',
     tagged 'sweep:<metro>:<niche>', ready for outbound engine

Sweep JSON shape (top-level):
  { "phase":1, "timestamp":..., "summary":{...},
    "metros":[ { "metro":..., "total_companies":...,
                 "whale_companies":[ {id,name,metro,niche,fleet_size,
                   daily_leak,annual_leak,recovery_potential,ceo_name,
                   phone,email,website,efficiency_score,ai_adoption,
                   tech_stack,confidence}, ... ] }, ... ] }

Run:
  python3 sweep_ingest.py /path/to/sweep.json [--supabase] [--outreach]
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"


def _db():
    c = sqlite3.connect(DB, timeout=60)
    c.row_factory = sqlite3.Row
    return c


def _metro_state(metro: str) -> str:
    # "Phoenix, AZ" -> "AZ"
    if "," in metro:
        return metro.split(",")[-1].strip()
    return ""


def _flatten(sweep: dict) -> list:
    """Flatten metros[].whale_companies into a flat company list."""
    out = []
    for m in sweep.get("metros", []):
        metro = m.get("metro", "")
        for co in m.get("whale_companies", []):
            co = dict(co)
            co.setdefault("metro", metro)
            out.append(co)
    return out


def _whale_tier(fleet_size: int, recovery: float) -> str:
    if fleet_size >= 30 or recovery >= 3_000_000:
        return "whale"
    if fleet_size >= 20 or recovery >= 1_500_000:
        return "strike"
    return "standard"


def ingest_crm(companies: list, c: sqlite3.Connection) -> dict:
    n_new = n_upd = 0
    for co in companies:
        uid = co.get("id") or f"{co.get('metro')}__{co.get('name')}"
        metro = co.get("metro", "")
        niche = co.get("niche", "")
        name = co.get("name", "")
        fleet = int(co.get("fleet_size", 0) or 0)
        recovery = float(co.get("recovery_potential", 0) or 0)
        tier = _whale_tier(fleet, recovery)
        exists = c.execute("SELECT id FROM crm_leads WHERE lead_uid=?",
                           (uid,)).fetchone()
        cols = dict(
            source="market_sweep",
            business_name=name,
            contact_name=co.get("ceo_name", ""),
            email=co.get("email", ""),
            phone=co.get("phone", ""),
            metro=metro,
            niche=niche,
            website=co.get("website", ""),
            employee_count=fleet,
            fleet_size=fleet,
            revenue_est=int(co.get("annual_leak", 0) or 0),
            whale_tier=tier,
            enrichment_score=float(co.get("efficiency_score", 0) or 0),
            omega_score=float(co.get("confidence", 0) or 0) * 100,
            status="raw",
            tags_json=json.dumps([f"sweep:{metro}:{niche}", f"tier:{tier}"]),
            notes=json.dumps({
                "daily_leak": co.get("daily_leak"),
                "annual_leak": co.get("annual_leak"),
                "recovery_potential": recovery,
                "ai_adoption": co.get("ai_adoption"),
                "tech_stack": co.get("tech_stack"),
                "phase": 1,
            }),
        )
        if exists:
            sets = ", ".join(f"{k}=?" for k in cols)
            c.execute(f"UPDATE crm_leads SET {sets}, updated_at=? WHERE lead_uid=?",
                      list(cols.values()) + [datetime.now().isoformat(), uid])
            n_upd += 1
        else:
            keys = ["lead_uid"] + list(cols)
            vals = [uid] + list(cols.values())
            ph = ", ".join("?" for _ in keys)
            c.execute(f"INSERT INTO crm_leads ({', '.join(keys)}) VALUES ({ph})", vals)
            n_new += 1
    c.commit()
    return {"new": n_new, "updated": n_upd}


def sync_supabase(companies: list) -> dict:
    """Mirror to Supabase crm_leads if configured. Returns {pushed, error}."""
    try:
        from empire_os.sb import supabase
    except Exception as e:
        return {"pushed": 0, "error": f"no_supabase_module:{e}"}
    if supabase is None:
        return {"pushed": 0, "error": "supabase_not_configured"}
    pushed = 0
    for co in companies:
        uid = co.get("id")
        try:
            supabase.upsert("crm_leads", {
                "lead_uid": uid,
                "business_name": co.get("name"),
                "contact_name": co.get("ceo_name"),
                "email": co.get("email"),
                "phone": co.get("phone"),
                "metro": co.get("metro"),
                "niche": co.get("niche"),
                "website": co.get("website"),
                "fleet_size": int(co.get("fleet_size", 0) or 0),
                "revenue_est": int(co.get("annual_leak", 0) or 0),
                "whale_tier": _whale_tier(int(co.get("fleet_size", 0) or 0),
                                          float(co.get("recovery_potential", 0) or 0)),
                "source": "market_sweep",
            }).execute()
            pushed += 1
        except Exception as e:
            return {"pushed": pushed, "error": str(e)}
    return {"pushed": pushed, "error": None}


def queue_outreach(companies: list, c: sqlite3.Connection) -> int:
    """Tag WHALE/STRIKE leads for outbound. Writes to crm_lead_tags + marks."""
    n = 0
    for co in companies:
        uid = co.get("id")
        fleet = int(co.get("fleet_size", 0) or 0)
        recovery = float(co.get("recovery_potential", 0) or 0)
        tier = _whale_tier(fleet, recovery)
        if tier == "standard":
            continue
        row = c.execute("SELECT id FROM crm_leads WHERE lead_uid=?", (uid,)).fetchone()
        if not row:
            continue
        lid = row["id"]
        c.execute("INSERT OR IGNORE INTO crm_lead_tags (lead_id, tag) VALUES (?,?)",
                  (lid, f"outreach:{tier}"))
        c.execute("UPDATE crm_leads SET status='qualifying' WHERE id=?", (lid,))
        n += 1
    c.commit()
    return n


def main():
    if len(sys.argv) < 2:
        print("usage: sweep_ingest.py <sweep.json> [--supabase] [--outreach]")
        sys.exit(1)
    path = sys.argv[1]
    do_sb = "--supabase" in sys.argv
    do_out = "--outreach" in sys.argv or True  # default queue
    with open(path) as f:
        sweep = json.load(f)
    companies = _flatten(sweep)
    print(f"[sweep_ingest] flattened {len(companies)} companies from "
          f"{len(sweep.get('metros', []))} metros")
    c = _db()
    r = ingest_crm(companies, c)
    print(f"[sweep_ingest] crm_leads: +{r['new']} new, ~{r['updated']} updated")
    if do_out:
        q = queue_outreach(companies, c)
        print(f"[sweep_ingest] outreach queue: {q} whale/strike leads tagged")
    if do_sb:
        s = sync_supabase(companies)
        print(f"[sweep_ingest] supabase: {s['pushed']} pushed"
              + (f" (err: {s['error']})" if s['error'] else ""))
    c.close()
    print("[sweep_ingest] DONE")


if __name__ == "__main__":
    main()
