#!/usr/bin/env python3
"""Funnel closeout: advance SETTLED leads -> BILLED -> COLLECTED -> DONE.
Unblocks the pipeline stall. Idempotent: only transitions leads not yet past SETTLED.
"""
import sys, sqlite3
sys.path.insert(0, "/root/empire_os")
from empire_os.funnel import SQLiteBackend, transition, FunnelState

DB = "/root/empire_os/empire_os.db"

def current_state(backend, prospect_id):
    row = backend.conn.execute(
        "SELECT to_state FROM si_funnel_event WHERE prospect_id=? "
        "ORDER BY occurred_at DESC LIMIT 1", (prospect_id,)).fetchone()
    return row[0] if row else None

def run():
    backend = SQLiteBackend(DB)
    # leads stuck at settled
    rows = backend.conn.execute(
        "SELECT DISTINCT prospect_id FROM si_funnel_event WHERE to_state='settled' "
        "AND prospect_id NOT IN (SELECT DISTINCT prospect_id FROM si_funnel_event WHERE to_state IN ('billed','collected','done'))"
    ).fetchall()
    print(f"=== funnel closeout: {len(rows)} leads at SETTLED ===")
    billed = collected = done = 0
    for (pid,) in rows:
        # settled -> billed (invoice creation handled by lead_deliverer on delivery;
        # here we mark the funnel state so billing is tracked)
        transition(backend, pid, "billed", "funnel_closeout", "settled closeout")
        billed += 1
        # mark collected if an invoice for this lead is paid
        paid = backend.conn.execute(
            "SELECT count(*) FROM si_ppc_invoices WHERE lead_id=? AND status='paid'",
            (pid,)).fetchone()[0]
        if paid:
            transition(backend, pid, "collected", "funnel_closeout", "invoice paid")
            collected += 1
            transition(backend, pid, "done", "funnel_closeout", "closed")
            done += 1
    backend.commit()
    print(f"billed={billed} collected={collected} done={done}")
    return billed

if __name__ == "__main__":
    run()
