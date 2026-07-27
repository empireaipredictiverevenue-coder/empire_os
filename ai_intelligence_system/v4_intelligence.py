#!/usr/bin/env python3
"""
v4_intelligence.py — V4 Intelligence Core: thin facade over the v3 cortex.

Backed by:
  - empire_os/agents/cortex_engine.py (predictive revenue + 4 pillars)
  - empire_os/cortex_ai_assistant.py (LLM-backed advisor)
  - /root/feedback/cortex_report.json (live snapshot written by cortex_engine)

This module does NOT replace the cortex. It exposes its outputs to any agent
through one stable interface, so v3 and v4 callers share the same data.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from ai_intelligence_system.v4_config import DB_PATH, FEEDBACK_DIR


CORTEX_REPORT = FEEDBACK_DIR / "cortex_report.json"


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), timeout=10.0)
    con.row_factory = sqlite3.Row
    return con


def _safe_load(path: Path) -> Optional[dict]:
    """Load JSON file or return None. Never raises on missing/corrupt."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_cortex_snapshot() -> dict:
    """Return the latest cortex snapshot the running engine wrote, or a
    minimal honest payload if cortex_engine has not run yet.

    The fallback is intentionally small. It tells the caller 'no data yet',
    not made-up numbers.
    """
    report = _safe_load(CORTEX_REPORT)
    if report:
        return {
            "source": "cortex_report.json",
            "written_at": report.get("written_at"),
            "pillars": report.get("pillars", {}),
            "raw_keys": sorted(report.keys()),
        }
    return {
        "source": "missing",
        "written_at": None,
        "pillars": {},
        "raw_keys": [],
        "note": "cortex_engine has not written /root/feedback/cortex_report.json yet",
    }


def live_funnel_counts() -> dict:
    """Real counts from the live DB. No fabrication — returns 0 if table empty."""
    con = _db()
    try:
        return {
            "lanes": con.execute("SELECT COUNT(*) FROM lanes").fetchone()[0],
            "tenants": con.execute("SELECT COUNT(*) FROM si_tenant").fetchone()[0],
            "subscriptions": con.execute("SELECT COUNT(*) FROM si_subscription").fetchone()[0],
            "lane_leads": con.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0],
            "delivered_leads": con.execute("SELECT COUNT(*) FROM delivered_leads").fetchone()[0],
            "settlements": con.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0],
            "evaluation_ledger_rows": con.execute("SELECT COUNT(*) FROM evaluation_ledger").fetchone()[0],
        }
    finally:
        con.close()


def get_system_status() -> dict:
    """Combined V4 Intelligence Core status. Real data, not promises."""
    snapshot = get_cortex_snapshot()
    counts = live_funnel_counts()
    return {
        "component": "intelligence_core",
        "version": "V4.0",
        "backed_by": ["cortex_engine.pillar_*", "cortex_report.json", "live_db_counts"],
        "cortex_available": snapshot["source"] != "missing",
        "cortex_written_at": snapshot["written_at"],
        "live_counts": counts,
    }
