#!/usr/bin/env python3
"""MRR tiered billing runner.
Iterates active subscriptions, generates monthly invoice via tenants API.
Idempotent per cycle: skips if an invoice already exists for this period.
FK-safe: skips subs whose tenant_id does not exist in si_tenant.
Amount-safe: skips zero-amount (free/trial) plans — no phantom $0 invoices.
"""
import sys, sqlite3, time
from datetime import datetime, timezone
sys.path.insert(0, "/root/empire_os")
from empire_os.tenants import TenantStore, compute_invoice_amount, PLANS
from empire_os.pay_link import build_pay_url, invoice_memo

DB = "/root/empire_os/empire_os.db"

def _with_retry(conn, sql, params=()):
    """Run a write with busy_timeout retry so the live hub can't deadlock us."""
    for _ in range(10):
        try:
            conn.execute(sql, params)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                time.sleep(0.5)
                continue
            raise
    return False

def queue_pay_email(conn, inv_id, tid, amt, pay_url, period):
    """Enqueue a payable invoice email into si_outbox (mail-sender flushes it).
    Idempotent: skips if an outbox row for this invoice already exists.
    """
    have = conn.execute(
        "SELECT count(*) FROM si_outbox WHERE source='mrr_invoice' AND meta_json LIKE ?",
        (f"%{inv_id}%",)).fetchone()[0]
    if have:
        return False
    row = conn.execute("SELECT email FROM si_tenant WHERE tenant_id=?", (tid,)).fetchone()
    if not row or not (row[0] or "").strip() or not amt:
        return False
    email = row[0].strip()
    usdc = amt / 100.0
    subject = f"Empire OS invoice {period} — ${usdc:.2f} USDT (BSC)"
    body = (
        f"Your Empire OS subscription invoice for {period} is ready.\n\n"
        f"Amount: ${usdc:.2f} USDT on BSC\n"
        f"Pay here: {pay_url}\n\n"
        f"Scan the link with Trust Wallet (BSC network) and send the "
        f"exact USDT amount. Your memo is attached automatically. The subscription "
        f"activates on confirmation.\n\n"
        f"Invoice: {inv_id}\n"
    )
    _with_retry(conn,
        "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, "
        "status, meta_json, recipient_kind, approval_ref, provider_message_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (email, subject, body, "revenue", "paid", "mrr_invoice", "pending",
         f'{{"invoice_id":"{inv_id}"}}', "tenant", "aprv-mrr-billing-auto",
         f"mrr_{inv_id}"),
    )
    return True

def run_billing(period: str = "2026-07"):
    store = TenantStore(DB)
    conn = store._conn
    # Survive contention with the live hub + billing_collector daemons.
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    subs = conn.execute(
        "SELECT subscription_id, tenant_id, plan, seats, billing_cycle "
        "FROM si_subscription WHERE status='active'").fetchall()
    # Defensive: ensure si_invoice has the columns we write (schema drift fix).
    cols = {r[1] for r in conn.execute("PRAGMA table_info(si_invoice)")}
    if "pay_url" not in cols:
        conn.execute("ALTER TABLE si_invoice ADD COLUMN pay_url TEXT")
    if "charged_at" not in cols:
        conn.execute("ALTER TABLE si_invoice ADD COLUMN charged_at TEXT")
    print(f"=== MRR billing run [{period}] : {len(subs)} active subs ===")
    created = 0
    emailed = 0
    skipped_orphan = 0
    skipped_zero = 0
    for sid, tid, plan, seats, cycle in subs:
        # idempotency: skip if invoice for this period+sub exists
        have = conn.execute(
            "SELECT count(*) FROM si_invoice WHERE subscription_id=? AND "
            "description LIKE ?", (sid, f"%{period}%")).fetchone()[0]
        if have:
            # make sure a pay link + email exist even for pre-existing invoices
            inv_row = conn.execute(
                "SELECT invoice_id, amount_cents, pay_url FROM si_invoice "
                "WHERE subscription_id=? AND description LIKE ? LIMIT 1",
                (sid, f"%{period}%")).fetchone()
            if inv_row and not inv_row[2]:
                url = build_pay_url(inv_row[0], inv_row[1])
                _with_retry(conn, "UPDATE si_invoice SET pay_url=? WHERE invoice_id=?",
                            (url, inv_row[0]))
                if queue_pay_email(conn, inv_row[0], tid, inv_row[1], url, period):
                    emailed += 1
            continue
        # FK-safe: tenant must exist
        texists = conn.execute(
            "SELECT count(*) FROM si_tenant WHERE tenant_id=?", (tid,)
        ).fetchone()[0]
        if not texists:
            skipped_orphan += 1
            print(f"  SKIP-ORPHAN {plan} tenant={tid[:8]} (no si_tenant row)")
            continue
        amt = compute_invoice_amount(plan, seats or 1, cycle or "monthly")
        if not amt and (plan or "").startswith("seat_"):
            # Marketplace lane-seat tiers (bronze/silver/gold) live in
            # marketplace.LANE_SEAT_PRICING, not tenants.PLANS. Use the sub's
            # own price_cents (written at signup from that same table).
            pc = conn.execute(
                "SELECT price_cents FROM si_subscription WHERE subscription_id=?",
                (sid,)).fetchone()
            amt = int(pc[0]) if pc and pc[0] else 0
        if not amt:
            skipped_zero += 1
            continue
        bps = PLANS.get(plan, PLANS["free"]).backend_bps
        desc = f"MRR {plan} x{seats or 1} {cycle or 'monthly'} {period}"
        inv = None
        try:
            for _attempt in range(5):
                try:
                    inv = store.create_invoice(
                        tid, amt, "usdc_pending",
                        subscription_id=sid,
                        description=desc,
                    )
                    break
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower():
                        time.sleep(1)
                        continue
                    raise
        except Exception as e:
            print(f"  SKIP-ERR {plan} tenant={tid[:8]} ({type(e).__name__}: {e})")
            skipped_orphan += 1
            continue
        if not inv:
            print(f"  SKIP-LOCKED {plan} tenant={tid[:8]}")
            skipped_orphan += 1
            continue
        # attach payable link + queue collection email
        pay_url = build_pay_url(inv.invoice_id, amt)
        _with_retry(conn,
                    "UPDATE si_invoice SET pay_url=?, charged_at=? WHERE invoice_id=?",
                    (pay_url, datetime.now(timezone.utc).isoformat(), inv.invoice_id))
        if queue_pay_email(conn, inv.invoice_id, tid, amt, pay_url, period):
            emailed += 1
        backend_note = f" + {bps/100:.0f}% backend on closed deals" if bps else ""
        print(f"  BILL {plan:10} tenant={tid[:8]} ${amt/100:.2f}{backend_note} inv={inv.invoice_id}")
        created += 1
    print(f"invoices created this run: {created} | pay-emails queued: {emailed}")
    print(f"skipped orphan-tenant: {skipped_orphan} | skipped zero-amount: {skipped_zero}")
    return created

if __name__ == "__main__":
    run_billing()
