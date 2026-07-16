"""
Hermes Gateway — single ingress for outbound notifications.

Why: Empire OS agents emit alerts via empire_os.alerting.emit(). Today
those alerts go straight to Resend. As we add Telegram (and future
channels), every sender would need to know every transport. This
gateway inverts the dependency: alerts go to /v1/notify/* here, and
the gateway fans them out to Telegram, Resend email, and (later) Slack.

Endpoints
---------
  GET  /v1/health              — liveness + transport status
  POST /v1/notify/telegram     — send a message to Telegram
  POST /v1/notify/email        — send via Resend (always empire-ai.co.uk)
  POST /v1/notify/alert        — paginate operator, severity-aware routing
  POST /v1/brief/daily         — generate + send CEO daily brief to Telegram
  GET  /v1/notify/recent       — last 50 outbound events
  GET  /v1/notify/stats        — per-channel counts

Channel routing rules
---------------------
  severity == critical -> Telegram + Email (always)
  severity == high     -> Telegram + Email
  severity == info     -> Telegram only
  severity == low      -> Telegram only

If Telegram fails: retry once, then fall back to Email.
If Email fails: log to /root/feedback/hermes_gateway.jsonl + return error.
"""
from __future__ import annotations
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests

ROLE_DIR = Path("/root/hermes_gateway")
ROLE_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = ROLE_DIR / "outbound.jsonl"
LOG_PATH.touch(exist_ok=True)

# Load .env
env_path = Path("/root/empire_os/.env")
if env_path.exists():
    for ln in env_path.read_text().splitlines():
        if "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            if not os.environ.get(k.strip()):
                os.environ[k.strip()] = v.strip()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
EMPIRE_FROM = os.environ.get("EMPIRE_FROM",
                             "Empire OS <founder@empire-ai.co.uk>")
EMPIRE_REPLY_TO = os.environ.get("EMPIRE_REPLY_TO", "founder@empire-ai.co.uk")
ALLOWED_DOMAIN = os.environ.get("ALLOWED_SEND_DOMAIN", "empire-ai.co.uk")
ALERT_FALLBACK_EMAIL = os.environ.get("ALERT_FALLBACK_EMAIL",
                                     "founder@empire-ai.co.uk")

HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")

app = FastAPI(title="hermes-gateway", version="0.1.0")


def _log(event: dict):
    event.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(event) + "\n")


def _telegram_send(text: str, parse_mode: str = "HTML", revenue: bool = False) -> dict:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("TELEGRAM not configured: set TELEGRAM_BOT_TOKEN + "
                        "TELEGRAM_CHAT_ID in .env to enable alerts")
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN/CHAT_ID not set"}
    # money-only mode: drop non-revenue (ops/noise) alerts at the chokepoint
    if os.environ.get("TELEGRAM_MONEY_ONLY", "0") == "1" and not revenue:
        return {"ok": True, "skipped": "money_only"}
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url,
                          json={"chat_id": TELEGRAM_CHAT_ID,
                                "text": text,
                                "parse_mode": parse_mode,
                                "disable_web_page_preview": True},
                          timeout=10)
        d = r.json() if r.headers.get("content-type", "").startswith(
            "application/json") else {}
        ok = r.status_code == 200 and d.get("ok", False)
        return {"ok": ok,
                "status": r.status_code,
                "message_id": (d.get("result") or {}).get("message_id")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def _resend_send(to: str, subject: str, body: str) -> dict:
    if not RESEND_API_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not set"}
    if f"@{ALLOWED_DOMAIN}" not in EMPIRE_FROM:
        return {"ok": False,
                "error": f"from '{EMPIRE_FROM}' not on @{ALLOWED_DOMAIN}"}
    try:
        r = requests.post("https://api.resend.com/emails",
                          headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                                   "Content-Type": "application/json"},
                          json={"from": EMPIRE_FROM,
                                "to": [to],
                                "reply_to": [EMPIRE_REPLY_TO],
                                "subject": subject,
                                "text": body},
                          timeout=15)
        if r.status_code in (200, 201):
            return {"ok": True,
                    "id": (r.json() or {}).get("id", "")}
        return {"ok": False, "status": r.status_code,
                "error": r.text[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


class NotifyPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    parse_mode: str = "HTML"
    severity: str = "info"  # critical | high | info | low
    source: str = "unknown"


class EmailPayload(BaseModel):
    to: str
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1)
    severity: str = "info"


class AlertPayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=4000)
    severity: str = "info"
    source: str = "unknown"


@app.get("/v1/health")
def health():
    return {
        "status": "online",
        "ts": datetime.now(timezone.utc).isoformat(),
        "channels": {
            "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
            "email":    bool(RESEND_API_KEY),
        },
        "from": EMPIRE_FROM,
        "domain": ALLOWED_DOMAIN,
        "version": app.version,
    }


@app.post("/v1/notify/telegram")
def notify_telegram(p: NotifyPayload):
    r = _telegram_send(p.text, p.parse_mode)
    _log({"channel": "telegram", "ok": r["ok"],
          "source": p.source, "severity": p.severity,
          "preview": p.text[:80], "result": r})
    if not r["ok"]:
        raise HTTPException(502, detail=r)
    return {"ok": True, **r}


