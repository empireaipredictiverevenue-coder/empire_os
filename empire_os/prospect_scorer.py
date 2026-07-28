#!/usr/bin/env python3
"""prospect_scorer — Pre-filter 30k cold prospects for nurture priority.

Score 0-100 from signals:
  - has email                  +20
  - has source                  +10
  - payout_per_lead > $50       +20
  - payout_per_lead > $100      +10 (bonus)
  - payout_per_lead > $500      +10 (bonus)
  - last_touch_at < 7 days      +15
  - last_touch_at < 30 days     +10
  - score (CRM) > 50            +5
  - score > 80                  +5 (bonus)

Threshold: 30 (top ~20% based on current distribution).
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "prospect_scorer.jsonl"

THRESHOLD = int(os.getenv("SCORE_THRESHOLD", "30"))
DEFAULT_BATCH = int(os.getenv("SCORE_BATCH", "1000"))


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


def score_prospect(p: dict) -> int:
    s = 0
    if p.get("email") and "@" in p["email"]:
        s += 20
    if p.get("source"):
        s += 10
    ppl = float(p.get("payout_per_lead") or 0)
    if ppl >= 50: s += 20
    if ppl >= 100: s += 10
    if ppl >= 500: s += 10
    last_touch = p.get("last_touch_at", "")
    if last_touch:
        try:
            ts = datetime.fromisoformat(last_touch.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age < timedelta(days=7): s += 15
            elif age < timedelta(days=30): s += 10
        except Exception:
            pass
    score = int(p.get("score") or 0)
    if score > 50: s += 5
    if score > 80: s += 5
    return min(100, s)


def ensure_score_col(c: sqlite3.Connection):
    """Add score column if missing (idempotent)."""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(si_buyer_outreach)")}
    if "score" not in cols:
        c.execute("ALTER TABLE si_buyer_outreach ADD COLUMN score INTEGER DEFAULT 0")
        c.commit()


def score_unscored(c: sqlite3.Connection, batch: int) -> tuple:
    """Score the next batch of unscored cold prospects."""
    rows = c.execute("""
        SELECT prospect_id, email, source, payout_per_lead,
               last_touch_at, score
        FROM si_buyer_outreach
        WHERE active = 1
          AND score IS NULL OR score = 0
          AND email IS NOT NULL AND email != ''
        LIMIT ?
    """, (batch,)).fetchall()
    scored = 0
    for r in rows:
        s = score_prospect(dict(r))
        c.execute(
            "UPDATE si_buyer_outreach SET score = ? WHERE prospect_id = ?",
            (s, r["prospect_id"]),
        )
        scored += 1
    c.commit()
    return scored, len(rows)


def mark_nurture_ready(c: sqlite3.Connection) -> int:
    """Mark prospects with score >= threshold for nurture enrollment."""
    cur = c.execute(
        "UPDATE si_buyer_outreach SET reply_state = 'nurture_ready' "
        "WHERE score >= ? AND active = 1 AND reply_state != 'contacted' "
        "AND reply_state != 'converted'",
        (THRESHOLD,),
    )
    c.commit()
    return cur.rowcount


def run(batch: int = DEFAULT_BATCH) -> dict:
    summary = {
        "ts": _now(),
        "batch": batch,
        "threshold": THRESHOLD,
        "scored": 0,
        "marked_ready": 0,
    }
    c = db()
    try:
        ensure_score_col(c)
        scored, _ = score_unscored(c, batch)
        summary["scored"] = scored
        summary["marked_ready"] = mark_nurture_ready(c)
        _log({"ts": _now(), "event": "tick_end", "summary": summary})
    finally:
        c.close()
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))