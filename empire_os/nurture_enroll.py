#!/usr/bin/env python3
"""nurture_enroll — Auto-enroll cold prospects in email nurture sequences.

When a sales_agent run touches a new cold prospect, enroll them in
the appropriate email sequence (3-step cold/warm). Bridges the gap
between the AI sales loop and the humanized 3-touch nurture.

Idempotent: skips prospects already enrolled in prospect_sequences.

Cadence: every 6h (matches the typical AI sales cycle).
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "nurture_enroll.jsonl"

DEFAULT_BATCH = int(os.getenv("ENROLL_BATCH", "200"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def get_default_sequence(c: sqlite3.Connection) -> Optional[int]:
    """Get the first active email_sequences row id."""
    row = c.execute(
        "SELECT id FROM email_sequences WHERE active=1 ORDER BY id ASC LIMIT 1"
    ).fetchone()
    return row["id"] if row else None


def get_unenrolled_cold(c: sqlite3.Connection, batch: int) -> list:
    """Cold prospects with email not yet in prospect_sequences."""
    rows = c.execute("""
        SELECT p.prospect_id, p.email, p.niche
        FROM si_buyer_outreach p
        WHERE p.active = 1
          AND p.email IS NOT NULL AND p.email != ''
          AND p.email NOT LIKE 'dc-%' AND p.email NOT LIKE '%@v.co'
          AND NOT EXISTS (
              SELECT 1 FROM prospect_sequences ps
              WHERE ps.prospect_id = p.prospect_id AND ps.status = 'active'
          )
        ORDER BY p.payout_per_lead DESC NULLS LAST, p.last_touch_at DESC
        LIMIT ?
    """, (batch,)).fetchall()
    return [dict(r) for r in rows]


def enroll(c: sqlite3.Connection, prospect_id: str, sequence_id: int) -> None:
    """Enroll prospect in the given sequence (status=active, step=0)."""
    c.execute("""
        INSERT INTO prospect_sequences
            (prospect_id, sequence_id, current_step, status, started_at, variant, updated_at)
        VALUES (?, ?, 0, 'active', datetime('now'), 'cold_default', datetime('now'))
    """, (prospect_id, sequence_id))
    c.commit()


def run(batch: int = DEFAULT_BATCH) -> dict:
    summary = {
        "ts": _now(),
        "batch": batch,
        "enrolled": 0,
        "skipped": 0,
        "no_sequence": False,
    }
    c = db()
    try:
        seq_id = get_default_sequence(c)
        if not seq_id:
            summary["no_sequence"] = True
            _log({"ts": _now(), "event": "no_active_sequence"})
            return summary

        prospects = get_unenrolled_cold(c, batch)
        for p in prospects:
            try:
                enroll(c, p["prospect_id"], seq_id)
                summary["enrolled"] += 1
            except Exception as e:
                summary["skipped"] += 1
                _log({"ts": _now(), "event": "enroll_error",
                      "prospect_id": p["prospect_id"],
                      "error": str(e)[:200]})
        _log({"ts": _now(), "event": "tick_end", "summary": summary})
    finally:
        c.close()
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))