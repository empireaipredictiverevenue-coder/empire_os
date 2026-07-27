#!/usr/bin/env python3
"""
empire_intel_market.py — market intelligence + lead-pipeline guard.

Runs as a systemd oneshot every 5 minutes (matches empire-health-deep cadence).
Produces TWO artifacts per run:

1. /root/feedback/market_intel.jsonl  — append-only JSONL of metrics for
   downstream consumers (cortex engine, neural_intel_report generator,
   g-brain north-mini). Each line:

   {
     "ts": "...",
     "lane_leads_total": ...,
     "lane_leads_null_metro": ...,
     "lane_leads_null_niche": ...,
     "lanes_occupied": ...,
     "lanes_empty": ...,
     "top_metros": [["NYC", N], ["HOU", N], ...],
     "top_niches": [["general_contractor", N], ...],
     "scoring_coverage_pct": ...,
     "pending_share_pct": ...,
     "delivered_today": ...,
     "leads_inserted_last_5min": ...,
     "guard_actions": [{"action":"backfill_metro","rows":N}, ...]
   }

2. Self-heal: backfills NULL metro / niche columns derived from lane_id
   when the lane_id format is `<niche>:<metro>`. SAFE — no destructive
   changes, just populates empty columns from data we already have.

Designed to be idempotent. Writes are append-only with timestamped rows so
consumers can tail the JSONL safely.

Run inside empire-hub container:
  /root/venv/bin/python3 /root/empire_os/scripts/empire_intel_market.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
JSONL_PATH = FEEDBACK_DIR / "market_intel.jsonl"

# Keep JSONL bounded so a stuck writer doesn't grow it unbounded.
# Older rows are rotated to market_intel.jsonl.1 etc.
MAX_JSONL_BYTES = 10 * 1024 * 1024  # 10 MiB


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _int(con: sqlite3.Connection, sql: str, *params) -> int:
    """Safe integer read."""
    try:
        row = con.execute(sql, params).fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _guard_backfill_microclimate(con: sqlite3.Connection) -> list[dict]:
    """Populate NULL metro/niche from lane_id when shape is parseable.

    Reads lane_id format `<niche>:<metro>` and writes the two columns when
    they are empty. Updates the in-memory db via commit.

    Returns list of {action, rows} for the JSONL record.
    """
    actions = []
    try:
        # metro
        cur = con.execute("""
            UPDATE lane_leads
            SET metro = SUBSTR(lane_id, INSTR(lane_id, ':') + 1)
            WHERE (metro IS NULL OR metro = '')
              AND lane_id LIKE '%:___'
              AND LENGTH(lane_id) - LENGTH(REPLACE(lane_id, ':', '')) = 1
        """)
        con.commit()
        actions.append({"action": "backfill_metro", "rows": cur.rowcount})
    except sqlite3.OperationalError as e:
        actions.append({"action": "backfill_metro", "rows": 0, "error": str(e)[:120]})

    try:
        cur = con.execute("""
            UPDATE lane_leads
            SET niche = SUBSTR(lane_id, 1, INSTR(lane_id, ':') - 1)
            WHERE (niche IS NULL OR niche = '')
              AND lane_id LIKE '%:___'
              AND LENGTH(lane_id) - LENGTH(REPLACE(lane_id, ':', '')) = 1
        """)
        con.commit()
        actions.append({"action": "backfill_niche", "rows": cur.rowcount})
    except sqlite3.OperationalError as e:
        actions.append({"action": "backfill_niche", "rows": 0, "error": str(e)[:120]})

    return actions


def _gather_metrics(con: sqlite3.Connection, guard_actions: list[dict]) -> dict:
    """Collect the metrics block for the JSONL row."""
    # Lane_leads health
    lane_total = _int(con, "SELECT COUNT(*) FROM lane_leads")
    null_metro = _int(
        con, "SELECT COUNT(*) FROM lane_leads WHERE metro IS NULL OR metro = ''"
    )
    null_niche = _int(
        con, "SELECT COUNT(*) FROM lane_leads WHERE niche IS NULL OR niche = ''"
    )

    # Lanes occupancy
    lanes_occupied = _int(
        con, "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''"
    )
    lanes_empty = _int(
        con, "SELECT COUNT(*) FROM lanes WHERE occupied_by IS NULL OR occupied_by = ''"
    )

    # Top metros + niches (top 6 each)
    try:
        top_metros = [
            (r["metro"], r["c"])
            for r in con.execute(
                "SELECT COALESCE(NULLIF(metro, ''), '<none>') AS metro, COUNT(*) AS c "
                "FROM lane_leads GROUP BY metro ORDER BY c DESC LIMIT 6"
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        top_metros = []

    try:
        top_niches = [
            (r["niche"], r["c"])
            for r in con.execute(
                "SELECT COALESCE(NULLIF(niche, ''), '<none>') AS niche, COUNT(*) AS c "
                "FROM lane_leads GROUP BY niche ORDER BY c DESC LIMIT 6"
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        top_niches = []

    # Funnel mix
    total_pending = _int(
        con, "SELECT COUNT(*) FROM lane_leads WHERE status IN ('pending','new') OR status IS NULL"
    )
    total_delivered = _int(
        con, "SELECT COUNT(*) FROM lane_leads WHERE status = 'delivered'"
    )
    total_scored = _int(
        con, "SELECT COUNT(*) FROM lane_leads WHERE omega_score IS NOT NULL AND omega_score > 0"
    )

    scoring_coverage_pct = round(
        (total_scored / lane_total * 100) if lane_total else 0.0, 2
    )
    pending_share_pct = round(
        (total_pending / lane_total * 100) if lane_total else 0.0, 2
    )

    # Throughput in the last 5 min (matches cadence)
    inserted_5m = _int(
        con, "SELECT COUNT(*) FROM lane_leads "
             "WHERE created_at > datetime('now', '-5 minutes')"
    )

    return {
        "lane_leads_total": lane_total,
        "lane_leads_null_metro": null_metro,
        "lane_leads_null_niche": null_niche,
        "lanes_occupied": lanes_occupied,
        "lanes_empty": lanes_empty,
        "top_metros": top_metros,
        "top_niches": top_niches,
        "scoring_coverage_pct": scoring_coverage_pct,
        "pending_share_pct": pending_share_pct,
        "delivered_today": total_delivered,
        "leads_inserted_last_5min": inserted_5m,
        "guard_actions": guard_actions,
    }


def _rotate_if_large(path: Path) -> None:
    """Rotate JSONL when it grows past MAX_JSONL_BYTES."""
    if not path.exists():
        return
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size <= MAX_JSONL_BYTES:
        return
    # keep the last 80% in place, move the rest to a rotated file
    rotated = path.with_suffix(".jsonl.1")
    try:
        if rotated.exists():
            rotated.unlink()
        path.rename(rotated)
    except OSError:
        pass  # best-effort rotation


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    con = _connect()
    try:
        guard_actions = _guard_backfill_microclimate(con)
        record = {"ts": now, **_gather_metrics(con, guard_actions)}
    finally:
        con.close()

    # Write JSONL (append, with rotation)
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    _rotate_if_large(JSONL_PATH)
    with JSONL_PATH.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")

    # Also write a "latest" snapshot for tools that don't tail JSONL
    latest = FEEDBACK_DIR / "market_intel_latest.json"
    with latest.open("w") as f:
        json.dump(record, f, indent=2, default=str)

    # One-line summary for the journal
    null_m = record["lane_leads_null_metro"]
    null_n = record["lane_leads_null_niche"]
    ins = record["leads_inserted_last_5min"]
    print(
        f"market_intel: total={record['lane_leads_total']:,} "
        f"null_metro={null_m} null_niche={null_n} "
        f"inserted_5m={ins} guard_actions={len(record['guard_actions'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
