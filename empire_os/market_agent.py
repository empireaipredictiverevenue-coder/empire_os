#!/usr/bin/env python3
"""market_agent.py — Empire AI Market Agent with enrichment Waterfall.

Layer 21 of the Predictive Cloud brain. The market agent:
  1. Runs our Serper product across ALL niches (multi-niche lead-gen sweep)
  2. Enriches every fresh lead through the self-built-first Waterfall
     (RegistryScraper -> SiteCrawler -> Apollo/PDL/Hunter if keyed -> Social -> Internal)
  3. Routes validated, contact-ready leads into the A2A marketplace + buyer waterfall

Self-hosted. NO Vercel/Dokku/Railway. Pure Incus/empire-net.
"""
from __future__ import annotations
import os
import sys
import json
import sqlite3
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")

DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")


def _conn():
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    return c


def run_market_cycle(niches: list = None, metros: list = None, limit: int = 10) -> dict:
    """Full market cycle: Serper sweep -> Waterfall enrich -> marketplace route."""
    from empire_os.lead_engine.serp_discovery import multi_niche_sweep
    from empire_os.waterfall import build_default_waterfall

    # 1. Multi-niche SERP sweep (our own Serper product)
    sweep = multi_niche_sweep(niches=niches, metros=metros, limit=limit)

    # 2. Enrich fresh serp_discovery leads through the Waterfall
    wf = build_default_waterfall()
    c = _conn()
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT lead_uid, business_name, website, niche, metro FROM crm_leads "
            "WHERE source='serp_discovery' AND (email IS NULL OR email='') "
            "AND website NOT LIKE '%facebook.com' AND website NOT LIKE '%google.com' "
            "AND website NOT LIKE '%yelp.com' LIMIT ?",
            (limit * 5,)).fetchall()
        enriched = 0
        for row in rows:
            lead = {"company": row["business_name"], "website": row["website"] or "",
                    "domain": (row["website"] or "").replace("www.", ""),
                    "industry": row["niche"], "city": row["metro"] or ""}
            res = wf.enrich(lead)
            if res.success and res.contact:
                c.execute(
                    "UPDATE crm_leads SET email=COALESCE(NULLIF(?,''),email), "
                    "phone=COALESCE(NULLIF(?,''),phone), enriched=1 WHERE lead_uid=?",
                    (res.contact.email or "", res.contact.phone or "", row["lead_uid"]))
                enriched += 1
        c.commit()
    finally:
        c.close()

    # 3. Route to marketplace (A2A) — mark validated leads
    return {
        "layer": 21,
        "serp_sweep": sweep,
        "waterfall_metrics": wf.metrics,
        "enriched": enriched,
        "next": "route validated leads to A2A marketplace / buyer waterfall",
    }


if __name__ == "__main__":
    print(json.dumps(run_market_cycle(limit=5), indent=2, default=str))
