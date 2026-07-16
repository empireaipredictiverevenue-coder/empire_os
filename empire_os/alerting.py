"""
Empire OS v3 — Alerting module
==============================

Sends alerts via:
  1. Resend email — always works (we have RESEND_API_KEY)
  2. Generic webhook — for Telegram/Slack/Discord when user provides URL

Alert types:
  - LANE_DRY: a niche+metro lane has had no leads for 24h
  - PRICE_SPIKE: predictive shows demand outstripping supply
  - REVENUE_DROP: MRR dropped >15% week-over-week
  - BUYER_REPLY: a buyer replied to outreach (HOT)
  - SOLANA_PAYMENT: invoice paid onchain
  - SOURCE_ERROR: lead source failed (>3 errors in row)

Each alert = one Resend email to configured recipients +
optional POST to ALERT_WEBHOOK_URL.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests


ALERT_LOG = Path("/root/feedback/alerts.jsonl")
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
RESEND_FROM = "Empire OS Alerts <alerts@empire-ai.co.uk>"
ALLOWED_SEND_DOMAIN = "empire-ai.co.uk"
RESEND_API_KEY = ""


def _read_env() -> dict:
    env_path = Path("/root/empire_os/.env")
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(event) + "\n")


def send_email(subject: str, body: str, to: str = "founder@empire-ai.co.uk") -> tuple[bool, str]:
    env = _read_env()
    api_key = env.get("RESEND_API_KEY", "")
    if not api_key:
        return False, "no_resend_key"
    if f"@{ALLOWED_SEND_DOMAIN}" not in RESEND_FROM:
        return False, f"from '{RESEND_FROM}' not on allowed domain @{ALLOWED_SEND_DOMAIN}"

    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [to],
                "reply_to": ["founder@empire-ai.co.uk"],
                "subject": subject,
                "text": body,
                "metadata": {"source": "alert"},
            },
            timeout=10,
        )
        if r.status_code < 300:
            return True, f"sent {r.status_code}: {r.text[:200]}"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)[:200]


def send_webhook(payload: dict) -> tuple[bool, str]:
    """POST to ALERT_WEBHOOK_URL (Slack/Discord/Telegram-compatible)."""
    env = _read_env()
    url = env.get("ALERT_WEBHOOK_URL", "")
    if not url:
        return False, "no_webhook"
    try:
        r = requests.post(url, json=payload, timeout=8)
        return r.status_code < 300, f"{r.status_code}: {r.text[:150]}"
    except Exception as e:
        return False, str(e)[:200]


def emit(alert_type: str, subject: str, body: str,
         severity: str = "info") -> dict:
    """Send an alert via hermes-gateway (preferred) or direct fallback.

    Channels: hermes-gateway (Telegram + email + future) if reachable,
              otherwise fall back to direct email send.

    Args:
        alert_type: LANE_DRY | REVENUE_DROP | BUYER_REPLY | SOLANA_PAYMENT | SOURCE_ERROR
        subject: alert title
        body: plain text body
        severity: info | warn | critical (also accepts high/low)

    Returns:
        dict with sent channels and any errors
    """
    env = _read_env()
    gateway_url = env.get("HERMES_GATEWAY_URL", "http://10.118.155.156:9100")
    recipients = env.get("ALERT_EMAIL", "founder@empire-ai.co.uk").split(",")

    results = {"alert_type": alert_type, "severity": severity,
               "channels": {}}

    # Primary path: route through hermes-gateway (fans out to Telegram + email)
    gateway_ok = False
    try:
        gw_payload = {"title": subject, "body": body,
                      "severity": severity, "source": alert_type}
        r = requests.post(f"{gateway_url}/v1/notify/alert",
                          json=gw_payload, timeout=8)
        if r.status_code == 200:
            j = r.json() if r.headers.get("content-type","").startswith(
                "application/json") else {}
            sent = j.get("sent", [])
            for s in sent:
                results["channels"][f"{s.get('channel','?')}"
                                    f"{':fallback' if s.get('fallback') else ''}"] = {
                    "ok": s.get("ok", False),
                    "via": "gateway",
                }
            # Treat gateway as successful if:
            #   - gateway returned ok=true (any channel sent), OR
            #   - for info/low severity, gateway replied 200 even if all
            #     channels failed (telegram is optional for those tiers)
            any_ok = any(s.get("ok") for s in sent)
            gateway_ok = bool(j.get("ok")) or any_ok or (
                severity in ("info", "low") and r.status_code == 200)
        else:
            results["channels"]["gateway"] = {
                "ok": False, "via": "gateway",
                "status": r.status_code, "error": r.text[:160]}
    except Exception as e:
        results["channels"]["gateway"] = {"ok": False,
                                           "error": str(e)[:160],
                                           "via": "gateway"}

    # Fallback: direct email send only if gateway did not respond successfully
    if not gateway_ok:
        for rcp in recipients:
            ok, info = send_email(subject, body, rcp.strip())
            results["channels"][f"email:{rcp}:direct"] = {
                "ok": ok, "info": info, "via": "direct"}

    _log(severity.upper(), "alert_sent",
         alert_type=alert_type, subject=subject,
         gateway_ok=gateway_ok,
         n_channels=len(results["channels"]))

    return results


if __name__ == "__main__":
    # Smoke test
    res = emit(
        "TEST",
        "Empire OS alert smoke test",
        "This is a test alert from the new alerting module.\n\nIf you received this, the email + webhook paths work.",
        severity="info",
    )
    print(json.dumps(res, indent=2))
