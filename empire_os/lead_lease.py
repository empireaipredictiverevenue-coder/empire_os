#!/usr/bin/env python3
"""lead_lease — Time-bound access to lane_leads rows.

Unlike pay-per-lead (immediate billing per delivery), a lease reserves
exclusive access to N leads in (niche, metro) for a fixed duration.
Buyer prepays USDC; reservations tracked in lane_leads.lease_id +
lease table; expiry auto-frees rows.

Tables:
  lead_leases(lease_id, buyer_wallet, niche, metro, max_leads, used_leads,
              price_usdc, starts_at, expires_at, status, quote_id)

Status: pending → active → expired | renewed | cancelled
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")

LEASE_DURATION_DAYS = int(os.getenv("LEASE_DURATION_DAYS", "30"))
PRICE_PER_LEAD_USDC = float(os.getenv("LEASE_PRICE_PER_LEAD_USDC", "8.0"))  # bulk discount vs $12 PPL


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_tables(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS lead_leases (
            lease_id TEXT PRIMARY KEY,
            buyer_wallet TEXT NOT NULL,
            niche TEXT NOT NULL,
            metro TEXT,
            max_leads INTEGER NOT NULL,
            used_leads INTEGER DEFAULT 0,
            price_usdc REAL NOT NULL,
            quote_id TEXT,
            starts_at TEXT,
            expires_at TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    # Add lease_id column to lane_leads if missing
    cols = [r[1] for r in c.execute("PRAGMA table_info(lane_leads)").fetchall()]
    if "lease_id" not in cols:
        c.execute("ALTER TABLE lane_leads ADD COLUMN lease_id TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lane_leads_lease ON lane_leads(lease_id)")
    c.commit()


def compute_price(max_leads: int, niche: str = "") -> float:
    """Lease price = N * bulk rate. Optional niche multiplier."""
    base = max_leads * PRICE_PER_LEAD_USDC
    return round(base, 2)


def create_lease(niche: str, metro: str, max_leads: int, buyer_wallet: str,
                 quote_id: Optional[str] = None) -> dict:
    """Create a lease reservation. Returns lease details + price."""
    c = db()
    try:
        ensure_tables(c)
        lease_id = f"lease_{uuid.uuid4().hex[:12]}"
        price = compute_price(max_leads, niche)
        starts = _now()
        expires = (datetime.now(timezone.utc) + timedelta(days=LEASE_DURATION_DAYS)).isoformat()

        c.execute(
            "INSERT INTO lead_leases (lease_id, buyer_wallet, niche, metro, max_leads, "
            "price_usdc, quote_id, starts_at, expires_at, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (lease_id, buyer_wallet, niche, metro, max_leads, price,
             quote_id, starts, expires, "pending"),
        )
        c.commit()
        return {
            "lease_id": lease_id,
            "buyer_wallet": buyer_wallet,
            "niche": niche,
            "metro": metro,
            "max_leads": max_leads,
            "used_leads": 0,
            "price_usdc": price,
            "starts_at": starts,
            "expires_at": expires,
            "duration_days": LEASE_DURATION_DAYS,
            "status": "pending",
            "pay_quote": quote_id,
        }
    finally:
        c.close()


def activate_lease(lease_id: str, deposit_tx: str) -> dict:
    """Activate lease after funding confirmed. Reserves available leads."""
    c = db()
    try:
        ensure_tables(c)
        lease = c.execute("SELECT * FROM lead_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not lease:
            return {"ok": False, "error": "lease_not_found"}
        if lease["status"] != "pending":
            return {"ok": False, "error": f"invalid_status:{lease['status']}"}

        # Reserve available leads matching niche/metro
        params = [lease["niche"]]
        metro_clause = ""
        if lease["metro"]:
            metro_clause = " AND metro = ?"
            params.append(lease["metro"])

        available = c.execute(
            f"SELECT COUNT(*) FROM lane_leads WHERE niche = ?{metro_clause} "
            f"AND (lease_id IS NULL OR lease_id = '') "
            f"AND (status IS NULL OR status = 'pending' OR status = 'new')",
            params,
        ).fetchone()[0]

        if available < lease["max_leads"]:
            c.execute(
                "UPDATE lead_leases SET status='failed', used_leads=0 WHERE lease_id=?",
                (lease_id,),
            )
            c.commit()
            return {
                "ok": False,
                "error": f"insufficient_leads:need={lease['max_leads']}_have={available}",
            }

        # Reserve them
        c.execute(f"""
            UPDATE lane_leads SET lease_id = ?
            WHERE id IN (
                SELECT id FROM lane_leads
                WHERE niche = ? {"AND metro = ?" if lease["metro"] else ""}
                AND (lease_id IS NULL OR lease_id = '')
                AND (status IS NULL OR status = 'pending' OR status = 'new')
                LIMIT ?
            )
        """, [lease_id, lease["niche"]] + ([lease["metro"]] if lease["metro"] else []) + [lease["max_leads"]])

        c.execute(
            "UPDATE lead_leases SET status='active', used_leads=0 WHERE lease_id=?",
            (lease_id,),
        )
        c.commit()

        return {
            "ok": True,
            "lease_id": lease_id,
            "status": "active",
            "reserved": lease["max_leads"],
            "deposit_tx": deposit_tx,
        }
    finally:
        c.close()


def consume_lease_lead(lease_id: str, prospect_id: str) -> dict:
    """Mark a leased lead as consumed (delivered to buyer)."""
    c = db()
    try:
        ensure_tables(c)
        lease = c.execute("SELECT * FROM lead_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not lease:
            return {"ok": False, "error": "lease_not_found"}
        if lease["status"] != "active":
            return {"ok": False, "error": f"not_active:{lease['status']}"}

        # Check expiry
        if datetime.fromisoformat(lease["expires_at"]) < datetime.now(timezone.utc):
            c.execute("UPDATE lead_leases SET status='expired' WHERE lease_id=?", (lease_id,))
            c.commit()
            return {"ok": False, "error": "expired"}

        # Verify the lead belongs to this lease
        row = c.execute(
            "SELECT id FROM lane_leads WHERE prospect_id = ? AND lease_id = ?",
            (prospect_id, lease_id),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "lead_not_in_lease"}

        c.execute(
            "UPDATE lane_leads SET status = 'delivered' WHERE prospect_id = ?",
            (prospect_id,),
        )
        new_used = lease["used_leads"] + 1
        c.execute(
            "UPDATE lead_leases SET used_leads = ? WHERE lease_id = ?",
            (new_used, lease_id),
        )
        c.commit()
        return {
            "ok": True,
            "lease_id": lease_id,
            "used_leads": new_used,
            "max_leads": lease["max_leads"],
            "remaining": lease["max_leads"] - new_used,
        }
    finally:
        c.close()


def expire_due_leases() -> int:
    """Background helper: mark all expired leases."""
    c = db()
    try:
        ensure_tables(c)
        cur = c.execute(
            "UPDATE lead_leases SET status='expired' "
            "WHERE status='active' AND expires_at < datetime('now')"
        )
        c.commit()
        return cur.rowcount
    finally:
        c.close()


def get_lease(lease_id: str) -> Optional[dict]:
    c = db()
    try:
        ensure_tables(c)
        row = c.execute("SELECT * FROM lead_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        return dict(row) if row else None
    finally:
        c.close()


def list_leases(buyer_wallet: Optional[str] = None, status: Optional[str] = None,
                limit: int = 50) -> list:
    c = db()
    try:
        ensure_tables(c)
        q = "SELECT * FROM lead_leases WHERE 1=1"
        params = []
        if buyer_wallet:
            q += " AND buyer_wallet = ?"
            params.append(buyer_wallet)
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in c.execute(q, params).fetchall()]
    finally:
        c.close()


def renew_lease(lease_id: str, extra_days: int = 30) -> dict:
    """Extend an expired or active lease by N days."""
    c = db()
    try:
        ensure_tables(c)
        lease = c.execute("SELECT * FROM lead_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        if not lease:
            return {"ok": False, "error": "lease_not_found"}
        if lease["status"] not in ("active", "expired"):
            return {"ok": False, "error": f"cannot_renew:{lease['status']}"}

        base = datetime.fromisoformat(lease["expires_at"])
        if base < datetime.now(timezone.utc):
            base = datetime.now(timezone.utc)
        new_expiry = (base + timedelta(days=extra_days)).isoformat()

        c.execute(
            "UPDATE lead_leases SET expires_at=?, status='active' WHERE lease_id=?",
            (new_expiry, lease_id),
        )
        c.commit()
        return {"ok": True, "lease_id": lease_id, "expires_at": new_expiry, "extra_days": extra_days}
    finally:
        c.close()