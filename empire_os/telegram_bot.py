"""Telegram Bot — send Empire OS notifications, briefs, and alerts.

Usage:
    from empire_os.telegram_bot import send_brief, send_message
    send_brief(backend, token="...", chat_id="...")
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Optional

from empire_os.ceo import build_brief
from empire_os.funnel import SQLiteBackend

logger = logging.getLogger("telegram_bot")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _post(token: str, method: str, payload: dict) -> dict:
    """Send a Telegram API call."""
    url = TELEGRAM_API.format(token=token, method=method)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        logger.warning("Telegram API call failed: %s", e)
        return {"ok": False, "error": str(e)}


def send_message(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> dict:
    """Send a plain text message to a Telegram chat."""
    return _post(token, "sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })


def build_brief_text(backend: SQLiteBackend) -> str:
    """Build a formatted CEO brief text for Telegram."""
    brief = build_brief(backend)
    funnel = brief.funnel if hasattr(brief, 'funnel') else {}
    headline = brief.headline if hasattr(brief, 'headline') else {}

    text = (
        "<b>Empire OS v3 — Daily Brief</b>\n"
        f"📅 {brief.date if hasattr(brief, 'date') else 'today'}\n\n"
        f"<b>Pipeline</b>\n"
        f"  Discovered: {funnel.get('discovered', 0)}\n"
        f"  Matched: {funnel.get('matched', 0)}\n"
        f"  Drafted: {funnel.get('outreach_drafted', 0)}\n"
        f"  Sent: {funnel.get('outreach_sent', 0)}\n"
        f"  Replied: {funnel.get('replied', 0)}\n"
        f"  Claimed: {funnel.get('claimed', 0)}\n"
        f"  Settled: {funnel.get('settled', 0)}\n\n"
        f"<b>Revenue</b>\n"
        f"  Gross: ${headline.get('gross_cents', 0) / 100:.2f}\n"
        f"  Settled: ${headline.get('settled_cents', 0) / 100:.2f}\n"
        f"  Deals: {headline.get('settlement_count', 0)}\n\n"
    )

    # Add decisions
    decisions = brief.decisions if hasattr(brief, 'decisions') else []
    if decisions:
        text += "<b>Actions</b>\n"
        for d in decisions[:5]:
            text += f"  ⚡ {d.summary[:100]}\n"

    text += (
        f"\n<i>AI Agentic Engine · {os.environ.get('EMPIRE_HOST', 'localhost')}</i>"
    )
    return text


def send_brief(
    backend: SQLiteBackend,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> dict:
    """Build and send the CEO brief to Telegram."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}

    text = build_brief_text(backend)
    return send_message(token, chat_id, text)


def send_alert(
    message: str,
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> dict:
    """Send an alert message to Telegram."""
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return {"ok": False, "error": "Token/chat not configured"}
    return send_message(token, chat_id, f"🚨 <b>Alert</b>\n{message}")
