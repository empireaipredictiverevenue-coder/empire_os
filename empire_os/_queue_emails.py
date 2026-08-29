#!/usr/bin/env python3
"""Batch-queue MRR invoice collection emails into si_outbox.

Senior-engineer note: the prior version used a *correlated* subquery
(`NOT EXISTS (SELECT 1 FROM si_outbox o WHERE o.meta_json LIKE '%'||i.invoice_id||'%')`)
which is O(rows x outbox_rows) — ~14k x 392k = billions of LIKE scans. That is
why it stalled, not the DB lock. This version pre-materialises the already-queued
invoice_ids ONCE into a Python set, then does a flat join + in-memory filter.
WAL + single COMMIT keeps lock pressure minimal.
"""
import sqlite3, os, re

os.environ.setdefault("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")
DB = "/root/empire_os/empire_os.db"

c = sqlite3.connect(DB, timeout=30)
c.execute("PRAGMA busy_timeout=120000")

# 1) already-queued invoice ids (one pass, no per-row subquery)
queued = set()
for (mj,) in c.execute("SELECT meta_json FROM si_outbox WHERE source='mrr_invoice'"):
    m = re.search(r'"invoice_id":"([^"]+)"', mj or "")
    if m:
        queued.add(m.group(1))
print(f"[queue] already-queued invoice ids: {len(queued)}")

# 2) flat candidate join (fast; indexes on tenant_id)
rows = c.execute("""
    SELECT i.invoice_id, i.tenant_id, i.amount_cents, i.pay_url, t.email
    FROM si_invoice i
    JOIN si_tenant t ON t.tenant_id = i.tenant_id
    WHERE i.description LIKE '%2026-07%'
      AND i.pay_url IS NOT NULL
      AND i.amount_cents > 0
      AND t.email IS NOT NULL
      AND t.email != ''
""").fetchall()
print(f"[queue] billable candidates: {len(rows)}")

todo = [(iid, tid, amt, url, em) for (iid, tid, amt, url, em) in rows if iid not in queued]
print(f"[queue] to insert: {len(todo)}")

# 3) single transaction insert
c.execute("BEGIN")
n = 0
for iid, tid, amt, url, email in todo:
    usdc = amt / 100.0
    subj = f"Empire OS invoice 2026-07 - ${usdc:.2f} USDT (BSC)"
    body = (
        f"Your Empire OS subscription invoice for 2026-07 is ready.\n\n"
        f"Amount: ${usdc:.2f} USDT on BSC\nPay here: {url}\n\n"
        f"Scan with Trust Wallet / MetaMask (BSC network). The memo is attached "
        f"automatically. Your subscription activates on confirmation.\n\n"
        f"Invoice: {iid}\n"
    )
    c.execute(
        "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, "
        "status, meta_json, buyer_tenant) VALUES (?,?,?,?,?,?,?,?,?)",
        (email, subj, body, "revenue", "paid", "mrr_invoice", "pending",
         f'{{"invoice_id":"{iid}"}}', tid),
    )
    n += 1
c.execute("COMMIT")
print(f"[queue] EMAILS QUEUED: {n}")
