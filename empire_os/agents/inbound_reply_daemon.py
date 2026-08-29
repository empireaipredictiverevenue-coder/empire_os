"""Empire OS — Gmail IMAP Inbound Reply Poller.

Polls Gmail via IMAP (imap.gmail.com:993 SSL) for ``flavag83@gmail.com``
and forwards each unseen message to the Empire OS hub endpoint
``POST /v1/inbound/parse`` so the buyer-outreach lane can flip its
state machine (``cold`` / ``contacted`` → ``replied``).

Behaviour matrix
----------------
* **No creds file** (or empty file): the daemon enters a *waiting for
  creds* state — it logs every 60s and never connects to Gmail. This
  lets systemd keep the unit alive while the operator provisions the
  Gmail App Password.
* **Creds present**: the daemon logs into Gmail via IMAP IDLE-free
  polling (``MAILBOX UNSEEN`` every ``POLL_INTERVAL`` seconds), fetches
  each unseen message, extracts headers + plain-text body, and POSTs
  it to the hub. On 2xx the message is marked ``\\Seen``; on transient
  failures the message is left untouched for the next cycle.
* **Hub unreachable**: the message stays unseen; the error is logged
  and JSONL-appended. The poll loop never crashes systemd.
* **SIGTERM / SIGINT**: graceful shutdown, current poll finishes, then
  exit 0.

Files
-----
* IMAP password:  ``/root/empire_secrets/gmail_app_password`` (mode 600)
* Human log:      ``/root/empire_os/feedback/inbound_reply_daemon.log``
* JSONL audit:    ``/root/empire_os/feedback/inbound_reply_daemon.jsonl``
* systemd unit:   ``/etc/systemd/system/empire-inbound-reply.service``

The daemon never raises on transient failures — every catch block
logs and continues.
"""
from __future__ import annotations

import email
import imaplib
import json
import logging
import os
import signal
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# ── Configuration ────────────────────────────────────────────────
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "flavag83@gmail.com"
IMAP_FOLDER = "INBOX"

CREDS_PATH = Path("/root/empire_secrets/gmail_app_password")
LOG_PATH = Path("/root/empire_os/feedback/inbound_reply_daemon.log")
JSONL_PATH = Path("/root/empire_os/feedback/inbound_reply_daemon.jsonl")

HUB_URL = os.environ.get("EMPIRE_HUB_URL", "http://127.0.0.1:8080").rstrip("/")
HUB_INBOUND_PATH = "/v1/inbound/parse"

POLL_INTERVAL = 60          # seconds between IMAP poll cycles
HUB_TIMEOUT = 10             # seconds for hub POST
WAITING_CREDS_RETRY = 60     # seconds between "waiting for creds" log lines
MAX_PER_CYCLE = 20           # max unseen messages to forward per cycle
IMAP_PER_PAGE_LIMIT = 500    # cap per day-bucket page to keep responses small
IMAP_DAY_WINDOW_DAYS = 14    # how far back to paginate when ESEARCH is large

# ── Logging ──────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s inbound_reply_daemon %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("inbound_reply_daemon")


# ── Helpers ──────────────────────────────────────────────────────
def _read_creds() -> Optional[str]:
    """Return the Gmail app password from disk, or None if unavailable.

    The file must exist, be readable, and contain a non-empty stripped
    value. Empty / whitespace-only / unreadable files are treated as
    'creds not present'.
    """
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


def _decode(value: Optional[str]) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body(msg: EmailMessage) -> str:
    """Prefer text/plain; fall back to text/html stripped of tags."""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
                except Exception:
                    continue
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # crude tag strip; hub will sanitise further if needed
                    import re
                    return re.sub(r"<[^>]+>", " ", html)
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
        except Exception:
            pass
    return ""


def _parse_message(raw_bytes: bytes) -> Dict[str, Any]:
    """Turn raw RFC822 bytes into the hub payload contract."""
    msg = email.message_from_bytes(raw_bytes)

    from_header = _decode(msg.get("From"))
    from_name, from_email = parseaddr(from_header)
    subject = _decode(msg.get("Subject"))
    message_id = (msg.get("Message-ID") or "").strip()
    to_email = _decode(msg.get("To"))
    body_text = _extract_body(msg)
    headers = {k: _decode(v) for k, v in msg.items()}

    return {
        "message_id": message_id,
        "from_email": from_email,
        "from_name": from_name,
        "to_email": to_email,
        "subject": subject,
        "body_text": body_text,
        "headers": headers,
    }


