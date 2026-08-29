#!/usr/bin/env python3
"""revenue_digest — Daily snapshot summary for founder.

Composes a one-page text digest from /v1/revenue/snapshot + writes
to /root/feedback/revenue_digest.jsonl. Optionally emails to founder
via Brevo.

Wired by:
  empire-revenue-digest.{service,timer}  — daily 08:00 UTC
"""
from __future__ import annotations
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
DIGEST_PATH = FEEDBACK_DIR / "revenue_digest.jsonl"


def fetch_snapshot() -> dict:
    """Pull live snapshot from hub."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/v1/revenue/snapshot", timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def compose(snap: dict) -> str:
    """Compose plain-text digest for founder email."""
    k = snap.get("kpis", {})
    vault = snap.get("vault", {})
    a2a = snap.get("a2a", {})
    lease = snap.get("lease", {})
    aff = snap.get("affiliate", {})
    awaiting = snap.get("awaiting_outreach", {})

    lines = [
        "EMPIRE OS — DAILY REVENUE DIGEST",
        f"Generated: {snap.get('ts', datetime.now(timezone.utc).isoformat())}",
        "",
        "== LIVE KPIs ==",
        f"Vault balance:        ${vault.get('balance_usdc', 0):.4f} USDC",
        f"Real revenue:         ${k.get('total_real_revenue_usdc', 0):,.2f} USDC",
        f"Committed pipeline:    ${k.get('total_committed_pipeline_usdc', 0):,.2f} USDC",
        f"Outreach queued:       {k.get('outreach_opportunities', 0)} prospects",
        "",
        "== A2A ==",
        f"Quotes total:         {a2a.get('quotes_total', 0)}",
        f"  pending:            {a2a.get('quotes_pending', 0)} (${a2a.get('pending_revenue_usdc', 0):,.2f})",
        f"  funded:             {a2a.get('quotes_funded', 0)}",
        f"  released:           {a2a.get('quotes_released', 0)} (${a2a.get('released_revenue_usdc', 0):,.2f})",
        "",
        "== LEASES ==",
        f"Active leases:        {lease.get('active', 0)} (${lease.get('active_revenue_usdc', 0):,.2f})",
        f"Total reservations:   {lease.get('total_reservations', 0)} leads",
        "",
        "== AFFILIATE ==",
        f"Refs active:          {aff.get('refs_active', 0)}",
        f"Conversions:          {aff.get('conversions', 0)}",
        f"Pending payout:       ${aff.get('pending_payout_usdc', 0):,.2f}",
        f"Paid out:             ${aff.get('paid_out_usdc', 0):,.2f}",
        "",
        "== OUTREACH ==",
        f"Queued for outreach:  {awaiting.get('queued_for_outreach', 0)}",
        f"Potential revenue:    ${awaiting.get('potential_revenue_usdc', 0):,.2f}",
        "",
        "Next sweep: hourly (empire-payout-scheduler.timer)",
        "Next sales agent: hourly (empire-a2a-sales-agent.timer)",
        "Next awaiting outreach: every 4h (empire-awaiting-outreach.timer)",
    ]
    return "\n".join(lines)


def persist_digest(text: str, snap: dict) -> int:
    """Append to revenue_digest.jsonl."""
    record = {
        "ts": snap.get("ts", datetime.now(timezone.utc).isoformat()),
        "digest": text,
        "kpis": snap.get("kpis", {}),
    }
    with open(DIGEST_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return int(datetime.now(timezone.utc).timestamp())


def email_to_founder(text: str) -> dict:
    """Email digest to founder via Brevo (if key set)."""
    api_key = os.environ.get("BREVO_API_KEY", "")
    if not api_key:
        from pathlib import Path as P
        _bp = P("/root/empire_secrets/brevo_api_key")
        if _bp.exists():
            api_key = _bp.read_text().strip()
    if not api_key:
        return {"sent": False, "error": "no_brevo_key"}

    try:
        payload = {
            "sender": {"name": "Empire OS", "email": "founder@empire-ai.co.uk"},
            "to": [{"email": "founder@empire-ai.co.uk"}],
            "subject": "Empire OS — Daily Revenue Digest",
            "textContent": text,
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


def main():
    snap = fetch_snapshot()
    text = compose(snap)
    did = persist_digest(text, snap)
    email_result = email_to_founder(text)
    print(f"DIGEST #{did}")
    print(text)
    print()
    print(f"EMAIL: {email_result}")


if __name__ == "__main__":
    main()