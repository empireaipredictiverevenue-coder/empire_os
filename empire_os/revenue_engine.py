#!/usr/bin/env python3
"""revenue_engine — Unifies outreach + conversion tracking + snapshots.

Single source for revenue-related operations:
- AEO click auto-conversion: track ?ref= → call affiliate.record_conversion
- Awaiting-subs outreach: quote + email the 1187 awaiting_payment tenants
- Revenue snapshot: dump live state to /root/feedback/revenue.jsonl

Hub endpoints added:
  GET  /v1/revenue/snapshot          - live JSON snapshot of all revenue
  POST /v1/revenue/snapshot/persist  - write snapshot to feedback/revenue.jsonl
  POST /v1/revenue/awaiting/run      - outreach batch to awaiting subs
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
FEEDBACK_DIR = Path(os.getenv("FEEDBACK_DIR", "/root/empire_os/feedback"))
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH = FEEDBACK_DIR / "revenue.jsonl"


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    c.row_factory = sqlite3.Row
    return c


def snapshot() -> dict:
    """Live revenue snapshot across all surfaces."""
    c = db()
    s = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "vault": {},
        "settlements": {},
        "a2a": {},
        "lease": {},
        "affiliate": {},
        "aeo": {},
        "awaiting_outreach": {},
    }

    # Vault live
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8081/v1/health/deep", timeout=5) as r:
            d = json.loads(r.read())
            rpc = d.get("checks", {}).get("chain", {}).get("rpc", {})
            s["vault"] = {
                "balance_usdc": rpc.get("vault_balance_usdc", 0),
                "token_accounts": rpc.get("token_accounts", 0),
            }
    except Exception as e:
        s["vault"] = {"error": str(e)[:100]}

    # Settlements
    try:
        s["settlements"] = {
            "si_charges_succeeded": c.execute(
                "SELECT COUNT(*) FROM si_charges WHERE status='succeeded'"
            ).fetchone()[0],
            "si_settlements_total_cents": c.execute(
                "SELECT COALESCE(SUM(amount_cents),0) FROM si_settlements"
            ).fetchone()[0],
            "ppc_paid": c.execute(
                "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='paid'"
            ).fetchone()[0],
            "ppc_open": c.execute(
                "SELECT COUNT(*) FROM si_ppc_invoices WHERE status='open'"
            ).fetchone()[0],
            "subs_awaiting_payment": c.execute(
                "SELECT COUNT(*) FROM si_subscription WHERE status='awaiting_payment'"
            ).fetchone()[0],
            "subs_active": c.execute(
                "SELECT COUNT(*) FROM si_subscription WHERE status='active'"
            ).fetchone()[0],
        }
    except Exception as e:
        s["settlements"] = {"error": str(e)[:100]}

    # A2A
    try:
        s["a2a"] = {
            "quotes_total": c.execute("SELECT COUNT(*) FROM a2a_quotes").fetchone()[0],
            "quotes_pending": c.execute("SELECT COUNT(*) FROM a2a_quotes WHERE status='pending'").fetchone()[0],
            "quotes_funded": c.execute("SELECT COUNT(*) FROM a2a_quotes WHERE status='funded'").fetchone()[0],
            "quotes_released": c.execute("SELECT COUNT(*) FROM a2a_quotes WHERE status='released'").fetchone()[0],
            "released_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_usdc),0) FROM a2a_quotes WHERE status='released'"
            ).fetchone()[0],
            "pending_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_usdc),0) FROM a2a_quotes WHERE status IN ('pending','funded')"
            ).fetchone()[0],
        }
    except Exception as e:
        s["a2a"] = {"error": str(e)[:100]}

    # Lease
    try:
        s["lease"] = {
            "active": c.execute("SELECT COUNT(*) FROM lead_leases WHERE status='active'").fetchone()[0],
            "active_revenue_usdc": c.execute(
                "SELECT COALESCE(SUM(price_usdc),0) FROM lead_leases WHERE status='active'"
            ).fetchone()[0],
            "total_reservations": c.execute(
                "SELECT COALESCE(SUM(max_leads),0) FROM lead_leases WHERE status='active'"
            ).fetchone()[0],
        }
    except Exception as e:
        s["lease"] = {"error": str(e)[:100]}

    # Affiliate
    try:
        s["affiliate"] = {
            "refs_active": c.execute("SELECT COUNT(*) FROM affiliate_refs WHERE active=1").fetchone()[0],
            "conversions": c.execute("SELECT COUNT(*) FROM affiliate_conversions").fetchone()[0],
            "pending_payout_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM affiliate_ledger WHERE status='pending'"
            ).fetchone()[0],
            "paid_out_usdc": c.execute(
                "SELECT COALESCE(SUM(amount_cents),0)/100.0 FROM affiliate_ledger WHERE status='paid'"
            ).fetchone()[0],
        }
    except Exception as e:
        s["affiliate"] = {"error": str(e)[:100]}

    # AEO
    try:
        s["aeo"] = {
            "impressions_24h": c.execute(
                "SELECT COUNT(*) FROM aeo_events WHERE event_type='impression' AND ts >= datetime('now','-1 day')"
            ).fetchone()[0],
            "clicks_24h": c.execute(
                "SELECT COUNT(*) FROM aeo_events WHERE event_type='click' AND ts >= datetime('now','-1 day')"
            ).fetchone()[0],
        }
    except Exception as e:
        s["aeo"] = {"error": str(e)[:100]}

    # Awaiting outreach potential
    try:
        rows = c.execute("""
            SELECT s.tenant_id, s.plan, s.price_cents, s.per_lead_cents,
                   t.email, t.crypto_wallet, t.niche, t.api_key
            FROM si_subscription s
            LEFT JOIN si_tenant t ON s.tenant_id = t.tenant_id
            WHERE s.status='awaiting_payment'
              AND t.email IS NOT NULL AND t.email != ''
              AND t.email NOT LIKE 'dc-%' AND t.email NOT LIKE '%@v.co'
            ORDER BY s.created_at DESC
            LIMIT 500
        """).fetchall()
        s["awaiting_outreach"] = {
            "queued_for_outreach": len(rows),
            "potential_revenue_usdc": sum(r["price_cents"] or 0 for r in rows) / 100.0,
        }
    except Exception as e:
        s["awaiting_outreach"] = {"error": str(e)[:100]}

    c.close()

    # Roll-up KPIs
    s["kpis"] = {
        "total_real_revenue_usdc": (
            s.get("a2a", {}).get("released_revenue_usdc", 0)
        ),
        "total_committed_pipeline_usdc": (
            s.get("a2a", {}).get("pending_revenue_usdc", 0)
            + s.get("lease", {}).get("active_revenue_usdc", 0)
        ),
        "outreach_opportunities": s.get("awaiting_outreach", {}).get("queued_for_outreach", 0),
        "vault_live_usdc": s.get("vault", {}).get("balance_usdc", 0),
    }
    return s


def persist(snap: dict) -> int:
    """Append snapshot to feedback/revenue.jsonl, return id."""
    line = json.dumps(snap, default=str)
    with open(JSONL_PATH, "a") as f:
        f.write(line + "\n")
    return int(datetime.now(timezone.utc).timestamp())


def awaiting_subs_outreach(batch: int = 10, dry_run: bool = False) -> dict:
    """Quote + email awaiting_payment tenants via a2a_sales_agent.

    Returns summary.
    """
    from empire_os.a2a_sales_agent import _ollama_chat, send_quote_email
    summary = {"ts": datetime.now(timezone.utc).isoformat(),
               "batch": batch, "dry_run": dry_run,
               "scanned": 0, "quoted": 0, "emailed": 0, "errors": 0}

    c = db()
    rows = c.execute("""
        SELECT s.subscription_id as sub_id, s.tenant_id, s.plan, s.price_cents,
               s.per_lead_cents, t.email, t.niche, t.crypto_wallet, t.api_key
        FROM si_subscription s
        LEFT JOIN si_tenant t ON s.tenant_id = t.tenant_id
        WHERE s.status='awaiting_payment'
          AND t.email IS NOT NULL AND t.email != ''
          AND t.email NOT LIKE 'dc-%' AND t.email NOT LIKE '%@v.co'
        ORDER BY s.created_at DESC
        LIMIT ?
    """, (batch,)).fetchall()
    c.close()
    summary["scanned"] = len(rows)

    for r in rows:
        try:
            rd = dict(r)
            email = rd.get("email", "")
            if not email:
                continue
            # Build a pay_url directly — skip the create_quote signing flow for speed
            # (awaiting subs already have known price; just email them the price + memo)
            vault = os.getenv("SOLANA_VAULT_WALLET", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
            amount = (rd.get("price_cents") or 0) / 100.0
            if amount <= 0:
                amount = 599.0  # silver default
            sub_id = rd.get("sub_id", "")
            memo = f"sub:{sub_id}"
            pay_url = f"solana:{vault}?amount={amount:.2f}&label=Empire%20OS&memo={memo}"

            subject = f"Complete your Empire OS subscription — ${amount:.0f} USDC"
            body = (
                f"Hi,\n\n"
                f"You started an Empire OS subscription but didn't complete payment.\n\n"
                f"  Plan: {rd.get('plan','silver')}\n"
                f"  Amount: ${amount:.2f} USDC\n"
                f"  Subscription: {sub_id}\n\n"
                f"Complete payment here:\n{pay_url}\n\n"
                f"After payment, your seat activates immediately and leads start flowing.\n\n"
                f"— Empire OS\n"
            )

            if dry_run:
                summary["quoted"] += 1
                summary["emailed"] += 1
                continue

            # Send via Brevo
            r2 = send_quote_email(
                {"product": rd.get("plan", "subscription"),
                 "amount_usdc": amount,
                 "pay_url": pay_url,
                 "quote_id": sub_id,
                 "expires_at": "open"},
                {"email": email},
            )
            if r2.get("sent"):
                summary["emailed"] += 1
                summary["quoted"] += 1
            else:
                summary["errors"] += 1
        except Exception as e:
            summary["errors"] += 1

    return summary


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "outreach":
        batch = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        dry = "--dry-run" in sys.argv
        print(json.dumps(awaiting_subs_outreach(batch, dry), indent=2))
    else:
        s = snapshot()
        persist(s)
        print(json.dumps(s, indent=2, default=str))