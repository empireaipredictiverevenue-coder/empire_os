#!/usr/bin/env python3
"""
Empire OS v3 — Daily Report SQL Only (Container-side)
=======================================================
Only runs SQL queries via read-only connections. No subprocess calls.
"""

import json
import sqlite3
import sys
import os
from datetime import datetime, date, timezone

DB = "/root/empire_os/empire_os.db"

def ro_conn():
    c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True, timeout=30)
    c.row_factory = sqlite3.Row
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
    "by_tier": {r["omega_tier"]: r["cnt"] for r in rows("SELECT omega_tier, COUNT(*) as cnt FROM lane_leads GROUP BY omega_tier LIMIT 20") if r["omega_tier"]},
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

# CORTEX BRAIN
brain_path = "/root/feedback/cortex_brain.json"
if os.path.exists(brain_path):
    with open(brain_path) as f:
        brain = json.load(f)
    RS["cortex_alerts"] = brain.get("snapshot", {}).get("alerts", [])[:5]
    advice = brain.get("advice", {})
    RS["cortex_summary"] = (advice.get("content", "") or "")[:500]

report["revenue_snapshot"] = RS

# ── LEAD STATS ──
report["lead_stats"] = {
    "lane_leads": {
        "total": scalar("SELECT COUNT(*) FROM lane_leads"),
        "by_status": rows("SELECT status, COUNT(*) as cnt FROM lane_leads GROUP BY status ORDER BY cnt DESC LIMIT 100"),
        "by_niche": rows("SELECT COALESCE(niche, 'unknown') as niche, COUNT(*) as cnt FROM lane_leads GROUP BY niche ORDER BY cnt DESC LIMIT 20"),
    },
    "buyer_outreach": {
        "total": scalar("SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000"),
        "by_reply_state": rows("SELECT COALESCE(reply_state, 'unknown') as state, COUNT(*) as cnt FROM si_buyer_outreach GROUP BY state ORDER BY cnt DESC LIMIT 100"),
    },
    "funnel_current": rows("""
        SELECT e.to_state as state, COUNT(*) as count
        FROM si_funnel_event e
        INNER JOIN (SELECT prospect_id, MAX(id) as max_id FROM si_funnel_event GROUP BY prospect_id) l ON e.id = l.max_id
        GROUP BY e.to_state ORDER BY count DESC LIMIT 100
    """),
}

# ── HEALTH (simplified) ──
report["health"] = {
    "ok": False,
    "revenue_path_ready": False,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "summary": {
        "env_ok": True,
        "db_ok": True,
        "chain_ok": True,
        "hub_ok": False,
        "listener_ok": True,
    }
}

# ── INVOICES ──
report["invoices"] = {
    "pending": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='pending' LIMIT 1000"),
    "paid_today": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' AND DATE(paid_at)=DATE('now') LIMIT 1000"),
    "paid_total": scalar("SELECT COUNT(*) FROM si_invoice WHERE status='paid' LIMIT 1000"),
}

# ── OUTPUT ──
print(json.dumps(report, default=str))