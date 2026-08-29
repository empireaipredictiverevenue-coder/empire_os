#!/usr/bin/env python3
"""Empire OS — Professional Telegram Bot with Webhooks.

Features:
- Two-way communication: receive commands, send revenue snapshots
- Professional formatting with emojis
- Webhook endpoint for receiving messages
- Command routing: /revenue, /pipeline, /status, /help
- Revenue-only mode support
- Automatic webhook registration

Run: /root/venv/bin/python3 /root/empire_os/empire_os/telegram_pro_bot.py
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import sys
import urllib.request
import urllib.error
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

sys.path.insert(0, "/root/empire_os")

from empire_os.telegram_bot import send_message as _send_message
from empire_os.funnel import SQLiteBackend
from empire_os.ceo import build_brief

# ── config ──────────────────────────────────────────────────────────────
TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")  # e.g. https://empire-ai.co.uk/telegram/webhook
MONEY_ONLY = os.environ.get("TELEGRAM_MONEY_ONLY", "0") == "1"

DB_PATH = "/root/empire_os/empire_os.db"
ACTIONS_LOG = Path("/root/empire_os/feedback/telegram_actions.jsonl")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_pro")

app = FastAPI(title="Empire OS Telegram Pro Bot", version="1.0.0")


# ── helpers ─────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_action(action: str, detail: dict) -> None:
    entry = {"ts": _now(), "action": action}
    entry.update(detail)
    try:
        ACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ACTIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _post(method: str, payload: dict) -> dict:
    if not TOKEN:
        return {"ok": False, "error": "TOKEN not set"}
    url = TELEGRAM_API.format(token=TOKEN, method=method)
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning("Telegram API %s failed: %s", method, e)
        return {"ok": False, "error": str(e)}


def send_pro(text: str, parse_mode: str = "HTML") -> dict:
    """Send message with professional formatting."""
    if not TOKEN or not CHAT_ID:
        return {"ok": False, "error": "TOKEN/CHAT_ID not set"}
    return _post("sendMessage", {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })


# ── formatters ──────────────────────────────────────────────────────────
def fmt_revenue_snapshot() -> str:
    """Build professional revenue snapshot."""
    cnx = sqlite3.connect(DB_PATH, timeout=20)
    try:
        # revenue data
        settled = cnx.execute(
            "SELECT COALESCE(SUM(amount_cents),0) FROM si_invoice WHERE status='paid'").fetchone()[0]
        open_inv = cnx.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM si_invoice WHERE status='open'").fetchone()
        # funnel - use actual lane_leads statuses + funnel states
        funnel = {}
        # lane_leads actual statuses
        for state in ('new','pending','delivered','qualified','matched','outreach_drafted','outreach_sent','replied','claimed','settled','billed','collected','done'):
            funnel[state] = cnx.execute(
                f"SELECT COUNT(*) FROM lane_leads WHERE status='{state}'"
            ).fetchone()[0]
        # buyers
                buyers = cnx.execute(
                    "SELECT COUNT(DISTINCT email) FROM si_buyer_outreach WHERE email NOT LIKE '%example%' AND email NOT LIKE '%v.co%'"
                ).fetchone()[0]
        outbox = cnx.execute(
            "SELECT status, COUNT(*) FROM si_outbox GROUP BY status").fetchall()
    finally:
        cnx.close()

    settled_usd = settled / 100.0
    open_count, open_amt = open_inv[0], open_inv[1] / 100.0 if open_inv[1] else 0

    lines = [
        "🏛 <b>Empire OS — Revenue Snapshot</b>",
        f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "💰 <b>Revenue</b>",
        f"  ✅ Settled: <b>${settled_usd:,.2f}</b> USDT (BSC)",
        f"  📋 Open Invoices: {open_count} (${open_amt:,.2f})",
        "",
        "📊 <b>Pipeline</b>",
        f"  🔍 Discovered: {funnel.get('discovered', 0):,}",
        f"  🎯 Matched: {funnel.get('matched', 0):,}",
        f"  ✏️ Drafted: {funnel.get('outreach_drafted', 0):,}",
        f"  📤 Sent: {funnel.get('outreach_sent', 0):,}",
        f"  💬 Replied: {funnel.get('replied', 0):,}",
        f"  ✋ Claimed: {funnel.get('claimed', 0):,}",
        f"  💎 Settled: {funnel.get('settled', 0):,}",
        "",
        "🤝 <b>Buyers & Outreach</b>",
        f"  👥 Active Buyer Prospects: {buyers}",
        f"  📬 Outbox: {dict(outbox)}",
        "",
        "🤖 <i>Empire OS v3 · Automated Agentic Engine</i>",
    ]
    return "\n".join(lines)


def fmt_pipeline_snapshot() -> str:
    """Pipeline with conversion rates."""
    cnx = sqlite3.connect(DB_PATH, timeout=20)
    try:
        stages = {}
        for s in ('discovered','matched','outreach_drafted','outreach_sent','replied','claimed','settled'):
            stages[s] = cnx.execute(
                f"SELECT COUNT(*) FROM lane_leads WHERE status='{s}'").fetchone()[0]
        # niche breakdown
        niches = cnx.execute(
            "SELECT niche, COUNT(*) FROM lane_leads WHERE status='pending' GROUP BY 1 ORDER BY 2 DESC LIMIT 8").fetchall()
    finally:
        cnx.close()

    lines = ["📈 <b>Pipeline Health</b>", f"📅 {datetime.now(timezone.utc).strftime('%H:%M UTC')}", ""]
    prev = stages.get('discovered', 0)
    for s in ('matched','outreach_drafted','outreach_sent','replied','claimed','settled'):
        cur = stages.get(s, 0)
        rate = (cur / prev * 100) if prev > 0 else 0
        emoji = {'matched':'🎯','outreach_drafted':'✏️','outreach_sent':'📤','replied':'💬','claimed':'✋','settled':'💎'}[s]
        lines.append(f"  {emoji} {s.replace('_',' ').title()}: {cur:,} ({rate:.1f}%)")
        prev = cur

    if niches:
        lines.append("")
        lines.append("🏷 <b>Top Niches (pending)</b>")
        for n, c in niches:
            lines.append(f"  • {n}: {c:,}")

    lines.append("")
    lines.append("🤖 <i>Empire OS v3</i>")
    return "\n".join(lines)


def fmt_status_snapshot() -> str:
    """System health status."""
    # check services
    import subprocess
    result = subprocess.run(
        ["systemctl", "list-units", "--type=service", "--state=failed", "--no-legend"],
        capture_output=True, text=True, timeout=10)
    failed = [l.split()[0] for l in result.stdout.strip().splitlines() if l]

    cnx = sqlite3.connect(DB_PATH, timeout=20)
    try:
        db_size = os.path.getsize(DB_PATH) / (1024**2)
        wal_size = 0
        try:
            wal_size = os.path.getsize(DB_PATH + "-wal") / (1024**2)
        except OSError:
            pass
    finally:
        cnx.close()

    lines = [
        "⚙️ <b>System Status</b>",
        f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"💾 DB: {db_size:.1f} MB  WAL: {wal_size:.1f} MB",
        f"❌ Failed Services: {len(failed)}",
    ]
    if failed:
        lines.append("  " + "\n  ".join(failed[:10]))
    else:
        lines.append("  ✅ All services healthy")
    lines.append("")
    lines.append("🤖 <i>Empire OS v3</i>")
    return "\n".join(lines)


# ── command router ──────────────────────────────────────────────────────
def handle_command(cmd: str, user_id: int) -> str:
    """Route slash commands to formatters."""
    cmd = cmd.lower().strip()

    if cmd in ("/start", "/help"):
        return (
            "🏛 <b>Empire OS — Telegram Pro</b>\n\n"
            "Commands:\n"
            "  /revenue — 💰 Revenue snapshot (settled USDT, open invoices)\n"
            "  /pipeline — 📈 Pipeline health with conversion rates\n"
            "  /status — ⚙️ System health (services, DB, WAL)\n"
            "  /brief — 📋 CEO daily brief from hub\n"
            "  /help — This message\n\n"
            "🔒 Revenue-only mode: " + ("ON" if MONEY_ONLY else "OFF") + "\n"
            "🤖 <i>Empire OS v3</i>"
        )

    if cmd == "/revenue":
        return fmt_revenue_snapshot()

    if cmd == "/pipeline":
        return fmt_pipeline_snapshot()

    if cmd == "/status":
        return fmt_status_snapshot()

    if cmd == "/brief":
        # fetch from hub
        import requests
        try:
            r = requests.get("http://10.118.155.218:8081/v1/ceo/brief", timeout=8)
            brief = r.json() if r.status_code == 200 else {}
        except Exception:
            brief = {}

        if not brief:
            return "⚠️ Brief unavailable from hub."

        headline = brief.get("headline") or {}
        funnel = brief.get("funnel") or {}
        return (
            f"📋 <b>CEO Brief</b>\n"
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
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
            f"🤖 <i>Empire OS v3</i>"
        )

    return "❓ Unknown command. Use /help."


# ── webhook endpoint ────────────────────────────────────────────────────
class Update(BaseModel):
    update_id: int
    message: dict | None = None
    edited_message: dict | None = None


@app.post("/telegram/webhook")
async def webhook(update: Update, request: Request):
    """Receive Telegram updates."""
    # verify secret
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET and secret != WEBHOOK_SECRET:
        raise HTTPException(401, "Invalid webhook secret")

    msg = update.message or update.edited_message
    if not msg:
        return {"ok": True}

    chat_id = str(msg.get("chat", {}).get("id", ""))
    user_id = msg.get("from", {}).get("id", 0)
    text = msg.get("text", "").strip()

    # only allow configured chat
    if CHAT_ID and chat_id != CHAT_ID:
        logger.warning("Unauthorized chat: %s", chat_id)
        return {"ok": True}

    _log_action("inbound", {"chat_id": chat_id, "user_id": user_id, "text": text[:100]})

    # handle commands
    if text.startswith("/"):
        response = handle_command(text.split()[0], user_id)
        send_pro(response)
        return {"ok": True}

    # echo non-commands with help hint
    send_pro("💬 Use /help for commands. Revenue-only mode: " + ("ON" if MONEY_ONLY else "OFF"))
    return {"ok": True}


@app.get("/telegram/webhook")
async def webhook_verify():
    return {"status": "Empire OS Telegram Pro webhook ready"}


@app.post("/telegram/set_webhook")
async def set_webhook():
    """Register webhook with Telegram."""
    if not WEBHOOK_URL:
        raise HTTPException(400, "TELEGRAM_WEBHOOK_URL not set")
    payload = {"url": WEBHOOK_URL}
    if WEBHOOK_SECRET:
        payload["secret_token"] = WEBHOOK_SECRET
    result = _post("setWebhook", payload)
    _log_action("set_webhook", {"result": result})
    return result


@app.post("/telegram/delete_webhook")
async def delete_webhook():
    result = _post("deleteWebhook", {})
    return result


@app.get("/telegram/webhook_info")
async def webhook_info():
    return _post("getWebhookInfo", {})


# ── scheduled: daily revenue snapshot ──────────────────────────────────
async def run_polling():
    """Long polling fallback when webhook DNS not ready."""
    offset = 0
    consecutive_errors = 0
    while True:
        try:
            result = _post("getUpdates", {"offset": offset, "timeout": 10, "allowed_updates": ["message"]})
            if result.get("ok"):
                consecutive_errors = 0
                for update in result["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update:
                        msg = update["message"]
                        chat_id = str(msg["chat"]["id"])
                        text = msg.get("text", "")
                        if text.startswith("/"):
                            response = handle_command(text, msg["from"]["id"])
                            send_pro(response)
            else:
                consecutive_errors += 1
                if consecutive_errors > 3:
                    logger.warning(f"Polling: {result}")
                    consecutive_errors = 0
        except Exception as e:
            logger.warning(f"Polling error: {e}")
        await asyncio.sleep(1)


@app.on_event("startup")
async def startup():
    _log_action("startup", {"version": "1.0.0", "money_only": MONEY_ONLY})
    if WEBHOOK_URL:
        await set_webhook()
    else:
        # Start polling fallback
        asyncio.create_task(run_polling())


# ── run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("TELEGRAM_PRO_PORT", "9103"))
    print(f"[{_now()}] telegram-pro starting :{port}")
    print(f"  token={'set' if TOKEN else 'MISSING'} chat={'set' if CHAT_ID else 'MISSING'}")
    print(f"  webhook_url={WEBHOOK_URL or 'NOT SET'}")
    print(f"  money_only={MONEY_ONLY}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")