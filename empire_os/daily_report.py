#!/usr/bin/env python3
"""
Empire OS v3 — Daily Report (Host-side, using incus exec + sqlite3 CLI)
========================================================================
Runs on host, executes sqlite3 commands inside container via incus exec.
Avoids Python DB connection locks by using sqlite3 CLI which worked reliably.
"""

import json
import subprocess
import sys
import os
from datetime import datetime, date, timezone
from pathlib import Path

FEEDBACK = Path("/root/feedback")
FEEDBACK.mkdir(parents=True, exist_ok=True)

def run_sql(sql):
    """Run SQL in container via incus exec sqlite3."""
    cmd = ["incus", "exec", "empire-hub", "--", "sqlite3", "/root/empire_os/empire_os.db", sql]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Exception(f"SQL failed: {result.stderr}")
    return result.stdout.strip()

def run_json_sql(sql):
    """Run SQL with -json flag."""
    cmd = ["incus", "exec", "empire-hub", "--", "sqlite3", "-json", "/root/empire_os/empire_os.db", sql]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise Exception(f"JSON SQL failed: {result.stderr}")
    return result.stdout.strip()

def scalar(sql):
    return run_sql(sql)

# Collect all data
TOTAL_LEADS = scalar("SELECT COUNT(*) FROM lane_leads")
LAST_24H = scalar("SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 day') LIMIT 1000")
AVG_FIT = scalar("SELECT ROUND(AVG(MIN(100, MAX(0, icp_fit_score))), 1) FROM lane_leads WHERE icp_fit_score IS NOT NULL LIMIT 5000")
AVG_FIT = AVG_FIT if AVG_FIT else "0"

BY_TIER_JSON = run_json_sql("SELECT omega_tier, COUNT(*) as cnt FROM lane_leads GROUP BY omega_tier LIMIT 20")

A2A_TOTAL = scalar("SELECT COUNT(*) FROM buyer_leads LIMIT 1000")
A2A_DELIVERED = scalar("SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000")
A2A_LOCKED = scalar("SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000")
A2A_LOCKED = A2A_LOCKED if A2A_LOCKED else "0"

BUYERS_TOTAL = scalar("SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000")
BUYERS_PRICED = scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0 LIMIT 1000")
BUYERS_ENDPOINT = scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE endpoint_url != '' AND endpoint_url IS NOT NULL LIMIT 1000")

CHARGES_TOTAL = scalar("SELECT COUNT(*) FROM si_charges LIMIT 1000")
CHARGES_OPEN = scalar("SELECT COUNT(*) FROM si_charges WHERE status='open' LIMIT 1000")
CHARGES_PAID = scalar("SELECT COUNT(*) FROM si_charges WHERE status='paid' LIMIT 1000")
CHARGES_VAULT = scalar("SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) FROM si_charges WHERE status='paid' LIMIT 1000")
CHARGES_VAULT = CHARGES_VAULT if CHARGES_VAULT else "0"

SETTLEMENTS = scalar("SELECT COUNT(*) FROM si_settlements LIMIT 1000")

INVOICES_PENDING = scalar("SELECT COUNT(*) FROM si_invoice WHERE status='pending' LIMIT 1000")
INVOICES_PAID_TODAY = scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' AND DATE(paid_at)=DATE('now') LIMIT 1000")
INVOICES_PAID_TOTAL = scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' LIMIT 1000")

ACTIVE_SUBS = scalar("SELECT COUNT(*) FROM si_subscription WHERE status = 'active' AND price_cents > 0")

MRR_JSON = run_json_sql("""
    SELECT plan, billing_cycle, price_cents, COUNT(*) as subs
    FROM si_subscription
    WHERE status = 'active' AND price_cents > 0
    GROUP BY plan, billing_cycle, price_cents
""")

# Build report
report = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "date": date.today().isoformat(),
    "revenue_snapshot": {
        "leads": {
            "total": int(TOTAL_LEADS),
            "last_24h": int(LAST_24H),
            "avg_fit_score": float(AVG_FIT),
            "by_tier": json.loads(BY_TIER_JSON),
        },
        "a2a": {
            "total": int(A2A_TOTAL),
            "delivered_http_200": int(A2A_DELIVERED),
            "locked_usd": float(A2A_LOCKED),
        },
        "buyers": {
            "total": int(BUYERS_TOTAL),
            "priced": int(BUYERS_PRICED),
            "with_endpoint": int(BUYERS_ENDPOINT),
        },
        "charges": {
            "total": int(CHARGES_TOTAL),
            "open": int(CHARGES_OPEN),
            "paid": int(CHARGES_PAID),
            "vault_usdc": float(CHARGES_VAULT),
        },
        "settlements": {
            "rows": int(SETTLEMENTS),
        },
        "invoices": {
            "pending": int(INVOICES_PENDING),
            "paid_today": int(INVOICES_PAID_TODAY),
            "paid_total": int(INVOICES_PAID_TOTAL),
        },
        "mrr": {
            "active_subs": int(ACTIVE_SUBS),
            "by_plan": json.loads(MRR_JSON),
        }
    },
    "ts": datetime.now(timezone.utc).isoformat(),
    "date": date.today().isoformat(),
}

# Save
FEEDBACK = Path("/root/feedback")
FEEDBACK.mkdir(parents=True, exist_ok=True)
path = FEEDBACK / f"daily_report_{date.today().isoformat()}.json"
path.write_text(json.dumps(report, indent=2, default=str))
print(f"Saved: {path}")

# Print summary
RS = report["revenue_snapshot"]
print(f"""
═══════════════════════════════════════════
  EMPIRE OS v3 — DAILY REPORT
  {date.today().isoformat()} | {datetime.now(timezone.utc).isoformat()[:19]} UTC
═══════════════════════════════════════════

💰 REVENUE SNAPSHOT
  Total leads:     {RS['leads']['total']:,}  (24h: {RS['leads']['last_24h']:,})
  Avg fit score:   {RS['leads']['avg_fit_score']:.1f}/100
  A2A matches:     {RS['a2a']['total']:,}  |  Delivered: {RS['a2a']['delivered_http_200']:,}  |  Locked: ${RS['a2a']['locked_usd']:,.2f}
  Buyers priced:   {RS['buyers']['priced']:,}  |  Endpointed: {RS['buyers']['with_endpoint']:,}
  Charges paid:    {RS['charges']['paid']:,}  |  Vault USDC: ${RS['charges']['vault_usdc']:,.4f}
  Settlements:     {RS['settlements']['rows']:,}
  Invoices pending: {RS['invoices']['pending']:,}
  Active subs:     {RS['mrr']['active_subs']:,}
  MRR by plan:     {json.dumps(RS['mrr']['by_plan'])}
""")