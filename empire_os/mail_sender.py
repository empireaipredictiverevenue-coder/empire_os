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
# Pluggable SMTP relay (e.g. ImproveMX free tier) — kills the Resend bill.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "resend").lower()
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.improvmx.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_TLS = os.environ.get("SMTP_TLS", "1") == "1"
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FEEDBACK_DIR = Path("/root/feedback")
POLL_INTERVAL = 30  # seconds between poll cycles
MAX_PER_CYCLE = 10  # max emails to pull per poll


def _direct_mx_send(to: str, subject: str, body: str) -> dict:
    """Sovereign outbound: resolve recipient MX + deliver straight to :25.
    No SaaS, no relay creds, no daily quota. Open-source route."""
    try:
        import smtplib
        import socket
        import dns.resolver  # pip install dnspython
        domain = to.split("@")[-1].strip().lower()
        if not domain:
            return {"ok": False, "error": "no recipient domain"}
        try:
            mx = sorted(dns.resolver.resolve(domain, "MX"),
                       key=lambda r: r.preference)[0].exchange.to_text().rstrip(".")
        except Exception:
            mx = domain  # fallback: try the A/AAAA directly
        from email.mime.text import MIMEText
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        # 10s connect + 30s overall; some MX are slow/blocked -> fail fast
        s = smtplib.SMTP(mx, 25, timeout=30)
        s.ehlo()
        if s.has_extn("starttls"):
            s.starttls()
        s.ehlo()
        s.sendmail(FROM_EMAIL, [to], msg.as_string())
        s.quit()
        return {"ok": True, "msg_id": f"direct:{mx}:{to}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _smtp_send(to: str, subject: str, body: str) -> dict:
    """Send one email via an SMTP relay (ImproveMX/Mailgun/etc). $0 if the
    relay is free. Returns {ok, msg_id?, error?}."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return {"ok": False, "error": "SMTP not configured (SMTP_HOST/USER/PASS)"}
    try:
        import smtplib
        from email.mime.text import MIMEText
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            if SMTP_TLS:
                s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_EMAIL, [to], msg.as_string())
        return {"ok": True, "msg_id": f"smtp:{to}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _real_smtp_cfg() -> bool:
    """True only if SMTP creds are real (not REPLACE_WITH_ placeholders)."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False
    for v in (SMTP_USER, SMTP_PASS):
        if str(v).startswith("REPLACE_WITH_"):
            return False
    return True


def _send(to: str, subject: str, body: str) -> dict:
    """Dispatch with failover: direct MX -> Resend -> SMTP relay.

    direct MX needs no creds (sovereign delivery). Used first when backend
    is 'direct' OR when SMTP creds are placeholder/missing. Resend then
    SMTP relay are the managed fallbacks.
    """
    # direct MX first (no creds, sovereign) — but only when backend explicitly
    # 'direct' AND port 25 reachable. In cloud hosts port 25 is usually
    # blocked, so we skip fast to avoid 30s hangs.
    if EMAIL_BACKEND == "direct" and _port25_open():
        try:
            r = _direct_mx_send(to, subject, body)
            if r.get("ok"):
                return r
        except Exception as e:
            r = {"ok": False, "error": f"direct_mx: {e}"}
    # Resend FIRST (SPF includes _spf.resend.com — proper deliverability).
    # Brevo (SPF missing — emails hit spam).
    if RESEND_API_KEY:
        r = _resend_send(to, subject, body)
        if r.get("ok"):
            return r
    # Brevo API fallback (bypasses SMTP IP block, no port 25 needed)
    if BREVO_API_KEY:
        r = _brevo_api_send(to, subject, body)
        if r.get("ok"):
            return r
    # Resend (if key present)
    if RESEND_API_KEY:
        r = _resend_send(to, subject, body)
        if r.get("ok"):
            return r
        err = str(r.get("error", ""))
        if "429" in err or "quota" in err.lower() or "daily" in err.lower():
            if _real_smtp_cfg():
                s = _smtp_send(to, subject, body)
                if s.get("ok"):
                    s["fallback"] = "smtp"
                return s
            return r
    # SMTP relay (real creds only)
    if _real_smtp_cfg():
        return _smtp_send(to, subject, body)
    return r if "r" in dir() else {"ok": False, "error": "no usable backend"}


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
            "User-Agent": "curl/8.5.0",  # CF 1010 blocks Python UA
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


BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")


def _port25_open() -> bool:
    """Fast probe: can we reach any MX on :25? Cloud hosts usually block it."""
    import socket
    try:
        s = socket.create_connection(("smtp.gmail.com", 25), timeout=4)
        s.close()
        return True
    except Exception:
        return False


def _brevo_api_send(to: str, subject: str, body: str) -> dict:
    """Send via Brevo REST API (bypasses SMTP IP block on cloud hosts)."""
    if not BREVO_API_KEY:
        return {"ok": False, "error": "BREVO_API_KEY not set"}
    payload = json.dumps({
        "sender": {"email": FROM_EMAIL.split("<")[-1].rstrip(">") if "<" in FROM_EMAIL else FROM_EMAIL},
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }).encode()
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": BREVO_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            mid = result.get("messageId", "")
            if mid:
                return {"ok": True, "brevo_id": mid}
            return {"ok": False, "error": f"no messageId: {result}"}
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

        result = _send(to_email, subject, body)

        if result.get("ok"):
            # Mark sent on hub
            mark = _hub_post(f"/v1/outbox/{out_id}/mark", {
                "status": "sent",
                "resend_id": result.get("resend_id", ""),
            })
            status = "sent"
            log_entry = {
                "id": out_id, "to": to_email, "status": "sent",
                "backend": EMAIL_BACKEND,
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