def _post_to_hub(payload: Dict[str, Any]) -> int:
    """POST to the hub; return HTTP status (0 on transport error)."""
    url = HUB_URL + HUB_INBOUND_PATH
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HUB_TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        log.warning("hub POST %s -> HTTP %s", url, exc.code)
        return exc.code
    except urllib.error.URLError as exc:
        log.warning("hub POST %s -> transport error: %s", url, exc)
        return 0
    except Exception as exc:  # last-resort safety net
        log.exception("hub POST unexpected error: %s", exc)
        return 0


# ── IMAP poll cycle ─────────────────────────────────────────────
def _imap_poll(pw: str) -> int:
    """One IMAP poll cycle. Returns number of messages forwarded.

    Handles Gmail IMAP response size: Gmail can return >1 MB on a single
    UID SEARCH if the mailbox is large. We paginate by date buckets and
    also cap per-cycle with MAX_PER_CYCLE so a backlog never wedges the
    hub thread.
    """
    forwarded = 0
    ctx = ssl.create_default_context()
    imap: Optional[imaplib.IMAP4_SSL] = None
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ctx)
        imap.login(IMAP_USER, pw)
        imap.select(IMAP_FOLDER, readonly=False)

        # Step 1: ask Gmail for recent UIDs only — paginates server-side.
        # ESEARCH returns "1:M" of UIDVALIDITY range; we then narrow to UNSEEN
        # via standard UID SEARCH (still capped by Gmail to a reasonable size).
        uids = _fetch_unseen_uids_paginated(imap)
        if not uids:
            log.info("imap poll: no unseen messages")
            return 0
        log.info("imap poll: %d unseen message(s)", len(uids))

        # Step 2: cap per-cycle so we don't wedge the hub on a huge backlog.
        uids_to_process = uids[:MAX_PER_CYCLE]
        if len(uids) > MAX_PER_CYCLE:
            log.info("imap poll: capping at %d this cycle (%d deferred)",
                     MAX_PER_CYCLE, len(uids) - MAX_PER_CYCLE)

        for num in uids_to_process:
            typ, msg_data = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or not msg_data[0]:
                log.warning("imap fetch failed for uid %s", num)
                continue
            raw = msg_data[0][1]
            try:
                payload = _parse_message(raw)
            except Exception as exc:
                log.exception("parse failed for uid %s: %s", num, exc)
                _audit("parse_error", uid=num.decode(errors="replace"), error=str(exc))
                continue

            status = _post_to_hub(payload)
            if 200 <= status < 300:
                imap.store(num, "+FLAGS", "\\Seen")
                forwarded += 1
                log.info(
                    "forwarded msg_id=%s from=%s status=%d",
                    payload.get("message_id"), payload.get("from_email"), status,
                )
                _audit(
                    "forwarded",
                    message_id=payload.get("message_id"),
                    from_email=payload.get("from_email"),
                    status=status,
                )
            else:
                log.warning("hub rejected msg_id=%s status=%d — leaving unseen",
                            payload.get("message_id"), status)
                _audit(
                    "forward_failed",
                    message_id=payload.get("message_id"),
                    from_email=payload.get("from_email"),
                    status=status,
                )
        return forwarded
    except imaplib.IMAP4.error as exc:
        log.warning("imap error: %s", exc)
        _audit("imap_error", error=str(exc))
        return 0
    except OSError as exc:
        log.warning("imap network error: %s", exc)
        _audit("imap_network_error", error=str(exc))
        return 0
    except Exception as exc:
        log.exception("imap unexpected error: %s", exc)
        _audit("imap_unexpected_error", error=str(exc))
        return 0
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass


