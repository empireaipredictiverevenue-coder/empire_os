#!/usr/bin/env python3
"""
Empire OS v3 — Revenue Snapshot Reporter
=========================================
Pulls live DB state + AI summary (Cortex brain) + sends to ANY messaging
platform via `hermes send`. Runs as systemd timer for daily/30min cadence.

Usage:
    python3 -m empire_os.revenue_snapshot           # full snapshot
    python3 -m empire_os.revenue_snapshot --json    # JSON only
    python3 -m empire_os.revenue_snapshot --send telegram  # push to telegram
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK = Path("/root/feedback")
FEEDBACK.mkdir(parents=True, exist_ok=True)


def mrr_breakdown(c) -> dict:
    """Compute MRR from active subscriptions grouped by plan/tier.

    MRR = sum(price_cents) / 100 for active subscriptions.
    ARR = MRR × 12.
    """
    rows = c.execute("""
        SELECT plan, billing_cycle, price_cents,
               COUNT(*) AS subs
        FROM si_subscription
        WHERE status = 'active' AND price_cents > 0
        GROUP BY plan, billing_cycle, price_cents
    """).fetchall()

    by_plan = {}
    total_cents = 0
    total_subs = 0
    for plan, cycle, price_cents, subs in rows:
        # Normalize to monthly (annual = /12)
        if cycle == "annual":
            monthly = (price_cents / 12.0)
        else:
            monthly = price_cents
        monthly_cents = int(monthly)
        by_plan[plan] = by_plan.get(plan, 0) + monthly_cents * subs
        total_cents += monthly_cents * subs
        total_subs += subs

    return {
        "total_usd": round(total_cents / 100.0, 2),
        "total_subs": total_subs,
        "by_plan": {k: round(v / 100.0, 2) for k, v in by_plan.items()},
    }


def snapshot() -> dict:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    snap = {"ts": datetime.now(timezone.utc).isoformat()}

    # LEADS
    snap["leads"] = {
        "total": c.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0],
        "last_1h": c.execute("SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 hour')").fetchone()[0],
        "last_24h": c.execute("SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 day')").fetchone()[0],
        "by_tier": {r["omega_tier"]: r["COUNT(*)"] for r in c.execute("SELECT omega_tier, COUNT(*) AS 'COUNT(*)' FROM lane_leads GROUP BY omega_tier").fetchall() if r["omega_tier"]},
        "avg_fit_score": c.execute(
            "SELECT ROUND(AVG(MIN(100, MAX(0, omega_score))), 1) "
            "FROM lane_leads WHERE omega_score IS NOT NULL"
        ).fetchone()[0] or 0,
    }

    # A2A MATCHES
    snap["a2a"] = {
        "total": c.execute("SELECT COUNT(*) FROM buyer_leads").fetchone()[0],
        "delivered_http_200": c.execute(
            "SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='http_200'"
        ).fetchone()[0],
        "pending": c.execute(
            "SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='pending'"
        ).fetchone()[0],
        "no_endpoint": c.execute(
            "SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='no_endpoint'"
        ).fetchone()[0],
        "locked_usd": c.execute(
            "SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads "
            "WHERE endpoint_status='http_200'"
        ).fetchone()[0] or 0,
        "test_received": c.execute(
            "SELECT COUNT(*) FROM test_received_leads"
        ).fetchone()[0],
    }

    # BUYERS
    snap["buyers"] = {
        "total": c.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0],
        "priced": c.execute(
            "SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0"
        ).fetchone()[0],
        "with_endpoint": c.execute(
            "SELECT COUNT(*) FROM si_buyer_outreach "
            "WHERE endpoint_url != '' AND endpoint_url IS NOT NULL"
        ).fetchone()[0],
    }

    # CHARGES
    snap["charges"] = {
        "total": c.execute("SELECT COUNT(*) FROM si_charges").fetchone()[0],
        "open": c.execute("SELECT COUNT(*) FROM si_charges WHERE status='open'").fetchone()[0],
        "paid": c.execute("SELECT COUNT(*) FROM si_charges WHERE status='paid'").fetchone()[0],
        "vault_usdc": c.execute(
            "SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) "
            "FROM si_charges WHERE status='paid'"
        ).fetchone()[0] or 0,
    }

    # SETTLEMENTS
    try:
        snap["settlements"] = {
            "rows": c.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0],
        }
    except Exception:
        snap["settlements"] = {"rows": 0, "note": "table missing"}

    # MRR (Monthly Recurring Revenue) — from active subscriptions
    snap["mrr"] = mrr_breakdown(c)

    # ARR (Annual Recurring Revenue) — MRR × 12
    snap["arr"] = snap["mrr"]["total_usd"] * 12

    # CORPUS BRAIN
    brain_path = FEEDBACK / "cortex_brain.json"
    if brain_path.exists():
        brain = json.loads(brain_path.read_text())
        snap["cortex_alerts"] = brain.get("snapshot", {}).get("alerts", [])[:5]
        advice = brain.get("advice", {})
        snap["cortex_summary"] = (advice.get("content", "") or "")[:500]
    return snap


def render_text(snap: dict) -> str:
    """Compact ASCII report for message body."""
    L, A, B = snap["leads"], snap["a2a"], snap["buyers"]
    CH = snap["charges"]
    M = snap["mrr"]

    lines = [
        "EMPIRE OS v3 — REVENUE SNAPSHOT",
        f"{snap['ts'][:19]} UTC",
        "",
        "MRR (Monthly Recurring Revenue)",
        f"  total MRR:    ${M['total_usd']:,.2f}",
        f"  ARR:          ${snap['arr']:,.2f}",
        f"  active subs:  {M['total_subs']:,}",
        "  by plan:",
    ]
    for plan, amt in sorted(M["by_plan"].items(), key=lambda x: -x[1]):
        lines.append(f"    {plan:25s} ${amt:>10,.2f}")

    lines += [
        "",
        "LEADS",
        f"  total:        {L['total']:,}",
        f"  last 1h:      {L['last_1h']:,}",
        f"  last 24h:     {L['last_24h']:,}",
        f"  by tier:      {' '.join(f'{k}={v}' for k, v in L['by_tier'].items())}",
        f"  avg fit:      {L['avg_fit_score']:.1f}/100",
        "",
        "A2A",
        f"  matches:      {A['total']:,}",
        f"  delivered:    {A['delivered_http_200']:,}",
        f"  pending:      {A['pending']:,}",
        f"  test_recv:    {A['test_received']:,}",
        f"  locked USD:   ${A['locked_usd']}",
        "",
        "BUYERS",
        f"  priced:       {B['priced']:,}",
        f"  endpointed:   {B['with_endpoint']:,}",
        "",
        "CHARGES",
        f"  total:        {CH['total']:,}",
        f"  open:         {CH['open']:,}",
        f"  paid:         {CH['paid']:,}",
        f"  vault USDC:   ${CH['vault_usdc']}",
        "",
        f"SETTLEMENTS rows: {snap['settlements']['rows']}",
    ]
    if snap.get("cortex_summary"):
        lines.append("")
        lines.append("🧠 CORTEX")
        lines.append(snap["cortex_summary"])
    if snap.get("cortex_alerts"):
        lines.append("")
        lines.append("⚠ ALERTS")
        for a in snap["cortex_alerts"][:3]:
            lines.append(f"  • {a[:120]}")
    return "\n".join(lines)


def send(target: str, body: str, subject: str = None) -> int:
    """Send via hermes CLI (uses Telegram/Discord/Slack bot token)."""
    cmd = ["hermes", "send", "-t", target, "--quiet"]
    if subject:
        cmd.extend(["--subject", subject])
    cmd.append(body)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="Print JSON")
    p.add_argument("--save", action="store_true", help="Save to /root/feedback")
    p.add_argument("--send", default=None, help="Send to: telegram / telegram:-100... / etc")
    args = p.parse_args()

    snap = snapshot()
    if args.json:
        print(json.dumps(snap, indent=2, default=str))
    else:
        print(render_text(snap))

    if args.save:
        path = FEEDBACK / "revenue_snapshot.json"
        path.write_text(json.dumps(snap, indent=2, default=str))
        print(f"\nSaved: {path}")

    if args.send:
        body = render_text(snap)
        subject = f"Empire OS Snapshot — ${snap['a2a']['locked_usd']} locked / {snap['leads']['last_24h']} leads / 24h"
        rc = send(args.send, body, subject)
        print(f"\nSend to {args.send}: exit={rc}")


if __name__ == "__main__":
    main()

