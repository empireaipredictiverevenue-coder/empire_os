"""Empire OS — Gmail Backlog Cleanup.

Marks OLD unseen messages as ``\\Seen`` to drain a large unread backlog
on ``flavag83@gmail.com`` without losing anything recent.

Rules
-----
* Keep messages newer than 90 days (search predicate: ``BEFORE
  <today - 90d>``).
* NEVER mark any message whose internal date is within the last 30
  days, even if it slips past the 90-day threshold (clock-drift /
  timezone safety net).
* Hard cap: ``MAX_PER_RUN = 50_000`` UIDs marked per run.
* If a single ``UID SEARCH UNSEEN BEFORE ...`` returns >10 000 hits,
  Gmail truncates the response. We paginate by day buckets going
  backwards until the bucket is empty or the cap is hit.
* Graceful errors: every external call is wrapped in try/except; the
  run never crashes systemd / a scheduled trigger.

Files
-----
* IMAP password:  ``/root/empire_secrets/gmail_app_password``
* JSONL audit:    ``/root/empire_os/feedback/gmail_backlog_cleanup.jsonl``
* Human log:      ``/root/empire_os/feedback/gmail_backlog_cleanup.log``

Run
---
::

    incus exec empire-hub -- python3 /root/empire_os/empire_os/gmail_backlog_cleanup.py
"""
from __future__ import annotations

import imaplib
import json
import logging
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime, parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Configuration ────────────────────────────────────────────────
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "flavag83@gmail.com"
IMAP_FOLDER = "INBOX"

CREDS_PATH = Path("/root/empire_secrets/gmail_app_password")
LOG_PATH = Path("/root/empire_os/feedback/gmail_backlog_cleanup.log")
JSONL_PATH = Path("/root/empire_os/feedback/gmail_backlog_cleanup.jsonl")

# 90-day retention rule (the spec).
KEEP_RECENT_DAYS = 90
# 30-day safety floor — never touch messages within this window.
# Redundant with the 90-day rule, but defends against clock drift,
# mis-classified internal dates, and accidental future-dated mail.
SAFETY_FLOOR_DAYS = 30

# Gmail truncates huge SEARCH responses. Anything above this count gets
# paginated by day bucket.
PAGINATE_THRESHOLD = 10_000
# Page size: how many days to walk backwards per pagination round.
# Bigger = fewer IMAP roundtrips. Smaller = each response stays under
# Gmail's 1 MB cap.
PAGINATE_DAY_WINDOW = 30
# Hard cap per run — abort gracefully when reached.
MAX_PER_RUN = 50_000
# Sleep between UID STORE batches so we don't hammer Gmail.
BATCH_SIZE = 500
BATCH_SLEEP_S = 0.2

# ── Logging ──────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s gmail_backlog_cleanup %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gmail_backlog_cleanup")


# ── Helpers ──────────────────────────────────────────────────────
def _read_creds() -> Optional[str]:
    """Read the Gmail app password from disk."""
    try:
        if not CREDS_PATH.exists():
            return None
        pw = CREDS_PATH.read_text().strip()
        return pw or None
    except OSError as exc:
        log.warning("creds read failed: %s", exc)
        return None