def _fetch_unseen_uids_paginated(imap: imaplib.IMAP4_SSL) -> list:
    """Fetch UNSEEN UIDs in date-bucket pages to avoid Gmail's >1 MB limit.

    Gmail returns oversized (>1 MB) responses when many UIDs match a single
    SEARCH. We split by day-bucket windows so each SEARCH stays small.

    Falls back to non-paginated search if ESEARCH/UID SEARCH is unavailable.
    """
    try:
        # First try ESEARCH (RFC 7377) — returns "1:M" range count without
        # listing UIDs. If count <= safety threshold, do single UID SEARCH UNSEEN.
        typ, data = imap.uid("SEARCH", None, "ESEARCH", "RETURN", "COUNT", "UNSEEN")
        if typ == "OK" and data and data[0]:
            count = int(str(data[0]).split()[-1])
            if count <= 1000:
                # Safe to fetch all UNSEEN UIDs in one call.
                typ, data = imap.uid("SEARCH", None, "UNSEEN")
                if typ == "OK" and data and data[0]:
                    return data[0].split()
            # Otherwise paginate by day.
            return _paginate_unseen_by_day(imap)
    except Exception as exc:
        log.debug("ESEARCH path failed, falling back: %s", exc)

    # Plain fallback: try standard SEARCH UNSEEN. Gmail may still 1MB-truncate.
    try:
        typ, data = imap.search(None, "UNSEEN")
        if typ == "OK" and data and data[0]:
            return data[0].split()
    except Exception:
        pass

    return []


def _paginate_unseen_by_day(imap: imaplib.IMAP4_SSL) -> list:
    """Walk back day-by-day until we hit the IMAP_PER_PAGE_LIMIT or empty bucket."""
    from datetime import datetime, timedelta, timezone
    out: list = []
    today = datetime.now(timezone.utc).date()
    for offset in range(IMAP_DAY_WINDOW_DAYS):
        day = today - timedelta(days=offset)
        # SINCE = day 00:00 UTC, BEFORE = next day 00:00 UTC. Imap accepts
        # "SINCE 1-Jan-2025" format.
        date_str = day.strftime("%d-%b-%Y")
        try:
            typ, data = imap.uid("SEARCH", None, "UNSEEN", "SINCE", date_str)
            if typ == "OK" and data and data[0]:
                out.extend(data[0].split())
                if len(out) >= IMAP_PER_PAGE_LIMIT:
                    log.info("imap paginate: hit page limit %d at day=%s",
                             IMAP_PER_PAGE_LIMIT, date_str)
                    break
        except Exception as exc:
            log.debug("imap paginate skip day=%s: %s", date_str, exc)
    return out


# ── Signal handling ──────────────────────────────────────────────
_RUNNING = True


def _stop(signum, frame):  # noqa: ARG001
    global _RUNNING
    log.info("signal %s received — shutting down after current cycle", signum)
    _RUNNING = False


# ── Main loop ────────────────────────────────────────────────────
def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    log.info(
        "inbound_reply_daemon starting (user=%s host=%s hub=%s%s interval=%ds)",
        IMAP_USER, IMAP_HOST, HUB_URL, HUB_INBOUND_PATH, POLL_INTERVAL,
    )
    _audit("start", user=IMAP_USER, host=IMAP_HOST, hub=HUB_URL + HUB_INBOUND_PATH)

    cycle = 0
    while _RUNNING:
        cycle += 1
        creds = _read_creds()

        if not creds:
            log.info(
                "waiting for creds at %s — will retry every %ds (cycle %d)",
                CREDS_PATH, WAITING_CREDS_RETRY, cycle,
            )
            _audit("waiting_for_creds", path=str(CREDS_PATH))
            # sleep in small slices so SIGTERM lands quickly
            slept = 0
            while _RUNNING and slept < WAITING_CREDS_RETRY:
                time.sleep(1)
                slept += 1
            continue

        log.info("poll cycle %d starting", cycle)
        forwarded = _imap_poll(creds)
        log.info("poll cycle %d complete (forwarded=%d)", cycle, forwarded)
        _audit("poll_cycle_complete", cycle=cycle, forwarded=forwarded)

        # sleep in small slices so SIGTERM lands quickly
        slept = 0
        while _RUNNING and slept < POLL_INTERVAL:
            time.sleep(1)
            slept += 1

    log.info("inbound_reply_daemon stopped cleanly")
    _audit("stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())