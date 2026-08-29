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


def signup(wallet: Optional[str] = None,
           commission_bps: int = DEFAULT_COMMISSION_BPS,
           label: Optional[str] = None,
           prefix: str = "REF") -> dict:
    """Create a new affiliate ref, return {ref_id, referral_url, ...}.

    Auto-generates a unique ref code and an empty wallet placeholder when
    `wallet` is omitted (affiliate can supply their payout address later
    via /v1/affiliate/register).
    """
    if wallet is None:
        wallet = ""  # placeholder; affiliate sets real payout wallet later
    code = generate_code(prefix=prefix)
    c = db()
    try:
        ensure_tables(c)
        c.execute(
            "INSERT INTO affiliate_refs (code, wallet, commission_bps, label) VALUES (?,?,?,?)",
            (code, wallet, commission_bps, label),
        )
        c.commit()
        row = c.execute("SELECT * FROM affiliate_refs WHERE code = ?", (code,)).fetchone()
        base = os.environ.get("AFFILIATE_BASE_URL", "https://empire-ai.co.uk/r/")
        referral_url = f"{base.rstrip('/')}/{code}"
        return {
            "ref_id": code,
            "referral_url": referral_url,
            "wallet": wallet,
            "commission_bps": commission_bps,
            "label": label,
        }
    finally:
        c.close()


