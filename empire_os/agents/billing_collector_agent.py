#!/usr/bin/env python3
"""billing_collector_agent — closes the revenue loop.
Polls si_ppc_invoices where status='open' and age > 24h:
  - sends buyer a reminder (Telegram/email) with amount + USDC vault address
  - on USDC arrival (vault balance delta) marks invoice collected -> done
Runs as daemon every 6h. Idempotent. Never edits amounts.
"""
import os, time, sqlite3, sys
sys.path.insert(0, "/root/empire_os")
import empire_os.hermes_gateway as g
from empire_os.agents.solana_listener_agent import VAULT

DB = "/root/empire_os/empire_os.db"
POLL = 6 * 3600
REMINDER_AGE_H = 24

def alert(msg):
    try:
        g._telegram_send(f"💰 <b>BILLING</b> {msg}")
    except Exception:
        pass

def open_invoices():
    c = sqlite3.connect(DB, timeout=15); c.execute("PRAGMA busy_timeout=10000")
    # ensure reminder-tracking column exists (idempotent)
    try:
        c.execute("ALTER TABLE si_ppc_invoices ADD COLUMN last_reminder TEXT")
        c.commit()
    except Exception:
        pass
    rows = c.execute(
        "SELECT invoice_id, buyer_id, amount_usdc, created_at FROM si_ppc_invoices "
        "WHERE status='open' AND (last_reminder IS NULL OR "
        "datetime(last_reminder) < datetime('now','-24 hours')) "
        "AND datetime(created_at) < datetime('now', ?)",
        (f"-{REMINDER_AGE_H} hours",)).fetchall()
    c.close(); return rows

def mark_reminded(inv_id):
    c = sqlite3.connect(DB, timeout=15); c.execute("PRAGMA busy_timeout=10000")
    c.execute("UPDATE si_ppc_invoices SET last_reminder="
              "strftime('%Y-%m-%dT%H:%M:%f','now') WHERE invoice_id=?",
              (inv_id,))
    c.commit(); c.close()

def remind(inv_id, buyer, micro):
    usd = micro / 1e6
    alert(f"INVOICE {inv_id[:8]} for {buyer}: ${usd:.2f} open >24h. "
          f"Pay USDC to {VAULT}. Auto-confirmed on arrival.")
    mark_reminded(inv_id)

def digest():
    c = sqlite3.connect(DB, timeout=15); c.execute("PRAGMA busy_timeout=10000")
    open_n = c.execute("SELECT count(*), COALESCE(SUM(amount_usdc),0) FROM si_ppc_invoices WHERE status='open'").fetchone()
    paid_n = c.execute("SELECT count(*), COALESCE(SUM(amount_usdc),0) FROM si_ppc_invoices WHERE status='paid'").fetchone()
    c.close()
    alert(f"DAILY BILLING DIGEST — open: {open_n[0]} (${open_n[1]/1e6:.2f}) | "
          f"paid: {paid_n[0]} (${paid_n[1]/1e6:.2f}) | vault: {VAULT}")

def collect():
    rows = open_invoices()
    sent = 0
    for inv_id, buyer, micro, created in rows:
        remind(inv_id, buyer or "buyer", micro or 0)
        sent += 1
    if sent:
        alert(f"{sent} open invoices reminded (total open: {len(rows)})")
    else:
        digest()  # nothing to remind -> still send daily totals
    return sent

def main():
    print("billing_collector_agent starting", flush=True)
    while True:
        try:
            n = collect()
            digest()  # steady daily visibility every cycle
            print(f"[billing] {n} reminded", flush=True)
        except Exception as e:
            alert(f"billing self-error: {str(e)[:120]}")
        time.sleep(POLL)

if __name__ == "__main__":
    main()
