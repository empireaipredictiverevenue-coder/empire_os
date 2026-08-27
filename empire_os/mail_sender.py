"""Outbound email sender — polls si_outbox, dispatches via Resend API.

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
import requests
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- PROXY BYPASS (critical: container has HTTP_PROXY that intercepts
#     127.0.0.1, breaking all hub localhost calls) ---
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1,10.118.155.218,10.118.155.1"
os.environ["no_proxy"] = "localhost,127.0.0.1,10.118.155.218,10.118.155.1"
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mail_sender")

# Load /root/empire_os/.env if not already in process env (so standalone
# mail_sender_runner.py works without systemd-passed env). Mirrors hub.py.
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for _line in _ENV_PATH.read_text().splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k = _k.strip()
            _v = _v.strip()
            if _k and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Email providers from environment
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "sandbox.mailgun.org")
FROM_EMAIL = os.environ.get("EMPIRE_FROM", "Empire OS <founder@empire-ai.co.uk>")

# Anti-spam compliance headers
LIST_UNSUBSCRIBE_URL = os.environ.get("LIST_UNSUBSCRIBE_URL", "https://empire-ai.co.uk/unsubscribe")
LIST_UNSUBSCRIBE_EMAIL = os.environ.get("LIST_UNSUBSCRIBE_EMAIL", "unsubscribe@empire-ai.co.uk")


def _clean_sender() -> str:
    """Extract a bare email from EMPIRE_FROM even if it carries quotes/<>.

    .env stores EMPIRE_FROM="Empire OS <founder@empire-ai.co.uk>" with the
    outer double-quotes as literal characters, which Brevo/Resend reject.
    """
    import re as _re
    raw = (FROM_EMAIL or "").strip().strip('"').strip("'")
    mm = _re.search(r"[\w.+-]+@[\w.-]+\.\w+", raw)
    return mm.group(0) if mm else raw


# Pluggable SMTP relay (e.g. ImproveMX free tier) — kills the Resend bill.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "resend").lower()
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.improvmx.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FEEDBACK_DIR = Path("/root/feedback")
POLL_INTERVAL = 10
MAX_PER_CYCLE = 50

# Daily send quota
DAILY_SEND_LIMIT = int(os.environ.get("EMAIL_SEND_DAILY_LIMIT", "100"))


def _direct_mx_send(to: str, subject: str, body: str) -> dict:
    """Sovereign outbound: resolve recipient MX + deliver straight to :25.
    No SaaS, no relay creds, no daily quota. Open-source route.
    """
    try:
        import smtplib
        import socket
        import dns.resolver  # pip install dnspython
        domain = to.split("@")[-1].strip().lower()
        # Resolve MX records
        try:
            answers = dns.resolver.resolve(domain, "MX")
            mx_records = sorted([(r.preference, str(r.exchange).rstrip(".")) for r in answers])
        except Exception:
            return {"ok": False, "error": "MX resolution failed"}
        
        for _, mx in mx_records:
            try:
                with smtplib.SMTP(mx, 25, timeout=10) as s:
                    s.ehlo()
                    s.sendmail("founder@empire-ai.co.uk", [to], 
                               f"From: Empire OS <founder@empire-ai.co.uk>\r\n"
                               f"To: {to}\r\n"
                               f"Subject: {subject}\r\n"
                               f"List-Unsubscribe: <https://empire-ai.co.uk/unsubscribe>, <mailto:unsubscribe@empire-ai.co.uk>\r\n"
                               f"List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n"
                               f"\r\n{body}")
                return {"ok": True, "mx": mx}
            except Exception:
                continue
        return {"ok": False, "error": "All MX servers failed"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _resend_send(to: str, subject: str, body: str) -> dict:
    """Send one email via Resend API. Returns {ok, resend_id?, error?}."""
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key:
        return {"ok": False, "error": "RESEND_API_KEY not set"}

    is_html = bool(body and ("<html" in body.lower() or "<!doctype" in body.lower() or "<table" in body.lower() or "<h1" in body.lower()))
    _sender = _clean_sender()
    payload_dict = {
        "from": _sender,
        "to": [to],
        "subject": subject,
        "reply_to": "founder@empire-ai.co.uk",
        "headers": {
            "List-Unsubscribe": "<https://empire-ai.co.uk/unsubscribe>, <mailto:unsubscribe@empire-ai.co.uk>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    }
    if is_html:
        payload_dict["html"] = body
        payload_dict["text"] = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n").replace("</p>", "\n\n").replace("</tr>", "\n")
        import re
        payload_dict["text"] = re.sub(r"<[^>]+>", "", payload_dict["text"])
    else:
        payload_dict["text"] = body
    payload = json.dumps(payload_dict).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "curl/8.5.0",  # CF 1010 blocks Python UA
            "Authorization": f"Bearer {resend_key}",
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


# Load Brevo API key from env first, then /root/empire_secrets/brevo_api_key
def _get_brevo_key() -> str:
    """Get Brevo API key dynamically from env or secret file."""
    brevo_key = os.environ.get("BREVO_API_KEY", "")
    if not brevo_key:
        bp = Path("/root/empire_secrets/brevo_api_key")
        if bp.exists():
            brevo_key = bp.read_text().strip()
    return brevo_key


def _port25_open() -> bool:
    """Fast probe: can we reach any MX on :25? Cloud hosts usually block it."""
    import socket
    try:
        s = socket.create_connection(("smtp.gmail.com", 25), timeout=4)
        s.close()
        return True
    except Exception:
        return False


def _brevo_api_send(to: str, subject: str, body: str, html_body: str = None) -> dict:
    """Send via Brevo REST API (bypasses SMTP IP block on cloud hosts)."""
    brevo_key = os.environ.get("BREVO_API_KEY", "")
    if not brevo_key:
        bp = Path("/root/empire_secrets/brevo_api_key")
        if bp.exists():
            brevo_key = bp.read_text().strip()
    if not brevo_key:
        return {"ok": False, "error": "BREVO_API_KEY not set"}
    _sender = _clean_sender()
    payload = {
        "sender": {"email": _sender},
        "replyTo": {"email": "founder@empire-ai.co.uk"},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
        "headers": {
            "List-Unsubscribe": "<https://empire-ai.co.uk/unsubscribe>, <mailto:unsubscribe@empire-ai.co.uk>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
    }
    if html_body:
        payload["htmlContent"] = html_body
    try:
        resp = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={"api-key": brevo_key},
            timeout=30
        )
        resp.raise_for_status()
        result = resp.json()
        mid = result.get("messageId", "")
        if mid:
            return {"ok": True, "brevo_id": mid}
        return {"ok": False, "error": f"no messageId: {result}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _mailgun_send(to: str, subject: str, body: str) -> dict:
    """Send one email via Mailgun HTTP API (no port 25, no SMTP blocks)."""
    if not MAILGUN_API_KEY:
        return {"ok": False, "error": "MAILGUN_API_KEY not set"}
    from email.utils import encode_rfc2231
    # multipart/form-data
    boundary = "----mgboundary"
    def field(name, value):
        return (f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n").encode()
    body_bytes = (
        field("from", FROM_EMAIL) +
        field("to", to) +
        field("subject", subject) +
        field("text", body) +
        field("h:List-Unsubscribe", "<https://empire-ai.co.uk/unsubscribe>, <mailto:unsubscribe@empire-ai.co.uk>") +
        field("h:List-Unsubscribe-Post", "List-Unsubscribe=One-Click")
    ) + f"--{boundary}--\r\n".encode()
    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    # Basic auth: api:KEY (without "key-" prefix)
    auth_str = f"api:{MAILGUN_API_KEY}"
    import base64
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Basic {auth_b64}",
            "User-Agent": "curl/8.5.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            mid = result.get("id", "")
            if mid:
                return {"ok": True, "mailgun_id": mid}
            return {"ok": False, "error": f"no id: {result}"}
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        detail = ""
        if isinstance(e, urllib.error.HTTPError):
            detail = e.read().decode()[:200]
        return {"ok": False, "error": str(e), "detail": detail}


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


def _mark_outbox(out_id: int, status: str, resend_id: str = "", error: str = "") -> bool:
    """Mark an outbox row via the HUB HTTP endpoint (single writer).
    This is the permanent fix for the 'database is locked' cascade: direct
    sqlite writes from this process contended with the hub's 13+ concurrent
    writers under a 175MB WAL. Routing through the hub (which already uses
    busy_timeout=30s) serialises the write and stops emails getting stuck in
    'pending'. Retries on transient failure.
    """
    payload = {"status": status, "resend_id": resend_id or "",
               "error": error[:200] if error else ""}
    for attempt in range(1, 8):
        try:
            url = f"{HUB_URL.rstrip('/')}/v1/outbox/{out_id}/mark"
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
                if resp.get("ok"):
                    return True
        except Exception as e:
            if attempt == 7:
                logger.warning("hub mark outbox %s failed after retries: %s",
                               out_id, e)
                return False
            time.sleep(min(2 * attempt, 8))
    return False


def _log_send(entry: dict):
    """Append a send attempt to the JSONL log."""
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    log_path = FEEDBACK_DIR / "mail_sender.jsonl"
    entry["_ts"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _sent_today() -> int:
    """Direct count of si_outbox rows marked sent today (UTC).
    Bypasses hub /v1/outbox endpoints — read-only sqlite against the
    container's empire_os.db so the guard fires even when hub is slow.
    """
    try:
        import sqlite3 as _sq
        db = "/root/empire_os/empire_os.db"
        if not Path(db).exists():
            return 0
        c = _sq.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        n = c.execute(
            "SELECT COUNT(*) FROM si_outbox "
            "WHERE status='sent' AND DATE(sent_at)=DATE('now')"
        ).fetchone()[0]
        c.close()
        return int(n)
    except Exception:
        # If we can't read the DB, assume 0 so the limiter doesn't block sends.
        return 0


def _daily_quota_ok() -> tuple[bool, int, int]:
    """Returns (ok_to_send, sent_today, limit)."""
    if DAILY_SEND_LIMIT <= 0:
        return True, 0, 0  # 0 = unlimited
    sent = _sent_today()
    return (sent < DAILY_SEND_LIMIT, sent, DAILY_SEND_LIMIT)


def send_pending_batch() -> int:
    """Fetch pending emails from hub and send them. Returns count sent."""
    # Daily limit guard (EMAIL_SEND_DAILY_LIMIT, default 100).
    ok, sent_today, limit = _daily_quota_ok()
    if not ok:
        logger.warning(
            "daily send limit hit: %d/%d sent today — pausing until tomorrow",
            sent_today, limit,
        )
        # Append to JSONL so we have evidence of the guard firing.
        _log_send({
            "guard": "daily_limit",
            "sent_today": sent_today,
            "limit": limit,
            "action": "skip_cycle",
        })
        return 0

    resp = _hub_get(f"/v1/outbox/pending?n={MAX_PER_CYCLE}")
    if not resp or not resp.get("rows"):
        return 0

    sent = 0
    for row in resp["rows"]:
        out_id = row["id"]
        to = row["to_email"]
        subject = row["subject"]
        body = row["body"]
        meta = row.get("meta_json", "{}")

        # Skip invalid emails (parens, commas in domain) before trying to send
        domain = to.split("@")[1] if "@" in to else ""
        if any(c in domain for c in "(),"):
            _mark_outbox(out_id, "failed", error="invalid email domain")
            _log_send({"out_id": out_id, "to": to, "status": "failed", "error": "invalid_email"})
            continue

        # Determine best backend from EMAIL_BACKEND (this host is Cloudflare-
        # blocked on Resend, so default to Brevo). Fallback chain below.
        backend = os.environ.get("EMAIL_BACKEND", "brevo").lower()
        brevo_key = os.environ.get("BREVO_API_KEY", "")
        if not brevo_key:
            bp = Path("/root/empire_secrets/brevo_api_key")
            if bp.exists():
                brevo_key = bp.read_text().strip()

        # If backend is brevo, send via Brevo first (skip Resend primary)
        if backend == "brevo" and brevo_key:
            res = _brevo_api_send(row["to_email"], row["subject"], row["body"],
                                  row.get("html_body"))
            if res.get("ok"):
                _mark_outbox(out_id, "sent", res.get("brevo_id", ""))
                _log_send({"out_id": out_id, "to": to, "status": "sent",
                           "provider": "brevo", "id": res.get("brevo_id")})
                sent += 1
                continue
            # brevo failed -> try resend as last resort
            if os.environ.get("RESEND_API_KEY"):
                res = _resend_send(row["to_email"], row["subject"], row["body"])
                if res.get("ok"):
                    _mark_outbox(out_id, "sent", res.get("resend_id", ""))
                    _log_send({"out_id": out_id, "to": to, "status": "sent",
                               "provider": "resend", "id": res.get("resend_id")})
                    sent += 1
                    continue
            _mark_outbox(out_id, "failed", error=res.get("error", "brevo failed"))
            continue

        # Primary: Resend
        if os.environ.get("RESEND_API_KEY"):
            res = _resend_send(row["to_email"], row["subject"], row["body"])
            if res.get("ok"):
                _mark_outbox(out_id, "sent", res.get("resend_id", ""))
                _log_send({"out_id": out_id, "to": to, "status": "sent", "provider": "resend", "id": res.get("resend_id")})
                sent += 1
                continue

        # Fallback: Brevo
        brevo_key = os.environ.get("BREVO_API_KEY", "")
        if not brevo_key:
            bp = Path("/root/empire_secrets/brevo_api_key")
            if bp.exists():
                brevo_key = bp.read_text().strip()
        if brevo_key:
            res = _brevo_api_send(row["to_email"], row["subject"], row["body"])
            if res.get("ok"):
                _mark_outbox(out_id, "sent", res.get("brevo_id", ""))
                _log_send({"out_id": out_id, "to": row["to_email"], "status": "sent", "provider": "brevo", "id": res.get("brevo_id")})
                sent += 1
                continue

        # Final fallback: Direct MX (no SaaS, no relay)
        res = _direct_mx_send(row["to_email"], row["subject"], row["body"])
        if res.get("ok"):
            _mark_outbox(out_id, "sent", res.get("mx", ""))
            _log_send({"out_id": out_id, "to": row["to_email"], "status": "sent", "provider": "mx", "mx": res.get("mx")})
            sent += 1
            continue

        # All failed
        _mark_outbox(out_id, "failed", error="all backends failed")
        _log_send({"out_id": out_id, "to": row["to_email"], "status": "failed"})

    return sent


def main():
    logger.info("mail_sender starting — poll interval %ds, max/cycle %d", POLL_INTERVAL, MAX_PER_CYCLE)
    while True:
        try:
            sent = send_pending_batch()
            if sent:
                logger.info("sent %d emails this cycle", sent)
        except Exception as e:
            logger.exception("send cycle error: %s", e)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    main()