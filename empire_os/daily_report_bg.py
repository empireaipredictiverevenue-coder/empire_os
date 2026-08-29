#!/usr/bin/env python3
"""
Empire OS v3 — Daily Report Runner (Background)
================================================
Runs the report in background inside container, writes result to file.
We'll poll for completion.
"""

import json
import sqlite3
import sys
import os
from datetime import datetime, date, timezone

DB = "/root/empire_os/empire_os.db"
OUTPUT = "/root/feedback/daily_report_latest.json"

def ro_conn():
    c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True, timeout=60)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA busy_timeout=30000')
    return c

def scalar(sql):
    c = ro_conn()
    try:
        cur = c.execute(sql)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        c.close()

def rows(sql):
    c = ro_conn()
    try:
        cur = c.execute(sql)
        return [dict(r) for r in cur.fetchall()]
    finally:
        c.close()

report = {"ts": datetime.now(timezone.utc).isoformat(), "date": date.today().isoformat()}

# ── REVENUE SNAPSHOT ──
RS = {}

RS["leads"] = {
    "total": scalar("SELECT COUNT(*) FROM lane_leads"),
    "last_24h": scalar("SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 day') LIMIT 1000"),
    "by_tier": {r["omega_tier"]: r["cnt"] for r in ro_conn().execute("SELECT omega_tier, COUNT(*) as cnt FROM lane_leads GROUP BY omega_tier LIMIT 20").fetchall() if r["omega_tier"]},
    "avg_fit_score": scalar("SELECT ROUND(AVG(MIN(100, MAX(0, icp_fit_score))), 1) FROM lane_leads WHERE icp_fit_score IS NOT NULL LIMIT 5000") or 0,
}

RS["a2a"] = {
    "total": scalar("SELECT COUNT(*) FROM buyer_leads LIMIT 1000"),
    "delivered_http_200": scalar("SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000"),
    "locked_usd": scalar("SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000") or 0,
}

RS["buyers"] = {
    "total": scalar("SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000"),
    "priced": scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0 LIMIT 1000"),
    "with_endpoint": scalar("SELECT COUNT(*) FROM si_buyer_outreach WHERE endpoint_url != '' AND endpoint_url IS NOT NULL LIMIT 1000"),
}

RS["charges"] = {
    "total": scalar("SELECT COUNT(*) FROM si_charges LIMIT 1000"),
    "open": scalar("SELECT COUNT(*) FROM si_charges WHERE status='open' LIMIT 1000"),
    "paid": scalar("SELECT COUNT(*) FROM si_charges WHERE status='paid' LIMIT 1000"),
    "vault_usdc": scalar("SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) FROM si_charges WHERE status='paid' LIMIT 1000") or 0,
}

RS["settlements"] = {"rows": scalar("SELECT COUNT(*) FROM si_settlements LIMIT 1000")}

# MRR / ARR
mrr_rows = rows("""
    SELECT plan, billing_cycle, price_cents, COUNT(*) as subs
    FROM si_subscription
    WHERE status = 'active' AND price_cents > 0
    GROUP BY plan, billing_cycle, price_cents LIMIT 1000
""")
by_plan = {}
total_cents = 0
total_subs = 0
for r in mrr_rows:
    if r["billing_cycle"] == "annual":
        monthly = r["price_cents"] / 12.0
    else:
        monthly = r["price_cents"]
    monthly_cents = int(monthly)
    by_plan[r["plan"]] = by_plan.get(r["plan"], 0) + monthly_cents * r["subs"]
    total_cents += monthly_cents * r["subs"]
    total_subs += r["subs"]

RS["mrr"] = {
    "total_usd": round(total_cents / 100.0, 2),
    "total_subs": total_subs,
    "by_plan": {k: round(v / 100.0, 2) for k, v in by_plan.items()},
}
RS["arr"] = RS["mrr"]["total_usd"] * 12

# INVOICES
RS["invoices"] = {
    "pending": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='pending' LIMIT 1000"),
    "paid_today": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' AND DATE(paid_at)=DATE('now') LIMIT 1000"),
    "paid_total": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' LIMIT 1000"),
}

report["revenue_snapshot"] = RS
report["ts"] = datetime.now(timezone.utc).isoformat()
report["date"] = date.today().isoformat()

# Write output
with open(OUTPUT, 'w') as f:
    json.dump(report, f, indent=2, default=str)

print("Report written to", OUTPUT)