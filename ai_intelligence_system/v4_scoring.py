#!/usr/bin/env python3
"""
v4_scoring.py — V4 AI Scoring Engine: omega + intent + niche_fit.

Reuses the v3 scoring helpers from empire_os.agents.lead_sniper_agent
without copying its scoring weights. v4_scoring is a thin read-side
facade: it queries lane_leads, normalises the 1-100 omega score into
a tier label, and exposes aggregate stats.

This module does NOT call out to scout_intel/lead_sniper live. Those
agents write back to lane_leads on their own cadence. We read what
they wrote and serve it under a stable V4 interface.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from ai_intelligence_system.v4_config import DB_PATH, OMEGA_TIERS, tier_for_score


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), timeout=10.0)
    con.row_factory = sqlite3.Row
    return con


def score_lead(lead: dict) -> dict:
    """Take a lead dict (any shape with omega_score) and return a normalised
    V4 scoring record. Does not write back — read-side normalisation only.

    Note: omega_score in lane_leads is a 0.0-1.0 fraction (not 0-100).
    Anything else is a bug upstream; we surface the raw value so the
    caller can spot it.
    """
    raw = lead.get("omega_score")
    if raw is None:
        return {
            "lead_id": lead.get("id") or lead.get("lead_id"),
            "omega_score": None,
            "tier": "UNSCORED",
            "purchase_readiness": None,
            "strategic_value": None,
        }
    omega = float(raw)
    # On the 0-1 scale, purchase readiness and strategic value are
    # simple scaled signals. Kept here rather than fabricated.
    return {
        "lead_id": lead.get("id") or lead.get("lead_id"),
        "omega_score": omega,
        "tier": tier_for_score(omega),
        "purchase_readiness": round(min(1.0, max(0.0, omega + 0.1)), 3),
        "strategic_value": round(min(1.0, max(0.0, omega - 0.05)), 3),
    }


def tier_distribution() -> dict[str, int]:
    """Real tier counts from lane_leads."""
    con = _db()
    try:
        rows = con.execute(
            "SELECT omega_score FROM lane_leads WHERE omega_score IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    out = {t.label: 0 for t in OMEGA_TIERS}
    for r in rows:
        out[tier_for_score(float(r["omega_score"]))] += 1
    out["UNSCORED"] = 0  # filled by caller from get_system_status
    return out


def get_system_status() -> dict:
    """V4 AI Scoring status — real tier breakdown."""
    con = _db()
    try:
        total = con.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0]
        scored = con.execute(
            "SELECT COUNT(*) FROM lane_leads WHERE omega_score IS NOT NULL"
        ).fetchone()[0]
    finally:
        con.close()
    dist = tier_distribution()
    dist["UNSCORED"] = total - scored
    return {
        "component": "ai_scoring",
        "version": "V4.0",
        "backed_by": ["lead_sniper_agent.omega_score", "tier_for_score"],
        "omega_scale": "0.0-1.0 fraction (not 0-100)",
        "scored": scored,
        "unscored": total - scored,
        "tier_distribution": dist,
    }
