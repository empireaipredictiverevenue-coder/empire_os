"""Empire OS — Inbound Reply Daemon (minimal).

Long-running service that ingests prospect replies from whichever
sources are configured and forwards them to the hub's
``POST /v1/inbound/reply`` endpoint, which flips
``si_buyer_outreach.reply_state`` from ``cold``/``contacted`` → ``replied``.

Two transport modes are supported, both OFF by default so the daemon
can boot even when no Resend inbound domain or IMAP mailbox has been
wired up yet:

1. **Webhook listener (FastAPI)** — bound to ``INBOUND_REPLY_BIND``
   (default ``0.0.0.0:8087``). Exposes ``POST /v1/inbound/reply`` that
   accepts the same body the hub endpoint does. Resend inbound (or any
   other provider) can POST here directly. The handler re-shapes the
   payload into the hub contract and proxies it.

2. **IMAP poller** — when ``INBOUND_IMAP_HOST`` is set, polls the inbox
   every ``INBOUND_IMAP_INTERVAL`` seconds, parses each new message,
   and forwards it through the same path.

If neither is configured, the daemon still runs as a "no-op keeper":
it stays alive so systemd is happy, and logs every minute that it's
idle. That makes this the right unit to deploy *before* the inbound
domain / IMAP credentials exist.

CLI:
    python inbound_reply_daemon.py            # run the daemon
    python inbound_reply_daemon.py --simulate # POST a fake reply to the hub
                                             # (used by /tmp tests)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

# ── Configuration ────────────────────────────────────────────────
HUB_URL = os.environ.get("EMPIRE_HUB_URL", "http://localhost:8081").rstrip("/")
HUB_INBOUND_PATH = "/v1/inbound/reply"
BIND_HOST = os.environ.get("INBOUND_REPLY_BIND", "0.0.0.0")
BIND_PORT = int(os.environ.get("INBOUND_REPLY_PORT", "8087"))

IMAP_HOST = os.environ.get("INBOUND_IMAP_HOST", "").strip()
IMAP_USER = os.environ.get("INBOUND_IMAP_USER", "").strip()
IMAP_PASS = os.environ.get("INBOUND_IMAP_PASS", "").strip()
IMAP_FOLDER = os.environ.get("INBOUND_IMAP_FOLDER", "INBOX")
IMAP_INTERVAL = int(os.environ.get("INBOUND_IMAP_INTERVAL", "60"))  # seconds
IMAP_MARK_SEEN = os.environ.get("INBOUND_IMAP_MARK_SEEN", "1") not in ("0", "false", "")

AUDIT_LOG = Path(os.environ.get(
    "INBOUND_REPLY_AUDIT_LOG", "/root/feedback/inbound_replies.jsonl"))

LOG_PATH = Path("/root/feedback/inbound_reply_daemon.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, mode="a"),
    ],
)
log = logging.getLogger("inbound_reply_daemon")

# ── Hub forwarding ───────────────────────────────────────────────

def forward_to_hub(payload: dict, timeout: float = 5.0) -> dict:
    """POST a reply event to the hub. Returns the hub's response dict.

    Falls back to a local audit-log-only path if the hub is unreachable,
    so we never silently lose a reply.
    """
    url = f"{HUB_URL}{HUB_INBOUND_PATH}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("hub POST %s failed: %s — logging locally", url, e)
        _audit_log_locally(payload, error=f"hub_unreachable: {e}")
        return {"matched": False, "updated": False,
                "error": f"hub_unreachable: {str(e)[:160]}"}


def _audit_log_locally(payload: dict, error: Optional[str] = None) -> None:
    """Append a reply event to the local audit log even when the hub is down."""
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        event = dict(payload)
        event["ts"] = datetime.now(timezone.utc).isoformat()
        if error:
            event["local_error"] = error
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        log.error("could not write audit log: %s", e)


# ── Resend inbound webhook adapter ────────────────────────────────

def resend_to_hub_contract(body: dict) -> dict:
    """Reshape a Resend inbound-webhook payload into the hub contract.

    Resend's inbound payload (when the inbound domain is configured)
    looks roughly like::

        {
          "from": "Gilbert <gilbert@jadeair.net>",
          "to": "outreach@empire-ai.co.uk",
          "subject": "Re: ...",
          "text": "...",
          "html": "...",
          "headers": {"in_reply_to": "...", ...}
        }

    Anything missing falls back to empty strings — the hub only
    requires ``from_email``.
    """
    headers = body.get("headers") or {}
    if isinstance(headers, list):
        headers = {h.get("name", "").lower(): h.get("value", "")
                   for h in headers}
    elif isinstance(headers, dict):
        headers = {k.lower(): v for k, v in headers.items()}

    return {
        "from_email": body.get("from") or body.get("from_email") or "",
        "subject": body.get("subject") or "",
        "body": body.get("text") or body.get("body") or "",
        "in_reply_to": headers.get("in_reply_to", ""),
        "source": "resend_inbound",
    }


# ── FastAPI webhook listener ─────────────────────────────────────

def _build_webhook_app():
    """Build the webhook app lazily so the daemon can boot without FastAPI."""
    from fastapi import FastAPI, Request, HTTPException

    app = FastAPI(title="Empire Inbound Reply Daemon",
                  version="0.1.0")

    @app.get("/health")
    def health():
        return {
            "status": "online",
            "engine": "empire-inbound-reply-daemon",
            "hub_url": HUB_URL,
            "imap_enabled": bool(IMAP_HOST and IMAP_USER and IMAP_PASS),
        }

    @app.post("/v1/inbound/reply")
    async def inbound(request: Request):
        try:
            raw = await request.json()
        except Exception:
            raise HTTPException(400, "invalid JSON body")

        # If this looks like a Resend inbound payload, reshape it.
        if "from" in raw and "from_email" not in raw:
            payload = resend_to_hub_contract(raw)
        else:
            payload = {
                "from_email": raw.get("from_email") or raw.get("from") or "",
                "subject": raw.get("subject", ""),
                "body": raw.get("body", ""),
                "in_reply_to": raw.get("in_reply_to", ""),
                "source": raw.get("source", "daemon_webhook"),
            }
        if not payload["from_email"]:
            raise HTTPException(400, "from_email (or from) is required")

        result = forward_to_hub(payload)
        # Mirror to local audit log for redundancy.
        _audit_log_locally({**payload, "hub_result": result})
        return result

    return app


# ── IMAP poller ──────────────────────────────────────────────────

def _imap_poll_loop(stop_evt: threading.Event) -> None:
    """Poll an IMAP inbox and forward each new message to the hub.

    Off by default — only runs when ``INBOUND_IMAP_HOST`` is set. Uses
    stdlib ``imaplib`` so no extra dependency is required.
    """
    import imaplib
    import email as email_lib
    from email.header import decode_header, make_header

    log.info("IMAP poller starting: %s@%s/%s every %ss",
             IMAP_USER or "<unset>", IMAP_HOST or "<unset>",
             IMAP_FOLDER, IMAP_INTERVAL)

    last_seen_uid: Optional[str] = None

    while not stop_evt.is_set():
        try:
            if not (IMAP_HOST and IMAP_USER and IMAP_PASS):
                stop_evt.wait(IMAP_INTERVAL)
                continue

            conn = imaplib.IMAP4_SSL(IMAP_HOST)
            conn.login(IMAP_USER, IMAP_PASS)
            conn.select(IMAP_FOLDER)
            typ, data = conn.uid("SEARCH", None, "ALL")
            if typ != "OK":
                conn.logout()
                stop_evt.wait(IMAP_INTERVAL)
                continue
            uids = data[0].split()
            for uid in uids:
                uid_s = uid.decode()
                if last_seen_uid is not None and uid_s <= last_seen_uid:
                    continue
                typ, msgdata = conn.uid("FETCH", uid, "(RFC822)")
                if typ != "OK" or not msgdata or not msgdata[0]:
                    continue
                raw = msgdata[0][1]
                msg = email_lib.message_from_bytes(raw)

                def _decode(h):
                    try:
                        return str(make_header(decode_header(h or "")))
                    except Exception:
                        return h or ""

                from_email = _decode(msg.get("From", ""))
                subject = _decode(msg.get("Subject", ""))
                in_reply_to = _decode(msg.get("In-Reply-To", ""))

                body_text = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                body_text = part.get_payload(decode=True).decode(
                                    part.get_content_charset() or "utf-8",
                                    errors="replace")
                                break
                            except Exception:
                                continue
                else:
                    try:
                        body_text = msg.get_payload(decode=True).decode(
                            msg.get_content_charset() or "utf-8",
                            errors="replace")
                    except Exception:
                        body_text = str(msg.get_payload())

                payload = {
                    "from_email": from_email,
                    "subject": subject,
                    "body": body_text[:8000],
                    "in_reply_to": in_reply_to,
                    "source": "imap",
                }
                log.info("IMAP: forwarding reply from %s (uid=%s)",
                         from_email, uid_s)
                result = forward_to_hub(payload)
                _audit_log_locally({**payload, "hub_result": result,
                                    "imap_uid": uid_s})

                if IMAP_MARK_SEEN:
                    try:
                        conn.uid("STORE", uid, "+FLAGS", "\\Seen")
                    except Exception:
                        pass

            if uids:
                last_seen_uid = uids[-1].decode()
            conn.logout()
        except Exception as e:
            log.warning("IMAP poll error: %s", e)

        stop_evt.wait(IMAP_INTERVAL)

    log.info("IMAP poller exiting")


# ── Daemon main loop ─────────────────────────────────────────────

_stop_evt = threading.Event()


def _install_signal_handlers() -> None:
    def _handler(signum, frame):
        log.info("signal %s received — shutting down", signum)
        _stop_evt.set()
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def run_daemon() -> None:
    _install_signal_handlers()

    # IMAP poller (optional)
    imap_thread = None
    if IMAP_HOST and IMAP_USER and IMAP_PASS:
        imap_thread = threading.Thread(
            target=_imap_poll_loop, args=(_stop_evt,),
            name="imap-poller", daemon=True)
        imap_thread.start()
    else:
        log.info("IMAP poller disabled (set INBOUND_IMAP_HOST/USER/PASS to enable)")

    # Webhook listener (always on; bound to INBOUND_REPLY_BIND)
    try:
        import uvicorn
    except ImportError:
        log.error("uvicorn not installed; cannot start webhook listener. "
                  "pip install fastapi uvicorn")
        sys.exit(1)

    app = _build_webhook_app()
    config = uvicorn.Config(app, host=BIND_HOST, port=BIND_PORT,
                            log_level="info", access_log=True)
    server = uvicorn.Server(config)

    log.info("Webhook listener on %s:%s → forwarding to %s%s",
             BIND_HOST, BIND_PORT, HUB_URL, HUB_INBOUND_PATH)
    server.run()

    _stop_evt.set()
    if imap_thread:
        imap_thread.join(timeout=2)


# ── Simulate one reply (for tests) ───────────────────────────────

def simulate_reply(from_email: str, subject: str = "Re: test",
                   body: str = "Test reply", in_reply_to: str = "",
                   source: str = "simulate") -> dict:
    payload = {
        "from_email": from_email,
        "subject": subject,
        "body": body,
        "in_reply_to": in_reply_to,
        "source": source,
    }
    return forward_to_hub(payload)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--simulate", action="store_true",
                   help="POST one test reply to the hub and exit")
    p.add_argument("--from-email", default="gilbert@jadeair.net")
    p.add_argument("--subject", default="Re: outreach test")
    p.add_argument("--body", default="Yes, interested. Please send details.")
    p.add_argument("--in-reply-to", default="")
    args = p.parse_args()

    if args.simulate:
        result = simulate_reply(
            args.from_email, args.subject, args.body, args.in_reply_to,
            source="simulate")
        print(json.dumps(result, indent=2))
        return

    run_daemon()


if __name__ == "__main__":
    main()