@app.post("/v1/notify/email")
def notify_email(p: EmailPayload):
    r = _resend_send(p.to, p.subject, p.body)
    _log({"channel": "email", "ok": r["ok"], "severity": p.severity,
          "to": p.to, "subject": p.subject, "result": r})
    if not r["ok"]:
        raise HTTPException(502, detail=r)
    return {"ok": True, **r}


@app.post("/v1/notify/alert")
def notify_alert(p: AlertPayload):
    """Paginate operator. Severity routes to channel(s).

    critical -> Telegram + Email
    high     -> Telegram + Email
    info     -> Telegram only
    low      -> Telegram only

    Telegram failure -> retry once -> fall back to Email.
    """
    severity = (p.severity or "info").lower()
    text = (f"<b>[{severity.upper()}] {p.title}</b>\n\n"
            f"<i>source: {p.source}</i>\n\n"
            f"{p.body[:3500]}")
    email_body = (f"[{severity.upper()}] {p.title}\n\n"
                  f"source: {p.source}\n\n{p.body}")
    sent = []

    if severity in ("critical", "high", "info", "low"):
        # Telegram
        t = _telegram_send(text)
        if not t["ok"]:
            t = _telegram_send(text)  # retry once
        _log({"channel": "telegram", "ok": t["ok"],
              "source": p.source, "severity": severity,
              "title": p.title, "result": t})
        sent.append({"channel": "telegram", **t})
        if not t["ok"] and severity in ("critical", "high"):
            # fall back to email
            e = _resend_send(ALERT_FALLBACK_EMAIL,
                             f"[{severity}] {p.title}", email_body)
            _log({"channel": "email", "ok": e["ok"], "fallback": True,
                  "source": p.source, "severity": severity,
                  "title": p.title, "result": e})
            sent.append({"channel": "email", "fallback": True, **e})

    if severity in ("critical", "high"):
        # Always also send email for critical/high
        e = _resend_send(ALERT_FALLBACK_EMAIL,
                         f"[{severity}] {p.title}", email_body)
        _log({"channel": "email", "ok": e["ok"], "source": p.source,
              "severity": severity, "title": p.title, "result": e})
        sent.append({"channel": "email", **e})

    any_ok = any(s.get("ok") for s in sent)
    return {"ok": any_ok, "severity": severity, "sent": sent}


@app.post("/v1/brief/daily")
def brief_daily():
    """Build today's brief from the hub, send to Telegram."""
    try:
        r = requests.get(f"{HUB_URL}/v1/ceo/brief", timeout=8)
        brief = r.json() if r.status_code == 200 else {}
    except Exception as e:
        brief = {"error": str(e)[:200]}

    if not brief:
        # fall back to a minimal text
        text = (f"<b>Empire OS — Daily Brief</b>\n"
                f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
                f"<i>Brief unavailable from hub.</i>")
    else:
        headline = brief.get("headline") or {}
        funnel = brief.get("funnel") or {}
        text = (
            f"<b>Empire OS — Daily Brief</b>\n"
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
            f"<b>Pipeline</b>\n"
            f"  Discovered: {funnel.get('discovered', 0)}\n"
            f"  Matched:    {funnel.get('matched', 0)}\n"
            f"  Drafted:    {funnel.get('outreach_drafted', 0)}\n"
            f"  Sent:       {funnel.get('outreach_sent', 0)}\n"
            f"  Replied:    {funnel.get('replied', 0)}\n"
            f"  Claimed:    {funnel.get('claimed', 0)}\n"
            f"  Settled:    {funnel.get('settled', 0)}\n\n"
            f"<b>Revenue</b>\n"
            f"  Gross:    ${headline.get('gross_cents', 0) / 100:.2f}\n"
            f"  Settled:  ${headline.get('settled_cents', 0) / 100:.2f}\n"
            f"  Deals:    {headline.get('settlement_count', 0)}\n"
        )

    t = _telegram_send(text)
    _log({"channel": "telegram", "ok": t["ok"],
          "kind": "daily_brief", "result": t})
    return {"ok": t["ok"], "result": t}


@app.get("/v1/notify/recent")
def notify_recent(n: int = 50):
    if not LOG_PATH.exists():
        return {"rows": []}
    lines = LOG_PATH.read_text().strip().splitlines()[-n:]
    rows = []
    for ln in lines:
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass
    return {"rows": rows[::-1]}  # newest first


@app.get("/v1/notify/stats")
def notify_stats():
    if not LOG_PATH.exists():
        return {"counts": {}, "total": 0}
    counts = Counter()
    total = 0
    for ln in LOG_PATH.read_text().strip().splitlines():
        try:
            e = json.loads(ln)
            counts[e.get("channel", "?")] += 1
            total += 1
        except Exception:
            pass
    return {"counts": dict(counts), "total": total}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("GATEWAY_PORT", "9100"))
    print(f"[{datetime.now(timezone.utc).isoformat()}] "
          f"hermes-gateway starting :{port}", flush=True)
    print(f"  telegram: token={'set' if TELEGRAM_BOT_TOKEN else 'MISSING'} "
          f"chat={'set' if TELEGRAM_CHAT_ID else 'MISSING'}", flush=True)
    print(f"  email:    resend={'set' if RESEND_API_KEY else 'MISSING'} "
          f"from={EMPIRE_FROM}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
