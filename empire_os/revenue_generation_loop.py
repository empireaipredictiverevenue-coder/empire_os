#!/usr/bin/env python3
"""Autonomous revenue loop — pulls real metrics from buyer_leads, survives laptop closed."""
import sqlite3, json, time, os
from datetime import datetime, timezone

DB_PATH = "/root/empire_os/empire_os.db"
LOG_PATH = "/root/empire_os/feedback/revenue_automation.log"
REVENUE_TARGET = float(os.environ.get("REVENUE_TARGET", "1000000"))

def get_metrics():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    try:
        delivered = conn.execute("SELECT COUNT(*), COALESCE(SUM(payout_usd),0) FROM buyer_leads WHERE endpoint_status='http_200'").fetchone()
        invoiced = conn.execute("SELECT COUNT(*), COALESCE(SUM(payout_usd),0) FROM buyer_leads WHERE settlement_status='invoiced'").fetchone()
        settled = conn.execute("SELECT COUNT(*), COALESCE(SUM(payout_usd),0) FROM buyer_leads WHERE settlement_status='settled'").fetchone()
        outbox = conn.execute("SELECT COUNT(*) FROM si_outbox WHERE status='pending'").fetchone()[0]
        empty_lanes = conn.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by IS NULL OR occupied_by=''").fetchone()[0]
        subs_pending = conn.execute("SELECT COUNT(*) FROM si_subscription WHERE status='awaiting_payment'").fetchone()[0]
        open_invoices = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount_usdc),0) FROM si_ppc_invoices WHERE status='open'").fetchone()
        return {
            "delivered_leads": delivered[0], "delivered_revenue": float(delivered[1]),
            "invoiced_leads": invoiced[0], "invoiced_revenue": float(invoiced[1]),
            "settled_leads": settled[0], "settled_revenue": float(settled[1]),
            "outbox_pending": int(outbox), "empty_lanes": int(empty_lanes),
            "subs_awaiting": int(subs_pending),
            "open_invoices": open_invoices[0], "open_invoice_total": float(open_invoices[1]),
        }
    finally:
        conn.close()

if __name__ == "__main__":
    print(f"REVENUE LOOP STARTED | Target: ${REVENUE_TARGET:.0f}")
    cycle = 0
    while True:
        cycle += 1
        ts = datetime.now(timezone.utc).isoformat()
        try:
            m = get_metrics()
            # Real revenue = invoiced + settled (pipeline value)
            revenue = m["invoiced_revenue"] + m["settled_revenue"]
            pct = min(100.0, (revenue / REVENUE_TARGET) * 100) if REVENUE_TARGET > 0 else 0
            log = {"ts": ts, "cycle": cycle, "revenue": revenue, "target": REVENUE_TARGET, "pct": pct, **m}
            with open(LOG_PATH, "a") as f:
                f.write(json.dumps(log) + "\n")
            print(f"Cycle {cycle} | Pipeline: ${revenue:.0f}/{REVENUE_TARGET:.0f} ({pct:.1f}%) | Delivered: {m['delivered_leads']} (${m['delivered_revenue']:.0f}) | Invoiced: {m['invoiced_leads']} | Settled: {m['settled_leads']} | Open invoices: {m['open_invoices']} (${m['open_invoice_total']:.0f})", flush=True)
            if revenue >= REVENUE_TARGET:
                print(f"TARGET REACHED: ${revenue:.2f}")
        except Exception as e:
            print(f"Error: {e}", flush=True)
        time.sleep(120)  # 2 min cycles for faster feedback
