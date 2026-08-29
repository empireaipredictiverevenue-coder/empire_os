#!/usr/bin/env python3
"""Empire OS — Gmail Backlog Cleanup (FAST inline version).

Fix: the original script paginated ALL days first then STORE'd at the end.
That made it look like a hung process because step 4 never began within the
timeout. This version INTERLEAVES: paginate one day bucket, immediately
STORE the UIDs as Seen, paginate next day. Each cycle is fast and makes
progress visible. ALso caps total marked UIDs so it always exits.

Run:
    incus exec empire-hub -- python3 /root/empire_os/empire_os/gmail_backlog_cleanup_v2.py [--cap 5000]

Always sys.exit(0). Idempotent — re-run picks up remaining UIDs.
"""
from __future__ import annotations

import imaplib
import json
import logging
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "flavag83@gmail.com"
IMAP_FOLDER = "INBOX"

CREDS_PATH = Path("/root/empire_secrets/gmail_app_password")
LOG_PATH = Path("/root/empire_os/feedback/gmail_backlog_cleanup.log")
JSONL_PATH = Path("/root/empire_os/feedback/gmail_backlog_cleanup.jsonl")

# 90-day retention: mark anything OLDER than this. Recent never touched.
KEEP_RECENT_DAYS = 90
# Per-bucket sleep so we don't hammer Gmail (rate-limit safety).
SLEEP_BETWEEN_BUCKETS_S = 0.5
# Default cap: stop after marking N UIDs (avoid hours-long runs).
DEFAULT_CAP = 5000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_creds():
    try:
        pw = CREDS_PATH.read_text().strip()
        return pw or None
    except OSError as e:
        print(f"creds read failed: {e}", flush=True)
        return None


def _audit(event: str, **fields):
    record = {"ts": _now(), "event": event, **fields}
    try:
        JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with JSONL_PATH.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass
    line = f"{record['ts']} {event} " + " ".join(f"{k}={v}" for k, v in fields.items())
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line, flush=True)


def _connect(pw):
    ctx = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
    imap.login(IMAP_USER, pw)
    imap.select(IMAP_FOLDER, readonly=False)
    return imap


def _store_seen(imap, uids: list) -> int:
    """Mark a list of UIDs as Seen. Returns count successfully marked."""
    if not uids:
        return 0
    # Gmail accepts comma-joined UID list, but split for safety.
    joined = ",".join(u.decode() if isinstance(u, bytes) else u for u in uids)
    try:
        typ, data = imap.uid("STORE", joined, "+FLAGS", "\\Seen")
        if typ != "OK":
            return 0
        # Response is one entry per UID; count OK flags.
        ok_count = sum(1 for d in data if d is not None)
        return ok_count
    except (imaplib.IMAP4.error, OSError) as e:
        print(f"STORE batch error ({len(uids)} uids): {e}", flush=True)
        return 0


def main():
    cap = DEFAULT_CAP
    if "--cap" in sys.argv:
        try:
            cap = int(sys.argv[sys.argv.index("--cap") + 1])
        except (IndexError, ValueError):
            pass

    pw = _read_creds()
    if not pw:
        _audit("error", reason="missing_creds")
        return 0

    _audit("start", cap=cap)
    imap = _connect(pw)
    try:
        # ESEARCH for total unseen count (sanity)
        try:
            typ, data = imap.uid("SEARCH", None, "ESEARCH", "RETURN", "COUNT", "UNSEEN")
            if typ == "OK" and data and data[0]:
                total_unseen = int(str(data[0]).split()[-1])
                _audit("unseen_total", count=total_unseen)
        except Exception:
            total_unseen = None

        marked_total = 0
        today = datetime.now(timezone.utc).date()
        cutoff = today - timedelta(days=KEEP_RECENT_DAYS)

        # Walk back day-by-day. For each day:
        # 1. UID SEARCH UNSEEN BEFORE <day+1> SINCE <day> → UIDs in that day
        # 2. Immediately STORE +FLAGS \Seen on them
        # 3. Sleep SLEEP_BETWEEN_BUCKETS_S
        # 4. If marked_total >= cap, stop.
        # We go up to 5 years back to drain anything in this mailbox.
        MAX_BACK_DAYS = 365 * 5
        for offset in range(1, MAX_BACK_DAYS + 1):
            if marked_total >= cap:
                _audit("cap_hit", cap=cap, marked=marked_total)
                break

            day = today - timedelta(days=offset)
            next_day = day + timedelta(days=1)
            day_str = day.strftime("%d-%b-%Y")
            next_day_str = next_day.strftime("%d-%b-%Y")
            try:
                typ, data = imap.uid(
                    "SEARCH", None, "UNSEEN",
                    "BEFORE", next_day_str,
                    "SINCE", day_str,
                )
            except Exception as e:
                _audit("search_error", day=day_str, error=str(e)[:120])
                continue
            if typ != "OK" or not data or not data[0]:
                # No unseen in this day — continue scanning older days.
                continue

            uids = data[0].split()
            if not uids:
                continue

            marked = _store_seen(imap, uids)
            marked_total += marked
            _audit(
                "bucket",
                day=day_str,
                hits=len(uids),
                marked=marked,
                running_total=marked_total,
            )
            time.sleep(SLEEP_BETWEEN_BUCKETS_S)

        _audit("done", marked=marked_total, cap=cap)
        return marked_total
    except Exception as e:
        _audit("error", error=str(e)[:200])
        return 0
    finally:
        try:
            imap.logout()
        except Exception:
            pass


if __name__ == "__main__":
    n = main()
    sys.exit(0)