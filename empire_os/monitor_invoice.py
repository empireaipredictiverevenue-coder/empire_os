"""Read-only monitor: flags stale pending invoices for operator review.

Reads DB `si_invoice` for rows where status='pending' AND created_at < (now - 2h).
Reports counts by tenant so operator can review / take action (whop webhook, crypto settlement,
or manual resolution). Does NOT auto-mark-paid. Emits JSON summary only.

Design:
- Safe to run alongside live agents (short read-only transactions).
- Handles schema: if `paid_method` column exists, reads it; otherwise falls back to `method` column.
- Does NOT mutate DB. No auto-mark-paid.
- Idempotent: re-running on same rows is safe.

Critical: only mark Paid when there is affirmative evidence (webhook HMAC match,
or external system signal such as USDT settlement). Do NOT guess / auto-assume.
"""

import sqlite3, json, os, time
from datetime import datetime, timezone, timedelta

DB = "/root/empire_os/empire_os.db"
MAX_AGE_HOURS = 2   # invoices older than 2h without payment → review batch
BATCH_SIZE = 50     # rows per tick so we don't hold locks too long


def now_utc():
    return datetime.now(timezone.utc)


def get_stale_pending():
    """Return (rows, cutoff_iso) where rows = (invoice_id, tenant_id, status, paid_method_or_method).
    
    If `paid_method` column exists, reads that. Falls back to `method` column.
    """
    cutoff = now_utc() - timedelta(hours=MAX_AGE_HOURS)
    cutoff_iso = cutoff.isoformat()
    conn = sqlite3.connect(DB, timeout=30)
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(si_invoice)")
        cols = [row[1] for row in c.fetchall()]
        has_paid_method = "paid_method" in cols
        has_status = "status" in cols
        has_method = "method" in cols

        # Determine which column to use for payment method
        if has_paid_method:
            paid_sel = "paid_method"
        elif has_method:
            paid_sel = "method"
        else:
            paid_sel = "NULL AS paid_method_fallback"

        # Build SELECT: always pick invoice_id, tenant_id, status + payment method column
        sel = f"invoice_id, tenant_id, status, {paid_sel}"

        # Build WHERE clause
        if has_status:
            table_where = "status='pending' AND created_at < ?"
        else:
            table_where = "created_at < ?"

        c.execute(
            f"SELECT {sel} FROM si_invoice WHERE {table_where}",
            (cutoff_iso,),
        )
        rows = c.fetchall()
        return rows, cutoff_iso, has_paid_method
    finally:
        conn.close()


def main():
    rows, cutoff_iso, has_paid_method = get_stale_pending()
    if not rows:
        print(json.dumps({"batch": 0, "stale_pending": 0, "has_paid_method": has_paid_method}))
        return

    # Count per-tenant for operator review
    tenant_counts = {}
    method_counts = {}
    for invoice_id, tenant_id, status, method_val in rows:
        tenant_counts[tenant_id] = tenant_counts.get(tenant_id, 0) + 1
        method_counts[method_val] = method_counts.get(method_val, 0) + 1

    output = {
        "batch": len(rows),
        "stale_pending": len(rows),
        "stale_pending_by_tenant": tenant_counts,
        "method_distribution": method_counts,
        "cutoff_utc": cutoff_iso,
        "has_paid_method": has_paid_method,
        "note": "invoices older than 2h with status=pending need operator review "
                "(whop webhook HMAC verification or BSC USDT settlement signal required "
                "to mark paid; no auto-payment applied by this script). "
                "If 'paid_method' column is missing, 'method' column values are shown instead.",
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()