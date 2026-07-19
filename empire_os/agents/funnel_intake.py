#!/usr/bin/env python3
"""
funnel_intake.py — UNIFIED LEAD INTAKE from ALL funnels.

Every lead-generating surface in Empire OS flows through here:
  - scrape      : si_buyer_outreach (29,731 real prospects, scraped/enriched)
  - aeo         : AEO page form submissions / CTA clicks (/srv/aeo)
  - outreach    : founder_outreach replies / paid subscribers (si_subscription)
  - cortex      : Empire Cortex Scanner pattern signals (niche demand)
  - referral    : affiliate slug referrals

All events land in `si_intake_event` (one table, one source of truth) so the
marketing strategies (rank / rent / rolling-stones) can score and route from a
single view instead of 5 fragmented tables.

Design: append-only event log. No dedup-on-write (cheap); dedup at read time.
"""
from __future__ import annotations
import json, os, sqlite3, sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")


def _db():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS si_intake_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        funnel TEXT, source TEXT, niche TEXT, metro TEXT,
        email TEXT, raw TEXT, ts TEXT)""")
    return c


def ingest(funnel: str, source: str, niche: str = "", metro: str = "",
           email: str = "", raw: str = "") -> int:
    """Single ingest API used by every funnel. Returns event id."""
    c = _db()
    ts = datetime.now(timezone.utc).isoformat()
    cur = c.execute(
        "INSERT INTO si_intake_event (funnel,source,niche,metro,email,raw,ts) "
        "VALUES (?,?,?,?,?,?,?)",
        (funnel, source, niche, metro, email, raw, ts))
    c.commit(); rid = cur.lastrowid; c.close()
    return rid


def seed_from_existing(limit: int = 0) -> dict:
    """Backfill si_intake_event from existing live tables (one-time / re-runnable)."""
    c = _db()
    out = {}
    # scrape funnel <- si_buyer_outreach
    try:
        rows = c.execute(
            "SELECT email,niche,metro FROM si_buyer_outreach "
            + ("LIMIT %d" % limit if limit else "")).fetchall()
        n = 0
        for email, niche, metro in rows:
            c.execute("INSERT INTO si_intake_event (funnel,source,niche,metro,email,ts) "
                      "VALUES ('scrape','si_buyer_outreach',?,?,?,?)",
                      (niche or "", metro or "", email or "",
                       datetime.now(timezone.utc).isoformat()))
            n += 1
        c.commit(); out["scrape"] = n
    except Exception as e:
        out["scrape_err"] = str(e)[:120]
    # paid funnel <- si_subscription
    try:
        rows = c.execute(
            "SELECT niche,source,tenant_id FROM si_subscription").fetchall()
        n = 0
        for niche, source, tid in rows:
            c.execute("INSERT INTO si_intake_event (funnel,source,niche,email,raw,ts) "
                      "VALUES ('outreach','si_subscription',?,?,?,?)",
                      (niche or "", tid or "", source or "",
                       datetime.now(timezone.utc).isoformat()))
            n += 1
        c.commit(); out["outreach"] = n
    except Exception as e:
        out["outreach_err"] = str(e)[:120]
    c.close()
    return out


def funnel_counts() -> dict:
    c = _db()
    rows = c.execute(
        "SELECT funnel, COUNT(*) FROM si_intake_event GROUP BY funnel").fetchall()
    c.close()
    return {f: n for f, n in rows}


def normalize_niche(niche: str) -> str:
    """Map raw lead niches -> real lane families that exist in `lanes`.

    Every family below has 11 metro lanes. We seat a demo buyer in each so
    ALL lead types bill. Unknown niches default to roof_repair (most-seated).
    """
    if not niche:
        return "roof_repair"
    n = niche.lower().strip().replace("_", " ")
    # explicit lane families pass through
    FAM = ("roof_repair", "residential_roofing", "commercial_roofing",
           "weight_loss", "hvac", "plumbing", "legal_services", "insurance",
           "debt_relief", "managed_it", "staffing", "addiction", "dental",
           "real_estate", "consulting", "software_dev", "web_dev", "cloud",
           "cybersecurity", "data_analytics", "marketing", "accounting",
           "tax_prep", "investing", "mortgage", "vision", "pt_rehab",
           "electrical", "storm_damage", "water_damage", "fire_damage",
           "mold_remediation", "sewage_cleanup", "disaster_restoration",
           "ai_automation", "hormone_therapy", "ozempic", "roundup",
           "paraquat", "zantac", "afff", "camp_lejeune")
    if n in FAM:
        return n
    # roofing + exterior home services
    if any(k in n for k in ("roof", "gut", "shing", "solar", "window",
                            "fenc", "exter", "tree", "restoration", "storm",
                            "water", "fire", "mold", "sewage", "disaster")):
        return "roof_repair"
    # HVAC / plumbing / electrical
    if any(k in n for k in ("hvac", "plumb", "electr", "heat")):
        return "hvac" if "hvac" in n else ("plumbing" if "plumb" in n else "electrical")
    # mass tort / legal / class action / pharma liability
    if any(k in n for k in ("tort", "class action", "pharma", "paraquat",
                            "roundup", "zantac", "afff", "lejeune", "consumer product")):
        return "legal_services"
    if "legal" in n or "law" in n or "lawyer" in n or "attorney" in n:
        return "legal_services"
    # insurance (auto/life/medicare/final expense/medical alert)
    if any(k in n for k in ("insurance", "medicare", "medic", "health",
                            "well", "fit", "weight", "addiction", "mental",
                            "nursing", "assisted", "home health", "clinic",
                            "rehab", "dental", "vision", "hormone", "ozempic")):
        return "weight_loss" if "weight" in n or "ozempic" in n or "hormone" in n else "addiction"
    # debt / finance
    if any(k in n for k in ("debt", "loan", "mortgage", "broker", "invest",
                            "tax", "account", "finance")):
        return "debt_relief" if "debt" in n else "mortgage"
    # staffing / HR / managed IT / software
    if any(k in n for k in ("staff", "hr", "managed it", "it ", "software",
                            "web", "cloud", "cyber", "data", "consult", "market", "ai ")):
        return "staffing" if "staff" in n or "hr" in n else "managed_it"
    # real estate
    if "real estate" in n or "property" in n:
        return "real_estate"
    # everything else -> roof_repair (most-seated) so it gets a billing shot
    return "roof_repair"


def niche_counts() -> dict:
    """Count events per niche — feeds strategy_rank + rolling_stones."""
    c = _db()
    rows = c.execute(
        "SELECT niche, COUNT(*) FROM si_intake_event WHERE niche != '' "
        "GROUP BY niche ORDER BY COUNT(*) DESC").fetchall()
    c.close()
    return {n: k for n, k in rows}


if __name__ == "__main__":
    print("🌊 funnel_intake: seeding from existing tables...")
    print(seed_from_existing())
    print("funnel_counts:", funnel_counts())
