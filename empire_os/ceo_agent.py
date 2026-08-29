#!/usr/bin/env python3
"""CEO Agent — Daily Decision Surface for Empire OS.

Reads funnel + revenue metrics, builds the "today" queue of decisions
the operator must act on. Runs hourly via systemd timer.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.funnel import SQLiteBackend, count_by_state, list_states
from empire_os.agent_core import OllamaClient

logger = logging.getLogger("ceo_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

FEEDBACK_DIR = Path("/root/empire_os/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

DB = "/root/empire_os/empire_os.db"
HUB = "http://127.0.0.1:8081"
TICK_INTERVAL = 3600  # 1 hour


def build_brief(backend: SQLiteBackend, as_of: date = None) -> dict:
    """Build the CEO daily brief. Idempotent read-only."""
    today = as_of or date.today()
    today_str = today.isoformat()

    # Funnel counts
    funnel_counts = count_by_state(backend)
    total_prospects = sum(funnel_counts.values())

    # Headline from daily_revenue_snapshots
    gross = settled = settlement_count = 0
    try:
        cursor = backend.execute(
            "SELECT gross_cents, settled_cents, settlement_count "
            "FROM daily_revenue_snapshots WHERE snapshot_date = ?",
            (today_str,),
        )
        row = cursor.fetchone()
        if row:
            gross = row["gross_cents"]
            settled = row["settled_cents"]
            settlement_count = row["settlement_count"]
    except Exception:
        pass

    # Decisions
    decisions = []

    # Priority 1: prospects that have replied (awaiting CEO review/claim)
    replied = list_states(backend, state="replied")
    for p in replied:
        decisions.append({
            "kind": "review_replied",
            "target_id": p.prospect_id,
            "priority": 1,
            "summary": f"Prospect {p.prospect_id} replied — review and claim",
        })

    # Priority 2: newly matched prospects that need outreach drafted
    matched = list_states(backend, state="matched")
    for p in matched:
        decisions.append({
            "kind": "ship_draft",
            "target_id": p.prospect_id,
            "priority": 2,
            "summary": f"Prospect {p.prospect_id} is matched — draft outreach",
        })

    # Priority 3: funnel summary
    decisions.append({
        "kind": "funnel_check",
        "target_id": "overview",
        "priority": 3,
        "summary": f"Pipeline: {funnel_counts}",
    })

    decisions.sort(key=lambda d: d["priority"])

    brief = {
        "date": today_str,
        "headline": {
            "gross_cents": gross,
            "settled_cents": settled,
            "settlement_count": settlement_count,
            "prospects_in_pipeline": total_prospects,
        },
        "funnel": funnel_counts,
        "decisions": decisions,
    }
    return brief


def tick():
    """Single CEO cycle — build and log brief."""
    backend = SQLiteBackend(DB)
    try:
        brief = build_brief(backend)
    finally:
        backend.close()

    # Log to feedback
    log_file = FEEDBACK_DIR / f"ceo_brief_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(brief) + "\n")

    logger.info(
        "CEO brief (%s): %d prospects, %d decisions, $%d gross",
        brief["date"],
        brief["headline"]["prospects_in_pipeline"],
        len(brief["decisions"]),
        brief["headline"]["gross_cents"],
    )

    return {"cycle": brief["date"], "summary": f"brief: {len(brief['decisions'])} decisions"}


def main():
    logger.info("CEO agent starting — tick interval %ds", TICK_INTERVAL)
    consecutive_failures = 0
    while True:
        try:
            result = tick()
            consecutive_failures = 0
            print(json.dumps(result))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            logger.error("CEO cycle failed: %s (backoff %ds)", e, backoff)
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)


if __name__ == "__main__":
    main()