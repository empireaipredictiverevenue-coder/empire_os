#!/usr/bin/env python3
"""affiliate — Ref-link tracking + USDC commission payouts.

Every AEO CTA, A2A quote, lead-buy URL accepts ?ref=CODE. When a
conversion is logged, the ref gets a commission_bps cut of the
sale. Commissions accumulate in affiliate_ledger and are swept
hourly by payout_scheduler to the affiliate's wallet.

Tables:
  affiliate_refs(code, wallet, commission_bps, created_at)
  affiliate_conversions(id, ts, ref_code, source, amount_cents,
                        commission_cents, status, meta)
  affiliate_ledger(id, ts, ref_code, conversion_id, amount_cents,
                   payout_tx, status)

Source: aeo | a2a | lease
Status: pending → swept | failed
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
DEFAULT_COMMISSION_BPS = int(os.getenv("AFFILIATE_DEFAULT_BPS", "1000"))  # 10%
MIN_PAYOUT_CENTS = int(os.getenv("AFFILIATE_MIN_PAYOUT_CENTS", "500"))  # $5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_tables(c: sqlite3.Connection) -> None:
    # affiliate_refs: ensure all columns exist (may have been created by aeo_monetize earlier)
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_refs (
            code TEXT PRIMARY KEY,
            wallet TEXT NOT NULL,
            commission_bps INTEGER DEFAULT 1000,
            label TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            active INTEGER DEFAULT 1
        )""")
    # Add missing columns if table existed without them
    cur_cols = [r[1] for r in c.execute("PRAGMA table_info(affiliate_refs)").fetchall()]
    if "label" not in cur_cols:
        c.execute("ALTER TABLE affiliate_refs ADD COLUMN label TEXT")
    if "active" not in cur_cols:
        c.execute("ALTER TABLE affiliate_refs ADD COLUMN active INTEGER DEFAULT 1")
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_conversions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ref_code TEXT NOT NULL,
            source TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            commission_cents INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            buyer_wallet TEXT,
            meta TEXT,
            payout_id INTEGER
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ref_code TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            payout_tx TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    c.commit()


def register_ref(code: str, wallet: str, commission_bps: int = DEFAULT_COMMISSION_BPS,
                 label: Optional[str] = None) -> dict:
    """Register an affiliate ref code -> wallet."""
    c = db()
    try:
        ensure_tables(c)
        c.execute(
            "INSERT OR IGNORE INTO affiliate_refs (code, wallet, commission_bps, label) VALUES (?,?,?,?)",
            (code, wallet, commission_bps, label),
        )
        c.commit()
        row = c.execute("SELECT * FROM affiliate_refs WHERE code = ?", (code,)).fetchone()
        return dict(row)
    finally:
        c.close()


def get_ref(code: str) -> Optional[dict]:
    c = db()
    try:
        ensure_tables(c)
        row = c.execute("SELECT * FROM affiliate_refs WHERE code = ? AND active=1", (code,)).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def generate_code(prefix: str = "REF") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def record_conversion(ref_code: str, source: str, amount_cents: int,
                      buyer_wallet: Optional[str] = None,
                      meta: Optional[dict] = None) -> dict:
    """Record a conversion, compute commission, accumulate in ledger."""
    c = db()
    try:
        ensure_tables(c)
        ref = get_ref(ref_code)
        if not ref:
            return {"ok": False, "error": "ref_not_found_or_inactive"}
        commission = int(amount_cents * ref["commission_bps"] / 10000)
        cur = c.execute(
            "INSERT INTO affiliate_conversions (ts, ref_code, source, amount_cents, "
            "commission_cents, buyer_wallet, meta) VALUES (?,?,?,?,?,?,?)",
            (_now(), ref_code, source, amount_cents, commission,
             buyer_wallet, json.dumps(meta) if meta else None),
        )
        conv_id = cur.lastrowid
        # Add to pending ledger
        c.execute(
            "INSERT INTO affiliate_ledger (ts, ref_code, amount_cents, status) VALUES (?,?,?,?)",
            (_now(), ref_code, commission, "pending"),
        )
        c.execute(
            "UPDATE affiliate_conversions SET payout_id = (SELECT MAX(id) FROM affiliate_ledger WHERE ref_code=?) WHERE id=?",
            (ref_code, conv_id),
        )
        c.commit()
        return {
            "ok": True,
            "conversion_id": conv_id,
            "ref_code": ref_code,
            "amount_cents": amount_cents,
            "commission_cents": commission,
            "commission_bps": ref["commission_bps"],
        }
    finally:
        c.close()


def pending_payouts() -> list:
    """Aggregate pending commissions per ref, drop below min."""
    c = db()
    try:
        ensure_tables(c)
        rows = c.execute("""
            SELECT l.ref_code, r.wallet, SUM(l.amount_cents) as total_cents, COUNT(l.id) as n
            FROM affiliate_ledger l
            JOIN affiliate_refs r ON l.ref_code = r.code
            WHERE l.status = 'pending'
            GROUP BY l.ref_code
            HAVING total_cents >= ?
        """, (MIN_PAYOUT_CENTS,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def mark_paid(ref_code: str, payout_tx: str) -> dict:
    """Mark all pending ledger entries for ref_code as paid."""
    c = db()
    try:
        ensure_tables(c)
        cur = c.execute(
            "UPDATE affiliate_ledger SET status='paid', payout_tx=? "
            "WHERE ref_code=? AND status='pending'",
            (payout_tx, ref_code),
        )
        c.commit()
        return {"ok": True, "rows": cur.rowcount, "payout_tx": payout_tx}
    finally:
        c.close()


def report(ref_code: Optional[str] = None, days: int = 30) -> dict:
    c = db()
    try:
        ensure_tables(c)
        params = [f"-{days} days"]
        where = "WHERE c.ts >= datetime('now', ?)"
        if ref_code:
            where += " AND c.ref_code = ?"
            params.append(ref_code)

        rows = c.execute(f"""
            SELECT c.ref_code, c.source, COUNT(*) as convs,
                   COALESCE(SUM(c.amount_cents), 0) as sales_cents,
                   COALESCE(SUM(c.commission_cents), 0) as earned_cents,
                   COALESCE(SUM(CASE WHEN l.status='paid' THEN l.amount_cents ELSE 0 END), 0) as paid_cents
            FROM affiliate_conversions c
            LEFT JOIN affiliate_ledger l ON c.payout_id = l.id
            {where}
            GROUP BY c.ref_code, c.source
            ORDER BY earned_cents DESC
        """, params).fetchall()
        return {
            "days": days,
            "ref_code": ref_code,
            "rows": [dict(r) for r in rows],
            "generated_at": _now(),
        }
    finally:
        c.close()