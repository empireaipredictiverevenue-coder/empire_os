"""
Outbound email sender — polls si_outbox, dispatches via Resend API.

Designed to run as either:
  a) A background thread inside the hub process, or
  b) A standalone cron job / systemd service

Logs every send attempt to /root/feedback/mail_sender.jsonl
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mail_sender")

# ── Auto-load .env so RESEND_API_KEY is available ─────────────────────
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _ln in _ENV_PATH.read_text().splitlines():
            _ln = _ln.strip()
            if not _ln or _ln.startswith("#") or "=" not in _ln:
                continue
            _k, _v = _ln.split("=", 1)
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("EMPIRE_FROM", "Empire OS <founder@empire-ai.co.uk>")
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FEEDBACK_DIR = Path("/root/feedback")
POLL_INTERVAL = 30  # seconds between poll cycles
MAX_PER_CYCLE = 10  # max emails to pull per poll


def _resend_send(to: str, subject: str, body: str) -> dict:
    """Send one email via Resend API. Returns {ok, resend_id?, error?}."""
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not set"}

    payload = json.dumps({
        "from": FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EmpireOS/1.0",
            "Authorization": f"Bearer {RESEND_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            rid = result.get("id", "")
            if rid:
                return {"ok": True, "resend_id": rid}
            return {"ok": False, "error": f"no id in response: {result}"}
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        body_text = ""
        if isinstance(e, urllib.error.HTTPError):
            body_text = e.read().decode()[:200]
        return {"ok": False, "error": str(e), "detail": body_text}


def _hub_get(endpoint: str) -> Optional[dict]:
    """GET from hub API."""
    url = f"{HUB_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("hub GET %s failed: %s", endpoint, e)
        return None


def _hub_post(endpoint: str, data: dict) -> Optional[dict]:
    """POST to hub API."""
    url = f"{HUB_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("hub POST %s failed: %s", endpoint, e)
        return None


def _log_send(entry: dict):
    """Append a send attempt to the JSONL log."""
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    log_path = FEEDBACK_DIR / "mail_sender.jsonl"
    entry["_ts"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def send_pending_batch() -> int:
    """Fetch pending emails from hub and send them. Returns count sent."""
    resp = _hub_get(f"/v1/outbox/pending?n={MAX_PER_CYCLE}")
    if not resp or not resp.get("rows"):
        return 0

    sent = 0
    for item in resp["rows"]:
        out_id = item["id"]
        to_email = item["to_email"]
        subject = item["subject"]
        body = item["body"]

        logger.info("sending %d → %s: %s", out_id, to_email, subject[:60])

        result = _resend_send(to_email, subject, body)

        if result.get("ok"):
            # Mark sent on hub
            mark = _hub_post(f"/v1/outbox/{out_id}/mark", {
                "status": "sent",
                "resend_id": result.get("resend_id", ""),
            })
            status = "sent"
            log_entry = {
                "id": out_id, "to": to_email, "status": "sent",
                "resend_id": result.get("resend_id"),
                "hub_mark_ok": mark.get("ok", False) if mark else False,
            }
            sent += 1
        else:
            # Mark failed
            err = result.get("error", "unknown")
            _hub_post(f"/v1/outbox/{out_id}/mark", {
                "status": "failed",
                "error": err[:200],
            })
            status = "failed"
            log_entry = {
                "id": out_id, "to": to_email, "status": "failed",
                "error": err, "detail": result.get("detail", ""),
            }

        _log_send(log_entry)
        logger.info("  → %s (resend_id=%s)", status, log_entry.get("resend_id", ""))

        # Brief throttle between sends (Resend rate limit)
        time.sleep(1)

    return sent


def run_forever(interval: int = POLL_INTERVAL):
    """Main loop. Polls, sends, sleeps."""
    logger.info("mail_sender started (poll every %ds)", interval)
    while True:
        try:
            n = send_pending_batch()
            if n:
                logger.info("dispatched %d emails this cycle", n)
        except Exception as e:
            logger.error("cycle error: %s", e, exc_info=True)
        time.sleep(interval)


def run_once():
    """Single-shot send (for cron/systemd oneshot)."""
    n = send_pending_batch()
    logger.info("dispatched %d emails (oneshot)", n)
    return n


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    import sys
    if "--once" in sys.argv:
        run_once()
    else:
        run_forever()