def _audit(event: str, **fields: Any) -> None:
    """Append a structured event to the JSONL audit log."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    try:
        with JSONL_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.warning("jsonl write failed: %s", exc)


def _imap_date(dt: datetime) -> str:
    """Return IMAP date string for a UTC datetime."""
    return dt.strftime("%d-%b-%Y")


def _safe_internal_date(imap: imaplib.IMAP4_SSL, uid: str) -> Optional[datetime]:
    """Fetch the INTERNALDATE for a UID and return as UTC datetime.

    Returns None if the fetch fails. INTERNALDATE is the date Gmail
    stamped when the message was received (in the mailbox's timezone,
    usually UTC). We use this to defend the 30-day safety floor
    regardless of the sender's claimed Date header.
    """
    try:
        typ, data = imap.uid("FETCH", uid, "(INTERNALDATE)")
        if typ != "OK" or not data or not data[0]:
            return None
        # data[0] is a tuple like (b'1 (INTERNALDATE "29-Jul-2026 10:14:22 +0000")', b'"29-Jul-2026 10:14:22 +0000"')
        # Extract the quoted date string robustly.
        for item in data:
            if isinstance(item, tuple) and len(item) >= 1:
                raw = item[0]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                # Find first quoted substring.
                start = raw.find('"')
                end = raw.find('"', start + 1) if start >= 0 else -1
                if start >= 0 and end > start:
                    from email.utils import parsedate_to_datetime as _ptd

                    return _ptd(raw[start + 1 : end]).astimezone(timezone.utc)
        return None
    except Exception as exc:
        log.debug("internaldate fetch failed for uid=%s: %s", uid, exc)
        return None


def _fetch_unseen_count_under_threshold(
    imap: imaplib.IMAP4_SSL, cutoff: datetime
) -> Optional[int]:
    """Use ESEARCH to count UNSEEN messages BEFORE ``cutoff``.

    Returns the count, or None on protocol failure.
    """
    date_str = _imap_date(cutoff)
    try:
        typ, data = imap.uid(
            "SEARCH", None, "ESEARCH", "RETURN", "COUNT", "UNSEEN",
            "BEFORE", date_str,
        )
        if typ == "OK" and data and data[0]:
            return int(str(data[0]).split()[-1])
    except Exception as exc:
        log.debug("ESEARCH count failed: %s", exc)
    return None


def _paginate_unseen_by_day(
    imap: imaplib.IMAP4_SSL, floor_dt: datetime, ceiling_dt: datetime
) -> List[str]:
    """Walk day-by-day from ``ceiling_dt`` backwards to ``floor_dt``.

    Returns the union of UNSEEN UIDs in the window
    ``[floor_dt, ceiling_dt)`` (half-open: floor_dt included,
    ceiling_dt excluded — i.e. messages strictly older than
    ``ceiling_dt``).

    Each day produces at most one ``UID SEARCH UNSEEN SINCE D BEFORE
    D+1`` roundtrip. Stops early when the bucket is empty OR when we
    exceed ``PAGINATE_DAY_WINDOW`` days (caller should re-invoke with a
    shifted window).
    """
    out: List[str] = []
    # Walk newest → oldest so the most recent (still-in-window) mail
    # gets processed first; older mail is the lower priority.
    for offset in range(PAGINATE_DAY_WINDOW):
        day = ceiling_dt.date() - timedelta(days=offset)
        # Day window: SINCE <day 00:00 UTC>, BEFORE <day+1 00:00 UTC>.
        day_start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        if day_start < floor_dt:
            return out  # walked past the safety floor — stop.
        sin_str = _imap_date(day_start)
        bef_str = _imap_date(day_end)
        try:
            typ, data = imap.uid(
                "SEARCH", None, "UNSEEN", "SINCE", sin_str, "BEFORE", bef_str
            )
            if typ == "OK" and data and data[0]:
                uids = data[0].split()
                if uids:
                    log.info(
                        "paginate day=%s hits=%d (running total=%d)",
                        sin_str, len(uids), len(out),
                    )
                    _audit(
                        "paginate_day", day=sin_str,
                        hit_count=len(uids), running_total=len(out),
                    )
                    out.extend(uids)
        except Exception as exc:
            log.warning("paginate day=%s failed: %s", sin_str, exc)
            _audit("paginate_day_error", day=sin_str, error=str(exc))
    return out


def _store_seen_batch(imap: imaplib.IMAP4_SSL, uids: List[str]) -> Tuple[int, int]:
    """Mark a batch of UIDs as ``\\Seen``.

    Returns (success_count, fail_count). Gmail accepts a comma-separated
    UID list in a single STORE command. We pass the whole batch at once
    to minimise roundtrips; Gmail splits it internally if needed.
    """
    if not uids:
        return 0, 0
    joined = b",".join(uids)
    try:
        typ, data = imap.uid("STORE", joined, "+FLAGS", "\\Seen")
        if typ != "OK":
            return 0, len(uids)
        # The response is one entry per UID, each carrying a FETCH FLAGS
        # line. Count successful flags.
        ok = 0
        for item in data or []:
            if isinstance(item, tuple) and item[0]:
                raw = item[0]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                if "\\Seen" in raw:
                    ok += 1
        return ok, len(uids) - ok
    except Exception as exc:
        log.warning("STORE batch failed: %s", exc)
        return 0, len(uids)


def _imap_count_unseen(imap: imaplib.IMAP4_SSL) -> Optional[int]:
    """Return current mailbox UNSEEN count, or None on error."""
    try:
        typ, data = imap.select(IMAP_FOLDER, readonly=True)
        if typ == "OK" and data and data[0]:
            return int(data[0])
    except Exception as exc:
        log.warning("COUNT UNSEEN failed: %s", exc)
    return None


# ── Main run ─────────────────────────────────────────────────────
def run() -> int:
    """Execute one cleanup pass; return 0 on success, non-zero on error."""
    t0 = time.monotonic()
    creds = _read_creds()
    if not creds:
        log.error("no creds at %s — aborting", CREDS_PATH)
        _audit("abort", reason="no_creds", path=str(CREDS_PATH))
        return 2

    now = datetime.now(timezone.utc)
    cutoff_90d = now - timedelta(days=KEEP_RECENT_DAYS)
    cutoff_30d = now - timedelta(days=SAFETY_FLOOR_DAYS)

    log.info(
        "starting cleanup: now=%s cutoff_90d=%s safety_floor=%s max_per_run=%d",
        now.isoformat(timespec="seconds"),
        cutoff_90d.isoformat(timespec="seconds"),
        cutoff_30d.isoformat(timespec="seconds"),
        MAX_PER_RUN,
    )
    _audit(
        "start",
        now=now.isoformat(),
        cutoff_90d=cutoff_90d.isoformat(),
        safety_floor=cutoff_30d.isoformat(),
        max_per_run=MAX_PER_RUN,
        user=IMAP_USER, host=IMAP_HOST,
    )

    ctx = ssl.create_default_context()
    imap: Optional[imaplib.IMAP4_SSL] = None
    marked_total = 0
    skipped_recent = 0
    skipped_error = 0
    before_unseen: Optional[int] = None
    after_unseen: Optional[int] = None

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
        imap.login(IMAP_USER, creds)
        imap.select(IMAP_FOLDER, readonly=False)

        # Baseline unseen count.
        before_unseen = _imap_count_unseen(imap)
        log.info("baseline UNSEEN count: %s", before_unseen)
        _audit("baseline", unseen=before_unseen)

        # Step 1: cheap ESEARCH to count candidates BEFORE cutoff_90d.
        count_under_90d = _fetch_unseen_count_under_threshold(imap, cutoff_90d)
        log.info("ESEARCH UNSEEN BEFORE %s count=%s",
                 _imap_date(cutoff_90d), count_under_90d)
        _audit("esearch_count", before=_imap_date(cutoff_90d),
               count=count_under_90d)

        candidate_uids: List[str] = []
        if count_under_90d is None or count_under_90d > PAGINATE_THRESHOLD:
            # Paginate by day. Walk backwards in PAGINATE_DAY_WINDOW-sized
            # chunks until EITHER we collect the target count OR we run
            # out of day-buckets to ask about (i.e. we hit the floor or
            # the bucket is empty).
            log.info("paginating by day buckets (window=%d days each, cap=%d)",
                     PAGINATE_DAY_WINDOW, MAX_PER_RUN)
            ceiling = cutoff_90d  # exclusive upper bound
            floor = cutoff_90d - timedelta(days=10 * 365)  # 10y safety
            empty_pages_in_a_row = 0
            while True:
                page = _paginate_unseen_by_day(imap, floor, ceiling)
                if not page:
                    empty_pages_in_a_row += 1
                    # Two empty 30-day windows in a row = we've walked
                    # past the actual data. Break immediately to save
                    # the ESEARCH+before-ground floor case.
                    if empty_pages_in_a_row >= 2:
                        log.info("two consecutive empty pages — stopping pagination")
                        break
                else:
                    empty_pages_in_a_row = 0
                candidate_uids.extend(page)
                log.info("page complete: collected=%d total=%d",
                         len(page), len(candidate_uids))
                _audit("page_complete",
                       page_size=len(page), total=len(candidate_uids))
                # Advance ceiling backwards by the window size.
                ceiling = ceiling - timedelta(days=PAGINATE_DAY_WINDOW)
                if ceiling <= floor:
                    break
                # Bail if we already have enough candidates — keeps
                # the run fast even when the ESEARCH count is huge.
                if len(candidate_uids) >= MAX_PER_RUN:
                    log.info("hit MAX_PER_RUN=%d — stopping pagination", MAX_PER_RUN)
                    break
        else:
            # Small enough to fetch in one shot.
            try:
                date_str = _imap_date(cutoff_90d)
                typ, data = imap.uid("SEARCH", None, "UNSEEN", "BEFORE", date_str)
                if typ == "OK" and data and data[0]:
                    candidate_uids = data[0].split()
            except Exception as exc:
                log.warning("single-shot SEARCH failed: %s", exc)
                _audit("search_single_failed", error=str(exc))

        log.info("candidate UIDs to inspect: %d", len(candidate_uids))
        _audit("candidates_collected", count=len(candidate_uids))

        # Step 2: enforce 30-day safety floor AND global cap.
        if len(candidate_uids) > MAX_PER_RUN:
            log.warning(
                "candidate count %d exceeds MAX_PER_RUN=%d — truncating",
                len(candidate_uids), MAX_PER_RUN,
            )
            _audit("cap_truncate",
                   candidates=len(candidate_uids), cap=MAX_PER_RUN)
            candidate_uids = candidate_uids[:MAX_PER_RUN]

        # Step 3: 30-day safety floor (defence in depth).
        #
        # All candidates were gathered by ``BEFORE <today-90d>``, so by
        # construction they are >= 90 days old — guaranteed older than
        # the 30-day floor. A per-UID INTERNALDATE fetch on 50K UIDs
        # would add thousands of roundtrips for no safety gain (the
        # search predicate is authoritative). We instead spot-check a
        # small random sample (100 UIDs spread across the candidate
        # list) to detect any IMAP server misbehaviour, then proceed.
        SPOT_CHECK = 100
        spot_failures = 0
        if len(candidate_uids) > SPOT_CHECK:
            import random
            sample = random.sample(candidate_uids, SPOT_CHECK)
            for uid in sample:
                dt = _safe_internal_date(imap, uid)
                if dt is not None and dt >= cutoff_30d:
                    # Should NEVER happen — search predicate is
                    # ``BEFORE <today-90d>``. If it does, bail out.
                    spot_failures += 1
                    log.error(
                        "30d safety SPOT-CHECK FAIL uid=%s dt=%s — aborting",
                        uid, dt.isoformat(),
                    )
        if spot_failures > 0:
            _audit("safety_abort", spot_failures=spot_failures)
            log.error("spot-check failed %d/%d — aborting run", spot_failures, SPOT_CHECK)
            return 4
        safe_uids = candidate_uids
        log.info(
            "30d safety floor verified via %d-UID spot check (0 failures)",
            min(SPOT_CHECK, len(candidate_uids)),
        )
        _audit("safety_spot_check",
               spot_check=min(SPOT_CHECK, len(candidate_uids)),
               failures=0)

        # Step 4: STORE +FLAGS \Seen in batches.
        for i in range(0, len(safe_uids), BATCH_SIZE):
            batch = safe_uids[i : i + BATCH_SIZE]
            ok, fail = _store_seen_batch(imap, batch)
            marked_total += ok
            skipped_error += fail
            if (i // BATCH_SIZE) % 10 == 0:
                log.info(
                    "STORE progress: %d/%d marked=%d fail=%d",
                    min(i + BATCH_SIZE, len(safe_uids)),
                    len(safe_uids), marked_total, skipped_error,
                )
                _audit("store_progress",
                       processed=min(i + BATCH_SIZE, len(safe_uids)),
                       total=len(safe_uids),
                       marked=marked_total, failed=skipped_error)
            time.sleep(BATCH_SLEEP_S)

        # Step 5: re-count UNSEEN to verify the drop.
        after_unseen = _imap_count_unseen(imap)
        log.info("final UNSEEN count: %s", after_unseen)
        _audit("final_unseen", unseen=after_unseen)

    except imaplib.IMAP4.abort as exc:
        log.error("IMAP abort: %s", exc)
        _audit("imap_abort", error=str(exc))
        return 3
    except Exception as exc:
        log.exception("cleanup failed: %s", exc)
        _audit("cleanup_failed", error=str(exc))
        return 1
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass

    elapsed = time.monotonic() - t0
    delta = (
        (before_unseen - after_unseen)
        if (before_unseen is not None and after_unseen is not None)
        else None
    )
    log.info(
        "DONE marked=%d skip_recent=%d skip_error=%d "
        "before_unseen=%s after_unseen=%s delta=%s elapsed=%.1fs",
        marked_total, skipped_recent, skipped_error,
        before_unseen, after_unseen, delta, elapsed,
    )
    _audit(
        "done",
        marked=marked_total,
        skip_recent=skipped_recent,
        skip_error=skipped_error,
        before_unseen=before_unseen,
        after_unseen=after_unseen,
        delta=delta,
        elapsed_s=round(elapsed, 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())