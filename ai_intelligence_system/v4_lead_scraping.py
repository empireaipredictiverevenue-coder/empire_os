#!/usr/bin/env python3
"""
v4_lead_scraping.py — V4 Lead Scraping Engine: facade over v3 scrapers + lane_leads.

Backed by:
  - empire_os/agents/crawler_agent.py (NYC permits + county records)
  - empire_os/agents/b2b_scraper_agent.py (B2B firms)
  - lane_leads table (the merged result both scrapers write to)

Exposes a query interface over the existing lane_leads corpus so any V4
caller can ask 'what leads do we have for niche X in metro Y' without
duplicating the v3 scraping logic.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from ai_intelligence_system.v4_config import DB_PATH, LANE_LEADS_LIMIT


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), timeout=10.0)
    con.row_factory = sqlite3.Row
    return con


def query_lane_leads(
    *,
    niche: Optional[str] = None,
    metro: Optional[str] = None,
    min_omega: Optional[int] = None,
    limit: int = LANE_LEADS_LIMIT,
) -> list[dict]:
    """Read from the live lane_leads table with optional filters.

    Returns real rows. Empty list if no matches — not fake data.

    Schema note: lane_leads has lead_ref, tort_key, omega_score, omega_tier,
    zip_code, source, name, phone — but NOT niche or metro. Those columns
    exist on crm_leads. Filters for missing columns are dropped (not raised)
    so a single call works across all lead sources.
    """
    con = _db()
    try:
        # Discover actual columns at query time.
        cols = {r[1] for r in con.execute("PRAGMA table_info(lane_leads)").fetchall()}
        sql = "SELECT * FROM lane_leads WHERE 1=1"
        params: list = []
        if niche and "niche" in cols:
            sql += " AND niche = ?"
            params.append(niche)
        if metro and "metro" in cols:
            sql += " AND metro = ?"
            params.append(metro)
        if min_omega is not None and "omega_score" in cols:
            sql += " AND omega_score >= ?"
            params.append(min_omega)
        sql += " ORDER BY omega_score DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cur = con.execute(sql, params)
        out_cols = [d[0] for d in cur.description]
        return [dict(zip(out_cols, row)) for row in cur.fetchall()]
    finally:
        con.close()


# Lead surface catalog. The Empire DB has multiple lead-shaped tables
# (lane_leads, crm_leads, si_ppl_leads, si_firm_candidates, etc). Expose
# them as one queryable surface so V4 callers can ask 'all leads' without
# having to know the schema.
LEAD_SOURCES = ("lane_leads", "crm_leads", "si_ppl_leads", "si_firm_candidates")


def _table_row_count(table: str) -> int:
    con = _db()
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()


def lead_source_counts() -> dict[str, int]:
    """Real counts across every lead-shaped table in the DB."""
    return {src: _table_row_count(src) for src in LEAD_SOURCES}


def distinct_niches(limit: int = 50) -> list[tuple[str, int]]:
    """Distinct (niche, count) pairs from lane_leads, ordered by volume."""
    con = _db()
    try:
        rows = con.execute(
            "SELECT niche, COUNT(*) as c FROM lane_leads "
            "WHERE niche IS NOT NULL AND niche != '' "
            "GROUP BY niche ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["niche"], r["c"]) for r in rows]
    finally:
        con.close()


def distinct_metros(limit: int = 50) -> list[tuple[str, int]]:
    """Distinct (metro, count) pairs from lane_leads."""
    con = _db()
    try:
        rows = con.execute(
            "SELECT metro, COUNT(*) as c FROM lane_leads "
            "WHERE metro IS NOT NULL AND metro != '' "
            "GROUP BY metro ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["metro"], r["c"]) for r in rows]
    finally:
        con.close()


def get_system_status() -> dict:
    """V4 Lead Scraping status — real counts only.

    Surfaces every lead-shaped table, not just lane_leads. The Empire
    pipeline has multiple lead sources (crm_leads, si_ppl_leads, etc)
    and V4 callers shouldn't have to know which one to ask.
    """
    source_counts = lead_source_counts()
    con = _db()
    try:
        scored = con.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE omega_score IS NOT NULL"
        ).fetchone()[0]
        unconsented = con.execute(
            "SELECT COUNT(*) FROM lane_leads "
            "WHERE source NOT IN (SELECT source FROM si_prospect_consent)"
        ).fetchone()[0]
    finally:
        con.close()
    lane_leads_total = source_counts["lane_leads"]
    return {
        "component": "lead_scraping",
        "version": "V4.0",
        "backed_by": ["crawler_agent", "b2b_scraper_agent", "lane_leads",
                      "crm_leads", "si_ppl_leads", "si_firm_candidates"],
        "lead_source_counts": source_counts,
        "lane_leads_total": lane_leads_total,
        "lane_leads_scored": scored,
        "lane_leads_unconsented": unconsented,
        "scoring_coverage": (scored / lane_leads_total) if lane_leads_total else 0.0,
    }
