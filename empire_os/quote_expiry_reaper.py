#!/usr/bin/env python3
"""quote_expiry_reaper — Send 1 reminder, then mark A2A quotes as expired.

Lifecycle:
  - quote created (status=pending, expires_at=now+30min)
  - 20min in: send 1 reminder email ("expires in ~10 min")
  - expires_at passed: status → expired
  - this is what recovery_sequence (a2a branch) does NOT yet cover

Idempotent: only sends reminder once per quote (tracks via meta field
'reminder_sent_at'). Only flips status=pending → expired.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "quote_expiry_reaper.jsonl"

REMINDER_MIN_BEFORE_EXPIRY = int(os.getenv("REMINDER_MIN_BEFORE", "10"))  # send when 10min remain
DEFAULT_BATCH = int(os.getenv("REAPER_BATCH", "200"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    return c


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def send_email(to_email: str, subject: str, body: str) -> dict:
    """Send via Brevo API (same path as a2a_sales_agent)."""
    api_key = os.getenv("BREVO_API_KEY", "")
    if not api_key:
        from pathlib import Path as P
        bp = P("/root/empire_secrets/brevo_api_key")
        if bp.exists():
            api_key = bp.read_text().strip()
    if not api_key:
        return {"sent": False, "error": "no_brevo_key"}
    sender = os.getenv("EMPIRE_FROM", "Empire OS <founder@empire-ai.co.uk>")
    sender_email = sender.split("<")[-1].rstrip(">") if "<" in sender else sender
    try:
        payload = {
            "sender": {"name": "Empire OS", "email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body,
        }
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "api-key": api_key},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
            return {"sent": True, "brevo_id": resp.get("messageId", "")}
    except Exception as e:
        return {"sent": False, "error": str(e)[:200]}


def get_due_quotes(c: sqlite3.Connection) -> list:
    """Quotes that need reminder OR are past expiry.

    Reminder: status=pending AND expires_at between now+1min and now+15min
               AND meta doesn't already have reminder_sent_at
    Expire:  status=pending AND expires_at < now
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    reminder_window_end = (
        datetime.now(timezone.utc) + timedelta(minutes=REMINDER_MIN_BEFORE_EXPIRY)
    ).isoformat()

    # Reminder candidates: expiring within the next X minutes
    rows = c.execute("""
        SELECT quote_id, product, quantity, amount_usdc,
               buyer_wallet, expires_at, meta
        FROM a2a_quotes
        WHERE status = 'pending'
          AND expires_at IS NOT NULL
          AND expires_at > ?
          AND expires_at < ?
          AND (meta IS NULL OR meta NOT LIKE '%reminder_sent_at%')
    """, (now_iso, reminder_window_end)).fetchall()

    # Expire candidates: past expiry
    expired = c.execute("""
        SELECT quote_id, product, amount_usdc, buyer_wallet, expires_at, meta
        FROM a2a_quotes
        WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < ?
    """, (now_iso,)).fetchall()
    return [dict(r) for r in rows], [dict(r) for r in expired]


def extract_prospect_email(meta_json: str) -> str:
    if not meta_json:
        return ""
    try:
        md = json.loads(meta_json)
        return md.get("prospect_email", "")
    except Exception:
        return ""


def extract_pay_url(meta_json: str, quote_id: str, amount_usdc: float) -> str:
    """Pull pay_url from meta, or reconstruct from vault + quote_id."""
    if meta_json:
        try:
            md = json.loads(meta_json)
            url = md.get("pay_url", "")
            if url:
                return url
        except Exception:
            pass
    # Reconstruct: vault + amount + memo a2a:q_xxx
    vault = os.getenv("SOLANA_VAULT_WALLET", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
    return (
        f"solana:{vault}?amount={amount_usdc:.2f}"
        f"&label=Empire%20A2A&memo=a2a:{quote_id}"
    )


def run(batch: int = DEFAULT_BATCH, dry_run: bool = False) -> dict:
    summary = {
        "ts": _now(),
        "batch": batch,
        "dry_run": dry_run,
        "reminders_sent": 0,
        "reminders_skipped": 0,
        "quotes_expired": 0,
        "errors": 0,
    }
    c = db()
    try:
        reminders, expired = get_due_quotes(c)
        summary["reminders_due"] = len(reminders)
        summary["expired_due"] = len(expired)

        # 1. Send reminders
        for q in reminders[:batch]:
            email = extract_prospect_email(q.get("meta", ""))
            if not email or "@" not in email:
                summary["reminders_skipped"] += 1
                continue
            amount = q.get("amount_usdc", 0)
            pay_url = extract_pay_url(q.get("meta", ""), q["quote_id"], amount)
            subject = f"Reminder: your ${amount:.0f} USDC offer expires in ~{REMINDER_MIN_BEFORE_EXPIRY} min"
            body = (
                f"Hi,\n\nYour Empire OS offer is still pending:\n\n"
                f"  Amount: ${amount:.2f} USDC\n"
                f"  Quote: {q['quote_id']}\n"
                f"  Product: {q.get('product','?')}\n\n"
                f"Pay here before it expires:\n{pay_url}\n\n"
                f"— Empire OS"
            )
            if not dry_run:
                result = send_email(email, subject, body)
                if result.get("sent"):
                    summary["reminders_sent"] += 1
                    # Mark reminder_sent_at in meta
                    cur_meta = q.get("meta", "{}")
                    try:
                        md = json.loads(cur_meta) if cur_meta else {}
                    except Exception:
                        md = {}
                    md["reminder_sent_at"] = _now()
                    c.execute(
                        "UPDATE a2a_quotes SET meta=? WHERE quote_id=?",
                        (json.dumps(md), q["quote_id"]),
                    )
                    c.commit()
                else:
                    summary["errors"] += 1
            else:
                summary["reminders_sent"] += 1

        # 2. Expire past-due quotes
        for q in expired[:batch]:
            if not dry_run:
                c.execute(
                    "UPDATE a2a_quotes SET status='expired' WHERE quote_id=?",
                    (q["quote_id"],),
                )
                c.commit()
            summary["quotes_expired"] += 1

        _log({"ts": _now(), "event": "tick_end", "summary": summary})
    finally:
        c.close()
    return summary


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(json.dumps(run(dry_run=dry), indent=2, default=str))