def dashboard(ref_id: str, days: int = 30) -> dict:
    """Affiliate dashboard: conversions, payouts, earnings, 30-d activity."""
    c = db()
    try:
        ensure_tables(c)
        ref = c.execute(
            "SELECT * FROM affiliate_refs WHERE code = ? AND active = 1",
            (ref_id,),
        ).fetchone()
        if not ref:
            return {"ok": False, "error": "ref_not_found_or_inactive", "ref_id": ref_id}
        ref = dict(ref)
        base = os.environ.get("AFFILIATE_BASE_URL", "https://empire-ai.co.uk/r/")
        referral_url = f"{base.rstrip('/')}/{ref_id}"

        # --- conversion aggregates ---
        agg = c.execute(
            """
            SELECT
                COUNT(*)                                          AS conversions_count,
                COALESCE(SUM(amount_cents), 0)                    AS total_sales_cents,
                COALESCE(SUM(commission_cents), 0)                AS total_earned_cents,
                COALESCE(SUM(CASE WHEN status='paid'    THEN commission_cents ELSE 0 END), 0) AS paid_cents,
                COALESCE(SUM(CASE WHEN status='pending'  THEN commission_cents ELSE 0 END), 0) AS pending_cents
            FROM affiliate_conversions
            WHERE ref_code = ?
            """,
            (ref_id,),
        ).fetchone()
        agg = dict(agg) if agg else {}
        conversions_count = int(agg.get("conversions_count") or 0)
        total_sales_cents = int(agg.get("total_sales_cents") or 0)
        total_earned_cents = int(agg.get("total_earned_cents") or 0)
        paid_cents = int(agg.get("paid_cents") or 0)
        pending_cents = int(agg.get("pending_cents") or 0)

        # --- ledger aggregates (pending_payout_usd derived from ledger) ---
        lag = c.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status='pending' THEN amount_cents ELSE 0 END), 0) AS ledger_pending_cents,
                COALESCE(SUM(CASE WHEN status='paid'    THEN amount_cents ELSE 0 END), 0) AS ledger_paid_cents
            FROM affiliate_ledger
            WHERE ref_code = ?
            """,
            (ref_id,),
        ).fetchone()
        lag = dict(lag) if lag else {}
        ledger_pending_cents = int(lag.get("ledger_pending_cents") or 0)
        ledger_paid_cents = int(lag.get("ledger_paid_cents") or 0)

        # conversion_rate = conversions_count / total_sales? No.
        # Define conversion_rate as paid_conversions / total_conversions.
        paid_count = c.execute(
            "SELECT COUNT(*) FROM affiliate_conversions WHERE ref_code = ? AND status = 'paid'",
            (ref_id,),
        ).fetchone()[0]
        conversion_rate = round((paid_count / conversions_count) * 100, 2) if conversions_count else 0.0

        # --- 30-day activity (per-day counts) ---
        activity_rows = c.execute(
            """
            SELECT date(ts) AS day, COUNT(*) AS n,
                   COALESCE(SUM(commission_cents), 0) AS earned_cents
            FROM affiliate_conversions
            WHERE ref_code = ? AND ts >= datetime('now', ?)
            GROUP BY day ORDER BY day DESC
            """,
            (ref_id, f"-{days} days"),
        ).fetchall()
        activity_30d = [
            {"day": r["day"], "conversions": r["n"],
             "earned_cents": int(r["earned_cents"] or 0)}
            for r in activity_rows
        ]

        # --- recent conversions (last 20, newest first) ---
        recent = c.execute(
            """
            SELECT id, ts, source, amount_cents, commission_cents, status,
                   buyer_wallet, payout_id
            FROM affiliate_conversions
            WHERE ref_code = ?
            ORDER BY id DESC LIMIT 20
            """,
            (ref_id,),
        ).fetchall()
        recent_conversions = [
            {"id": r["id"], "ts": r["ts"], "source": r["source"],
             "amount_cents": int(r["amount_cents"] or 0),
             "commission_cents": int(r["commission_cents"] or 0),
             "status": r["status"],
             "buyer_wallet": r["buyer_wallet"],
             "payout_id": r["payout_id"]}
            for r in recent
        ]

        return {
            "ok": True,
            "ref_id": ref_id,
            "referral_url": referral_url,
            "wallet": ref.get("wallet", ""),
            "commission_bps": int(ref.get("commission_bps") or 0),
            "conversions_count": conversions_count,
            "pending_payout_cents": ledger_pending_cents,
            "pending_payout_usd": round(ledger_pending_cents / 100, 2),
            "total_earned_cents": total_earned_cents,
            "total_earned_usd": round(total_earned_cents / 100, 2),
            "paid_out_cents": ledger_paid_cents,
            "paid_out_usd": round(ledger_paid_cents / 100, 2),
            "conversion_rate_pct": conversion_rate,
            "total_sales_cents": total_sales_cents,
            "total_sales_usd": round(total_sales_cents / 100, 2),
            "recent_conversions": recent_conversions,
            "activity_30d": activity_30d,
            "generated_at": _now(),
        }
    finally:
        c.close()


def payouts(ref_id: Optional[str] = None, limit: int = 100) -> dict:
    """Payout history (paid ledger entries) + pending totals."""
    c = db()
    try:
        ensure_tables(c)
        params: list = []
        where = ""
        if ref_id:
            where = "WHERE ref_code = ?"
            params.append(ref_id)
        # Paid (historical) payouts
        paid_rows = c.execute(
            f"""
            SELECT id, ts, ref_code, amount_cents, payout_tx, status
            FROM affiliate_ledger {where} AND status = 'paid'
            ORDER BY id DESC LIMIT ?
            """,
            params + [limit],
        ) if ref_id else c.execute(
            f"""
            SELECT id, ts, ref_code, amount_cents, payout_tx, status
            FROM affiliate_ledger WHERE status = 'paid'
            ORDER BY id DESC LIMIT ?
            """,
            [limit],
        )
        paid = [
            {"id": r["id"], "ts": r["ts"], "ref_code": r["ref_code"],
             "amount_cents": int(r["amount_cents"] or 0),
             "amount_usd": round(int(r["amount_cents"] or 0) / 100, 2),
             "payout_tx": r["payout_tx"], "status": r["status"]}
            for r in paid_rows
        ]
        # Pending summary
        pending_rows = c.execute(
            f"""
            SELECT ref_code, COUNT(*) AS n,
                   COALESCE(SUM(amount_cents), 0) AS pending_cents,
                   MIN(ts) AS oldest_ts, MAX(ts) AS newest_ts
            FROM affiliate_ledger {where} AND status = 'pending'
            GROUP BY ref_code ORDER BY pending_cents DESC
            """
            if ref_id else
            """
            SELECT ref_code, COUNT(*) AS n,
                   COALESCE(SUM(amount_cents), 0) AS pending_cents,
                   MIN(ts) AS oldest_ts, MAX(ts) AS newest_ts
            FROM affiliate_ledger WHERE status = 'pending'
            GROUP BY ref_code ORDER BY pending_cents DESC
            """,
            params if ref_id else [],
        ).fetchall()
        pending = [
            {"ref_code": r["ref_code"], "count": r["n"],
             "pending_cents": int(r["pending_cents"] or 0),
             "pending_usd": round(int(r["pending_cents"] or 0) / 100, 2),
             "oldest_ts": r["oldest_ts"], "newest_ts": r["newest_ts"]}
            for r in pending_rows
        ]
        total_pending_cents = sum(p["pending_cents"] for p in pending)
        total_paid_cents = sum(p["amount_cents"] for p in paid)
        return {
            "ok": True,
            "ref_id": ref_id,
            "paid": paid,
            "paid_count": len(paid),
            "paid_total_cents": total_paid_cents,
            "paid_total_usd": round(total_paid_cents / 100, 2),
            "pending": pending,
            "pending_count": sum(p["count"] for p in pending),
            "pending_total_cents": total_pending_cents,
            "pending_total_usd": round(total_pending_cents / 100, 2),
            "generated_at": _now(),
        }
    finally:
        c.close()


def request_payout(ref_id: str, wallet: Optional[str] = None) -> dict:
    """Trigger a payout request: aggregate pending commissions per ref,
    create a settlement record (si_settlements row), mark ledger as
    'requested' (intermediate state). Returns settlement info.
    """
    c = db()
    try:
        ensure_tables(c)
        ref = c.execute(
            "SELECT * FROM affiliate_refs WHERE code = ? AND active = 1",
            (ref_id,),
        ).fetchone()
        if not ref:
            return {"ok": False, "error": "ref_not_found_or_inactive", "ref_id": ref_id}
        ref = dict(ref)
        # Aggregate pending commissions for this ref
        agg = c.execute(
            """
            SELECT COUNT(*) AS n,
                   COALESCE(SUM(amount_cents), 0) AS total_cents,
                   MIN(id) AS first_id, MAX(id) AS last_id
            FROM affiliate_ledger
            WHERE ref_code = ? AND status = 'pending'
            """,
            (ref_id,),
        ).fetchone()
        agg = dict(agg) if agg else {}
        n = int(agg.get("n") or 0)
        total_cents = int(agg.get("total_cents") or 0)
        if n == 0 or total_cents == 0:
            return {"ok": False, "error": "no_pending_payout",
                    "ref_id": ref_id, "pending_cents": 0}
        payout_wallet = wallet or ref.get("wallet") or ""
        if not payout_wallet:
            return {"ok": False, "error": "no_payout_wallet",
                    "ref_id": ref_id,
                    "hint": "Provide ?wallet= or set wallet via /v1/affiliate/register"}
        # Create a settlement record in si_settlements (audit table).
        # prospect_id encodes affiliate:<ref_id>:<first_id>-<last_id>
        c.execute(
            """
            INSERT INTO si_settlements
              (prospect_id, tenant_id, amount_cents, settled_at,
               settled_by, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"affiliate:{ref_id}:{agg['first_id']}-{agg['last_id']}",
             payout_wallet,
             total_cents,
             _now(),
             "affiliate_payout_endpoint",
             f"Affiliate payout request for {n} pending commissions ref={ref_id}"),
        )
        settlement_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Mark the pending ledger entries as 'requested' (intermediate state
        # before the on-chain payout_scheduler marks them 'paid').
        cur = c.execute(
            "UPDATE affiliate_ledger SET status='requested' "
            "WHERE ref_code = ? AND status = 'pending'",
            (ref_id,),
        )
        rows_marked = cur.rowcount
        # Also flip the linked conversions' status to 'requested' so the
        # dashboard reflects the in-flight payout.
        c.execute(
            "UPDATE affiliate_conversions SET status='requested' "
            "WHERE ref_code = ? AND status = 'pending'",
            (ref_id,),
        )
        c.commit()
        return {
            "ok": True,
            "ref_id": ref_id,
            "settlement_id": settlement_id,
            "payout_wallet": payout_wallet,
            "ledger_entries_marked": rows_marked,
            "amount_cents": total_cents,
            "amount_usd": round(total_cents / 100, 2),
            "status": "requested",
            "message": "Payout requested. Settlement record created; "
                       "payout_scheduler will broadcast the on-chain USDC transfer.",
        }
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