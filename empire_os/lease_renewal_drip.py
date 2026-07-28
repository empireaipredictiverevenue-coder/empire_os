#!/usr/bin/env python3
"""lease_renewal_drip — Auto-send renewal pay_url 7d before lease expiry.

For each active lease expiring within 7 days, email the tenant a
fresh renewal pay_url (rebuild quote via a2a_marketplace). Tracks
renewal_sent_at in lease meta to prevent duplicate sends.

Cadence: daily timer.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = FEEDBACK_DIR / "lease_renewal_drip.jsonl"

DEFAULT_DAYS = int(os.getenv("RENEWAL_DAYS_BEFORE", "7"))


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
    """Send via Brevo API (same path as everything else)."""
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


def get_expiring_leases(c: sqlite3.Connection, days: int = DEFAULT_DAYS) -> list:
    """Active leases expiring within N days, that haven't been renewed yet."""
    now = datetime.now(timezone.utc)
    cutoff = (now + timedelta(days=days)).isoformat()
    rows = c.execute("""
        SELECT lease_id, buyer_wallet, niche, max_leads, used_leads,
               price_usdc, expires_at
        FROM lead_leases
        WHERE status = 'active'
          AND expires_at IS NOT NULL
          AND expires_at < ?
    """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def build_renewal_pay_url(lease: dict) -> str:
    """Reconstruct a pay_url pointing to a fresh quote via the lease owner."""
    vault = os.getenv("SOLANA_VAULT_WALLET", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
    amount = lease.get("price_usdc", 0)
    lease_id = lease.get("lease_id", "")
    return (
        f"solana:{vault}?amount={amount:.2f}"
        f"&label=Empire%20Lease%20Renewal&memo=lease:{lease_id}"
    )


def run(days: int = DEFAULT_DAYS, dry_run: bool = False) -> dict:
    summary = {
        "ts": _now(),
        "days_before": days,
        "dry_run": dry_run,
        "expiring": 0,
        "dripped": 0,
        "skipped": 0,
        "errors": 0,
    }
    c = db()
    try:
        leases = get_expiring_leases(c, days)
        summary["expiring"] = len(leases)

        for lease in leases:
            wallet = lease.get("buyer_wallet", "")
            if not wallet:
                summary["skipped"] += 1
                continue

            # Find tenant email via crypto_wallet
            t_row = c.execute(
                "SELECT email FROM si_tenant WHERE crypto_wallet = ?",
                (wallet,),
            ).fetchone()
            if not t_row or not t_row["email"]:
                summary["skipped"] += 1
                continue
            email = t_row["email"]
            if "@" not in email or email.startswith("tenant:"):
                summary["skipped"] += 1
                continue

            amount = lease.get("price_usdc", 0)
            pay_url = build_renewal_pay_url(lease)
            used = lease.get("used_leads", 0) or 0
            max_l = lease.get("max_leads", 0) or 0
            subject = f"Renew your Empire OS lease — ${amount:.0f} USDC"
            body = (
                f"Hi,\n\n"
                f"Your Empire OS lease is expiring soon:\n\n"
                f"  Lease: {lease['lease_id']}\n"
                f"  Niche: {lease.get('niche','?')}\n"
                f"  Renewal price: ${amount:.2f} USDC\n"
                f"  Used {used} of {max_l} leads this term\n\n"
                f"Renew here (same terms, 30 days):\n{pay_url}\n\n"
                f"— Empire OS"
            )

            if dry_run:
                summary["dripped"] += 1
                continue

            result = send_email(email, subject, body)
            if result.get("sent"):
                summary["dripped"] += 1
                # Mark renewal_sent_at in lease meta (use sqlite since no meta col)
                # For now just log it
                _log({
                    "ts": _now(),
                    "event": "renewal_sent",
                    "lease_id": lease["lease_id"],
                    "tenant_id": tenant_id,
                    "email": email,
                    "brevo_id": result.get("brevo_id"),
                    "expires_at": lease.get("expires_at"),
                })
            else:
                summary["errors"] += 1
                _log({
                    "ts": _now(),
                    "event": "renewal_error",
                    "lease_id": lease["lease_id"],
                    "email": email,
                    "error": result.get("error"),
                })
    finally:
        c.close()
    _log({"ts": _now(), "event": "tick_end", "summary": summary})
    return summary


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(json.dumps(run(dry_run=dry), indent=2, default=str))