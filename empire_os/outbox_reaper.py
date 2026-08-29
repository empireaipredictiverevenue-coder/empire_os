#!/usr/bin/env python3
"""Empire outbox reaper — drain si_outbox backlog.

Long-lived daemon. Every 30s:

  1. Mark the 20 oldest `pending` rows as `sent` (sets sent_at).
  2. Mark `pending` rows older than 30 days as `dropped`.
  3. Mark `failed` rows older than 14 days as `dropped`.

Each row is processed in its own try/except so one bad row can't kill the
cycle. The daemon ALWAYS sys.exit(0) — even on fatal errors — so systemd
Restart=always can keep it alive without thrashing.

Log: /root/empire_os/feedback/outbox_reaper.jsonl  (one JSON object per line)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG = "/root/empire_os/feedback/outbox_reaper.jsonl"

CYCLE_SLEEP_SEC = 30
SEND_BATCH = 20                       # oldest pending marked 'sent' per cycle
PENDING_DROP_AGE_DAYS = 30            # older pending -> dropped
FAILED_DROP_AGE_DAYS = 14             # older failed  -> dropped
OLD_PENDING_DROP_BATCH = 200          # safety cap per cycle
OLD_FAILED_DROP_BATCH = 500           # safety cap per cycle
SQLITE_TIMEOUT = 30


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_log(entry: dict) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as exc:  # never let logging crash the daemon
        print(f"[outbox_reaper] log write failed: {exc}", flush=True)


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB, timeout=SQLITE_TIMEOUT)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _drop_old_pending(conn: sqlite3.Connection, ts: str) -> tuple[int, list[dict]]:
    """Pending rows older than PENDING_DROP_AGE_DAYS -> 'dropped'."""
    cur = conn.execute(
        "SELECT id, created_at FROM si_outbox "
        "WHERE status='pending' AND created_at < datetime('now','-30 days') "
        "ORDER BY created_at LIMIT ?",
        (OLD_PENDING_DROP_BATCH,),
    )
    ids = [r[0] for r in cur.fetchall()]
    dropped = 0
    errs: list[dict] = []
    for row_id in ids:
        try:
            uc = conn.execute(
                "UPDATE si_outbox SET status='dropped', sent_at=? "
                "WHERE id=? AND status='pending' AND created_at < datetime('now','-30 days')",
                (ts, row_id),
            )
            if uc.rowcount > 0:
                dropped += 1
        except Exception as exc:
            errs.append({"row_id": row_id, "op": "drop_old_pending", "error": str(exc)[:200]})
    return dropped, errs


def _mark_oldest_pending_as_sent(conn: sqlite3.Connection, ts: str) -> tuple[int, list[dict]]:
    """Mark SEND_BATCH oldest `pending` rows as `sent` (sets sent_at)."""
    cur = conn.execute(
        "SELECT id FROM si_outbox WHERE status='pending' "
        "ORDER BY created_at LIMIT ?",
        (SEND_BATCH,),
    )
    ids = [r[0] for r in cur.fetchall()]
    marked = 0
    errs: list[dict] = []
    for row_id in ids:
        try:
            uc = conn.execute(
                "UPDATE si_outbox SET status='sent', sent_at=? "
                "WHERE id=? AND status='pending'",
                (ts, row_id),
            )
            if uc.rowcount > 0:
                marked += 1
        except Exception as exc:
            errs.append({"row_id": row_id, "op": "mark_sent", "error": str(exc)[:200]})
    return marked, errs


def _drop_old_failed(conn: sqlite3.Connection, ts: str) -> tuple[int, list[dict]]:
    """Failed rows older than FAILED_DROP_AGE_DAYS -> 'dropped'."""
    cur = conn.execute(
        "SELECT id FROM si_outbox WHERE status='failed' "
        "AND created_at < datetime('now','-14 days') "
        "ORDER BY created_at LIMIT ?",
        (OLD_FAILED_DROP_BATCH,),
    )
    ids = [r[0] for r in cur.fetchall()]
    dropped = 0
    errs: list[dict] = []
    for row_id in ids:
        try:
            uc = conn.execute(
                "UPDATE si_outbox SET status='dropped', sent_at=? "
                "WHERE id=? AND status='failed' AND created_at < datetime('now','-14 days')",
                (ts, row_id),
            )
            if uc.rowcount > 0:
                dropped += 1
        except Exception as exc:
            errs.append({"row_id": row_id, "op": "drop_old_failed", "error": str(exc)[:200]})
    return dropped, errs


def _counts(conn: sqlite3.Connection) -> tuple[int | None, int | None]:
    """Best-effort remaining counts for visibility (not blocking)."""
    try:
        (p,) = conn.execute(
            "SELECT COUNT(*) FROM si_outbox WHERE status='pending'"
        ).fetchone()
        (f,) = conn.execute(
            "SELECT COUNT(*) FROM si_outbox WHERE status='failed'"
        ).fetchone()
        return p, f
    except Exception:
        return None, None


def reap_cycle() -> dict:
    """One drain cycle. Returns a summary dict."""
    ts = _now()
    summary: dict = {
        "ts": ts,
        "marked_sent": 0,
        "dropped_old_pending": 0,
        "dropped_old_failed": 0,
        "row_errors": 0,
        "remaining_pending": None,
        "remaining_failed": None,
    }
    all_errs: list[dict] = []

    conn = _open_db()
    try:
        # 1. Drop ancient pending first (frees ID space, clear audit).
        n, errs = _drop_old_pending(conn, ts)
        summary["dropped_old_pending"] = n
        all_errs.extend(errs)

        # 2. Deliver is owned by mail_sender.py (empire-mail-sender.service).
        #    This reaper MUST NOT flip pending->sent itself — that silently drops
        #    undelivered mail (the 14k-invoice gap). It only drops ancient rows.
        #    (mark-sent step removed: mail_sender marks sent after real dispatch.)

        # 3. Drop ancient failed rows.
        n, errs = _drop_old_failed(conn, ts)
        summary["dropped_old_failed"] = n
        all_errs.extend(errs)

        # Commit once per cycle — much faster than per-row commit.
        conn.commit()

        # Visibility (best-effort, may be slow on huge tables).
        p, f = _counts(conn)
        summary["remaining_pending"] = p
        summary["remaining_failed"] = f
    finally:
        try:
            conn.close()
        except Exception:
            pass

    summary["row_errors"] = len(all_errs)
    if all_errs:
        summary["sample_errors"] = all_errs[:5]
    return summary


def main() -> None:
    _write_log({"event": "start", "ts": _now(), "pid": os.getpid()})
    print("[outbox_reaper] started, pid={}".format(os.getpid()), flush=True)

    while True:
        try:
            s = reap_cycle()
            _write_log({"event": "cycle", **s})
            print(
                "[outbox_reaper] cycle "
                "marked_sent={marked_sent} dropped_old_pending={dropped_old_pending} "
                "dropped_old_failed={dropped_old_failed} errors={row_errors} "
                "remaining_pending={remaining_pending} remaining_failed={remaining_failed}".format(**s),
                flush=True,
            )
        except Exception as exc:
            err_entry = {
                "event": "cycle_error",
                "ts": _now(),
                "error": str(exc)[:500],
                "tb": traceback.format_exc()[:500],
            }
            _write_log(err_entry)
            print(f"[outbox_reaper] cycle error: {exc}", flush=True)

        try:
            time.sleep(CYCLE_SLEEP_SEC)
        except Exception:
            # Ctrl-C / signal — exit cleanly with 0 so systemd is happy.
            break


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _write_log({"event": "fatal", "ts": _now(), "error": str(exc)[:500]})
        print(f"[outbox_reaper] fatal: {exc}", flush=True)
    # ALWAYS exit 0 — systemd Restart=always will respawn us on actual crashes.
    sys.exit(0)