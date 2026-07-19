"""
Empire OS v3 - Mail Sender Agent
==================================

Outbound sender using Resend (already wired in hub). Polls a queue
table (si_outbox) for pending emails + dispatches via Resend API.

Cadence: 30s.

Queue ingestion:
  - reads /root/feedback/email_expert.jsonl (email-expert draft log)
  - converts each entry into a si_outbox row (if not already)
  - rate-limited: 100/day per tier (free-tier friendly)
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

# Load .env if any key is missing
env_path = Path("/root/empire_os/.env")
if env_path.exists():
    for ln in env_path.read_text().splitlines():
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            if not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip()

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
RESEND_API = os.environ.get("RESEND_API_KEY",
                            "")
FROM_EMAIL = os.environ.get("EMPIRE_FROM",
                            "Empire OS <founder@empire-ai.co.uk>")
REPLY_TO = os.environ.get("EMPIRE_REPLY_TO", "founder@empire-ai.co.uk")
ALLOWED_DOMAIN = os.environ.get("ALLOWED_SEND_DOMAIN", "empire-ai.co.uk")
FB  = Path("/root/feedback")
LOG = FB / "mail_sender.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(30)))
DAILY_CAP = int(os.environ.get("DAILY_CAP", "100"))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def _hub_get(path: str):
    try:
        return requests.get(f"{HUB}{path}", timeout=8).json()
    except Exception:
        return {}


def _hub_post(path: str, body: dict):
    try:
        r = requests.post(f"{HUB}{path}", json=body, timeout=10)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)[:160]}


def queue_via_compose(brief: dict) -> dict:
    """Compose a draft via the hub's /v1/email/compose endpoint."""
    code, data = _hub_post("/v1/email/compose", brief)
    return {"code": code, "data": data}


def send_via_resend(to: str, subject: str, body: str) -> dict:
    """Send via Resend using the API key in .env."""
    if not RESEND_API:
        return {"ok": False, "error": "RESEND_API_KEY not set"}
    # Domain guard: refuse any sender outside the allowed domain
    if f"@{ALLOWED_DOMAIN}" not in FROM_EMAIL:
        return {"ok": False,
                "error": f"from '{FROM_EMAIL}' not on allowed domain @{ALLOWED_DOMAIN}"}
    try:
        r = requests.post("https://api.resend.com/emails",
                          headers={"Authorization": f"Bearer {RESEND_API}",
                                   "Content-Type": "application/json"},
                          json={"from": FROM_EMAIL,
                                "to": [to],
                                "reply_to": [REPLY_TO],
                                "subject": subject,
                                "text": body},
                          timeout=15)
        if r.status_code in (200, 201):
            return {"ok": True, "id": (r.json() or {}).get("id", "")}
        return {"ok": False, "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def already_sent_today() -> int:
    log_path = LOG
    if not log_path.exists():
        return 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = 0
    for ln in log_path.read_text().splitlines():
        if today in ln and '"ok": true' in ln:
            n += 1
    return n


def cycle():
    if not RESEND_API:
        log("WARN", "no_resend_key",
            note="set RESEND_API_KEY in /root/empire_os/.env")
        return
    sent_today = already_sent_today()
    if sent_today >= DAILY_CAP:
        log("INFO", "daily_cap_reached", sent=sent_today)
        return
    # poll hub's si_outbox
    pending = _hub_get("/v1/outbox/pending?n=10")
    rows = pending.get("rows", []) if isinstance(pending, dict) else []
    if not rows:
        log("INFO", "queue_empty")
        return
    for r in rows:
        to      = r.get("to_email", "")
        subject = r.get("subject", "(no subject)")
        body    = r.get("body", "")
        out_id  = r.get("id", "")
        result = send_via_resend(to, subject, body)
        log("EVENT" if result.get("ok") else "ERROR",
            "send", to=to, subject=subject[:80],
            ok=result.get("ok", False), resend_id=result.get("id"),
            err=result.get("error", "")[:120],
            out_id=out_id)
        # mark sent via hub
        if result.get("ok"):
            _hub_post(f"/v1/outbox/{out_id}/mark", {"status": "sent"})


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] mail-sender online - {INTERVAL}s "
          f"daily_cap={DAILY_CAP}", flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
