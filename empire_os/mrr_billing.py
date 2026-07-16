#!/usr/bin/env python3
"""MRR tiered billing runner.
Iterates active subscriptions, generates monthly invoice via tenants API.
Idempotent per cycle: skips if an invoice already exists for this period.
"""
import sys, sqlite3
sys.path.insert(0, "/root/empire_os")
from empire_os.tenants import TenantStore, compute_invoice_amount

DB = "/root/empire_os/empire_os.db"

def run_billing(period: str = "2026-07"):
    store = TenantStore(DB)
    conn = store._conn
    subs = conn.execute(
        "SELECT subscription_id, tenant_id, plan, seats, billing_cycle "
        "FROM si_subscription WHERE status='active'").fetchall()
    print(f"=== MRR billing run [{period}] : {len(subs)} active subs ===")
    created = 0
    for sid, tid, plan, seats, cycle in subs:
        # idempotency: skip if invoice for this period+sub exists
        have = conn.execute(
            "SELECT count(*) FROM si_invoice WHERE subscription_id=? AND "
            "description LIKE ?", (sid, f"%{period}%")).fetchone()[0]
        if have:
            print(f"  skip {plan} tenant={tid[:8]} (already billed {period})")
            continue
        amt = compute_invoice_amount(plan, seats or 1, cycle or "monthly")
        from empire_os.tenants import PLANS
        bps = PLANS.get(plan, PLANS["free"]).backend_bps
        desc = f"MRR {plan} x{seats or 1} {cycle or 'monthly'} {period}"
        inv = store.create_invoice(
            tid, amt, "usdc_pending",
            subscription_id=sid,
            description=desc,
        )
        backend_note = f" + {bps/100:.0f}% backend on closed deals" if bps else ""
        print(f"  BILL {plan:10} tenant={tid[:8]} ${amt/100:.2f}{backend_note} inv={inv.invoice_id}")
        created += 1
    print(f"invoices created this run: {created}")
    return created

if __name__ == "__main__":
    run_billing()
