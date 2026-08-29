#!/usr/bin/env python3
"""
Settlement Bridge — connects buyer_leads.delivered (http_200) to BSC USDT settlement.

Flow:
1. Scan buyer_leads where endpoint_status='http_200' AND settlement_status IS NULL
2. For each, create si_ppc_invoice with lead_id + buyer_id + payout_usd
3. When BSC listener detects payment (via balance delta + finance_reconcile),
   it will call /v1/billing/crypto/verify which activates subscription
4. Bridge also listens for finance_reconcile attributions and marks buyer_leads settled

Run via systemd timer every 60s.
"""
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"
LOG_DIR = "/root/empire_os/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "settlement_bridge.jsonl")

def log(level: str, msg: str, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry), flush=True)

def get_conn():
    c = sqlite3.connect(DB, timeout=60, isolation_level=None)
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("PRAGMA journal_mode=WAL")
    c.row_factory = sqlite3.Row
    return c

def process_cycle():
    """One settlement bridge cycle — single transaction, no nested connections."""
    conn = get_conn()
    try:
        now = datetime.now(timezone.utc).isoformat()
        ts = int(time.time())

        # 1. Find delivered leads without settlement (read first)
        # Include both webhook (http_200) and email (email_sent) deliveries
        # Exclude leads that already have si_ppc_invoices
        rows = conn.execute("""
            SELECT bl.id, bl.buyer_id, bl.lane_lead_id, bl.prospect_id, bl.niche, bl.metro, bl.payout_usd
            FROM buyer_leads bl
            LEFT JOIN si_ppc_invoices pi ON pi.lead_id = bl.lane_lead_id
            WHERE bl.endpoint_status IN ('http_200', 'email_sent')
              AND (bl.settlement_status IS NULL OR bl.settlement_status='')
              AND bl.payout_usd > 0
              AND pi.invoice_id IS NULL
            ORDER BY bl.created_at ASC
            LIMIT 500
        """).fetchall()

        # 2. Batch all inserts + updates in one transaction
        created = 0
        with conn:
            for i, row in enumerate(rows):
                lead_id = row["lane_lead_id"]
                buyer_id = row["buyer_id"]
                payout = row["payout_usd"]
                niche = row["niche"] or ""
                metro = row["metro"] or ""
                prospect_id = row["prospect_id"] or ""
                amount_cents = int(round(payout * 100))
                # Use ts + counter to ensure unique IDs even within same second
                invoice_ts = ts + i
                invoice_id = f"inv_lead_{lead_id}_{invoice_ts}"
                charge_id = f"chg_lead_{lead_id}_{invoice_ts}"
                head = f"lead_delivery:{niche}:{metro}"

                conn.execute("""
                    INSERT INTO si_ppc_invoices
                    (invoice_id, charge_id, buyer_id, head, lead_id, amount_cents, amount_usdc, status, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """, (invoice_id, charge_id, buyer_id, head, lead_id, amount_cents, payout,
                      json.dumps({"source": "settlement_bridge", "lead_id": lead_id, "prospect_id": prospect_id}), now))

                conn.execute("""
                    INSERT INTO si_charges
                    (charge_id, buyer_id, processor, customer_ref, payment_ref, head, reason, amount_cents, currency, status, processor_response, attempt_count, created_at)
                    VALUES (?, ?, 'usdt_bsc', ?, '', ?, ?, ?, 'USDT', 'pending', ?, 1, ?)
                """, (charge_id, buyer_id, invoice_id, head, f"Settlement for lead {lead_id} ({niche}/{metro})",
                      amount_cents, json.dumps({"source": "settlement_bridge", "lead_id": lead_id}), now))

                conn.execute("UPDATE buyer_leads SET settlement_status='invoiced', invoice_id=? WHERE lane_lead_id=?",
                             (invoice_id, lead_id))
                created += 1

        if created:
            log("INFO", "batch_invoiced", count=created)

        # 3. Sync settled leads (separate short transaction)
        settled_count = 0
        try:
            with conn:
                settled_rows = conn.execute("""
                    SELECT bl.lane_lead_id
                    FROM buyer_leads bl
                    JOIN si_funnel_event fe ON fe.prospect_id = bl.prospect_id
                    WHERE bl.settlement_status='invoiced'
                      AND fe.to_state='settled'
                      AND fe.actor='bsc_listener'
                      AND fe.notes LIKE '%' || bl.lane_lead_id || '%'
                """).fetchall()
                for r in settled_rows:
                    conn.execute("UPDATE buyer_leads SET settlement_status='settled' WHERE lane_lead_id=?",
                                 (r["lane_lead_id"],))
                    settled_count += 1
        except Exception as e:
            log("WARN", "settled_sync_failed", error=str(e)[:200])

        return {"created_invoices": created, "updated_to_settled": settled_count}
    finally:
        conn.close()

def main():
    import sys
    once = "--once" in sys.argv
    log("INFO", "settlement_bridge_started", mode="once" if once else "loop")
    consecutive_fails = 0
    while True:
        try:
            result = process_cycle()
            if result["created_invoices"] > 0 or result["updated_to_settled"] > 0:
                log("INFO", "cycle_complete", **result)
            consecutive_fails = 0
        except Exception as e:
            consecutive_fails += 1
            log("ERROR", "cycle_error", error=str(e)[:200], fails=consecutive_fails)
        if once:
            break
        # Retry faster after failures, normal pace when working
        time.sleep(5 if consecutive_fails > 0 else 60)

if __name__ == "__main__":
    main()