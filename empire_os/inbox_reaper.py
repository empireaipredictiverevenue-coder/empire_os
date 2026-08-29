#!/usr/bin/env python3
"""GRIP inbox reaper — drain stale si_outbox backlog.

Schedule: every 5 min via systemd timer. Idempotent, safe to re-run.
ALWAYS sys.exit(0).
"""
import sqlite3, os, sys, json
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/grip_inbox_reaper.jsonl"
MAX_PER_RUN = 500
SQLITE_TIMEOUT = 10


def now():
    return datetime.now(timezone.utc).isoformat()


def open_db():
    uri = f"file:{DB}?mode=rw"
    c = sqlite3.connect(uri, uri=True, timeout=SQLITE_TIMEOUT)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def write_log(entry):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    ts = now()
    summary = {"ts": ts, "dropped_count": 0, "retried_count": 0, "remaining_pending": 0, "actions": []}

    try:
        c = open_db()

        # 1. Drop pending rows older than 30 days (cap batch).
        cur = c.execute(
            "UPDATE si_outbox SET status='dropped' "
            "WHERE id IN (SELECT id FROM si_outbox "
            "  WHERE status='pending' AND created_at < datetime('now','-30 days') "
            "  ORDER BY created_at LIMIT ?) "
            "AND status='pending'",
            (MAX_PER_RUN,),
        )
        summary["dropped_old"] = cur.rowcount
        summary["dropped_count"] = summary["dropped_old"]
        c.commit()

        # 2. Drop failed rows older than 14 days (audit trail preserved).
        cur = c.execute(
            "UPDATE si_outbox SET status='dropped' "
            "WHERE id IN (SELECT id FROM si_outbox "
            "  WHERE status='failed' AND created_at < datetime('now','-14 days') "
            "  ORDER BY created_at LIMIT ?) "
            "AND status='failed'",
            (MAX_PER_RUN,),
        )
        summary["dropped_failed"] = cur.rowcount
        summary["dropped_count"] += summary["dropped_failed"]
        c.commit()

        # 3. Retry failed rows whose sent_at is NULL (no delivery evidence)
        #    and are younger than the 14-day drop cutoff. Schema has no
        #    `error` column, so we approximate the spirit of
        #    "skip invalid/suppressed" by requiring sent_at IS NULL and a
        #    recent-ish created_at.
        cur = c.execute(
            "UPDATE si_outbox SET status='pending', sent_at=NULL "
            "WHERE id IN (SELECT id FROM si_outbox "
            "  WHERE status='failed' AND sent_at IS NULL "
            "  AND created_at >= datetime('now','-14 days') "
            "  ORDER BY created_at LIMIT ?) "
            "AND status='failed' AND sent_at IS NULL",
            (MAX_PER_RUN,),
        )
        summary["retried_count"] = cur.rowcount
        c.commit()

        # 4. Remaining pending count (for visibility) — read after the
        #    three updates above, so it reflects post-run state.
        (remaining,) = c.execute(
            "SELECT COUNT(*) FROM si_outbox WHERE status='pending'"
        ).fetchone()
        c.close()
        summary["remaining_pending"] = remaining

        summary["actions"] = [
            {"action": "drop", "kind": "pending_over_30d", "count": summary["dropped_old"]},
            {"action": "drop", "kind": "failed_over_14d", "count": summary["dropped_failed"]},
            {"action": "retry", "kind": "failed_no_send_evidence", "count": summary["retried_count"]},
        ]

    except Exception as e:
        # On crash mid-run, partial counts already populated into summary.
        # Mark the entry as partial so consumers can branch on it.
        summary["partial"] = True
        summary["error"] = str(e)[:300]
        # still emit one JSONL line per run, exit 0

    write_log(summary)
    print(
        "inbox_reaper dropped={} retried={} remaining_pending={}".format(
            summary["dropped_count"], summary["retried_count"], summary["remaining_pending"]
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()