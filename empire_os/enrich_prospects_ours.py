#!/usr/bin/env python3
"""enrich_prospects_ours — Uses OUR enrichment.batch_enrich (no external Hunter).

Fills missing emails in si_buyer_outreach by running our multi-source
enrichment cascade (whois, bbb, hunter, apollo, prospeo, email_pattern,
google_search, ddg, bing, website_scraper — all 15 sources in
empire_os/enrichment.py).

Reads HUNTER_API_KEY / APOLLO_API_KEY / PROSPEO_API_KEY from
/root/empire_secrets/* (best-effort, missing keys are skipped).

Schedule: nightly systemd timer.
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
LOG_PATH = FEEDBACK_DIR / "enrich_prospects.jsonl"

DEFAULT_BATCH = int(os.getenv("ENRICH_BATCH", "100"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


class Backend:
    """Minimal shim matching enrichment.py expectations."""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


def run(batch: int = DEFAULT_BATCH, dry_run: bool = False) -> dict:
    """Run enrichment cascade on missing-email prospects."""
    sys.path.insert(0, "/root/empire_os")
    from empire_os.enrichment import enrich_prospects

    backend = Backend(DB_PATH)
    summary = {
        "ts": _now(),
        "batch": batch,
        "dry_run": dry_run,
        "processed": 0,
        "enriched": 0,
        "failed": 0,
    }

    try:
        result = enrich_prospects(backend, limit=batch, only_missing_email=True)
        summary.update(result)
        _log({"ts": _now(), "event": "tick_end", "summary": summary})
    except Exception as e:
        summary["error"] = str(e)[:200]
        _log({"ts": _now(), "event": "error", "err": str(e)[:200]})
    finally:
        backend.conn.close()

    return summary


if __name__ == "__main__":
    import sys as _s
    dry = "--dry-run" in _s.argv
    batch = int(_s.argv[1]) if len(_s.argv) > 1 and _s.argv[1].isdigit() else DEFAULT_BATCH
    print(json.dumps(run(batch=batch, dry_run=dry), indent=2, default=str))