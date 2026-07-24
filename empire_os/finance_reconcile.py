#!/usr/bin/env python3
"""
finance_reconcile.py — Unmatched USDC deposit reconciliation.

When a buyer pays via Phantom/TokenPocket (no memo support on SPL transfers),
the solana_listener_agent sees the deposit land in the vault but cannot
match it to any pending si_charges row. Without this module, those funds
sit unallocated forever. With it, every unmatched deposit is captured to
si_unmatched_deposits and can be attributed to a buyer manually.

Flow:
  1. listener sees usdc_incoming, no matching open charge by amount+memo
  2. listener (or a daily cron) calls record_unmatched() with tx signature,
     amount, sender, vault balance
  3. operator reviews via GET /v1/finance/unmatched
  4. operator says "this 7-cent deposit pays for buyer X's seat"
  5. POST /v1/finance/attribute {tx, buyer_id} -> creates si_charges row,
     flips si_unmatched_deposits.status to 'attributed', writes si_settlements

Schema is created on import. Idempotent.
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

DB = "/root/empire_os/empire_os.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_unmatched_deposits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_signature    TEXT NOT NULL UNIQUE,
    amount_usdc     REAL NOT NULL,
    amount_cents    INTEGER NOT NULL,
    sender_wallet   TEXT NOT NULL DEFAULT '',
    vault_wallet    TEXT NOT NULL,
    vault_balance_after_usdc REAL,
    received_at     TEXT NOT NULL,
    block_time      INTEGER,
    status          TEXT NOT NULL DEFAULT 'unmatched',  -- unmatched | attributed | refunded | voided
    matched_buyer_id TEXT DEFAULT '',
    matched_charge_id TEXT DEFAULT '',
    matched_at      TEXT,
    notes           TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_unmatched_status ON si_unmatched_deposits(status, received_at);
CREATE INDEX IF NOT EXISTS idx_unmatched_amount ON si_unmatched_deposits(amount_cents, status);
"""


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def ensure_schema() -> None:
    c = _conn()
    c.executescript(SCHEMA_SQL)
    c.commit()
    c.close()


@dataclass
class UnmatchedDeposit:
    tx_signature: str
    amount_usdc: float
    vault_wallet: str
    received_at: str
    sender_wallet: str = ""
    vault_balance_after_usdc: float = 0.0
    block_time: int = 0
    notes: str = ""


def record_unmatched(d: UnmatchedDeposit) -> dict:
    """Record an unmatched deposit. Idempotent on tx_signature (INSERT OR IGNORE)."""
    ensure_schema()
    cents = int(round(d.amount_usdc * 1_000_000))  # USDC has 6 decimals
    # Convert micro-USDC to "cents" (USD). For a USDC deposit where 1 USDC = $1,
    # cents = micro_usdc / 10000. Example: 0.07 USDC = 70000 micro = 7 cents.
    cents_usd = cents // 10000

    c = _conn()
    try:
        cur = c.execute(
            """INSERT OR IGNORE INTO si_unmatched_deposits
               (tx_signature, amount_usdc, amount_cents, sender_wallet,
                vault_wallet, vault_balance_after_usdc, received_at,
                block_time, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unmatched', ?)""",
            (d.tx_signature, d.amount_usdc, cents_usd, d.sender_wallet,
             d.vault_wallet, d.vault_balance_after_usdc, d.received_at,
             d.block_time, d.notes))
        c.commit()
        inserted = cur.rowcount > 0
        if not inserted:
            row = c.execute(
                "SELECT id, status FROM si_unmatched_deposits WHERE tx_signature=?",
                (d.tx_signature,)).fetchone()
            return {
                "ok": True, "duplicate": True,
                "id": row["id"], "status": row["status"]}
        return {"ok": True, "duplicate": False, "id": cur.lastrowid,
                "amount_cents": cents_usd, "amount_usdc": d.amount_usdc}
    finally:
        c.close()


def list_unmatched(limit: int = 50, status: str = "unmatched") -> list[dict]:
    ensure_schema()
    c = _conn()
    try:
        rows = c.execute(
            """SELECT * FROM si_unmatched_deposits
               WHERE status = ?
               ORDER BY received_at DESC
               LIMIT ?""",
            (status, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def _resolve_buyer(buyer_id: str) -> dict:
    """Resolve buyer_id to a real tenant in si_tenant.

    Accepts three forms:
      1. tenant_id (UUID)         — direct lookup
      2. crypto_wallet (base58)   — lookup by wallet
      3. email                    — lookup by email

    Returns {ok, tenant_id, form, reason}. On no-match returns
    {ok: False, reason: "..."}. Never silently defaults to 'default'.
    """
    c = _conn()
    try:
        # 1) tenant_id
        row = c.execute(
            "SELECT tenant_id, name, email, crypto_wallet, plan "
            "FROM si_tenant WHERE tenant_id=?",
            (buyer_id,)).fetchone()
        if row:
            return {"ok": True, "tenant_id": row["tenant_id"],
                    "form": "tenant_id", "email": row["email"],
                    "name": row["name"], "plan": row["plan"]}
        # 2) crypto_wallet
        row = c.execute(
            "SELECT tenant_id, name, email, crypto_wallet, plan "
            "FROM si_tenant WHERE crypto_wallet=?",
            (buyer_id,)).fetchone()
        if row:
            return {"ok": True, "tenant_id": row["tenant_id"],
                    "form": "crypto_wallet", "email": row["email"],
                    "name": row["name"], "plan": row["plan"]}
        # 3) email
        row = c.execute(
            "SELECT tenant_id, name, email, crypto_wallet, plan "
            "FROM si_tenant WHERE email=? OR delivery_email=?",
            (buyer_id, buyer_id)).fetchone()
        if row:
            return {"ok": True, "tenant_id": row["tenant_id"],
                    "form": "email", "email": row["email"],
                    "name": row["name"], "plan": row["plan"]}
        return {"ok": False, "reason": f"no tenant matched buyer_id={buyer_id!r}",
                "buyer_id": buyer_id}
    finally:
        c.close()


def attribute_deposit(tx_signature: str, buyer_id: str,
                       reason: str = "manual_attribute") -> dict:
    """Link an unmatched deposit to a real tenant.

    Resolves buyer_id (tenant_id / wallet / email) to a si_tenant row.
    REJECTS unknown buyers rather than silently aggregating to
    'default' tenant — fixes the multi-tenant ledger hazard the audit
    flagged (Q2).

    Creates a synthetic si_charges row (status='succeeded'), writes a
    si_settlements entry with the REAL tenant_id, flips the deposit to
    status='attributed'.

    Returns dict with ok/error and the linked ids.
    """
    ensure_schema()
    c = _conn()
    try:
        dep = c.execute(
            "SELECT * FROM si_unmatched_deposits WHERE tx_signature=?",
            (tx_signature,)).fetchone()
        if not dep:
            return {"ok": False, "error": f"no deposit with tx={tx_signature}"}
        dep = dict(dep)
        if dep["status"] != "unmatched":
            return {"ok": False, "error": f"deposit already {dep['status']}",
                    "matched_buyer_id": dep.get("matched_buyer_id"),
                    "matched_charge_id": dep.get("matched_charge_id")}

        # Resolve buyer to a real tenant. NO silent 'default'.
        resolved = _resolve_buyer(buyer_id)
        if not resolved["ok"]:
            return {"ok": False, "error": resolved["reason"],
                    "hint": "buyer_id must be a tenant_id, crypto_wallet, "
                            "or email of an existing si_tenant row"}

        tenant_id = resolved["tenant_id"]

        # Generate ids
        import hashlib as _hl
        charge_id = "chg_attr_" + _hl.sha256(tx_signature.encode()).hexdigest()[:16]
        matched_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

        # Insert si_charges. buyer_id = tenant_id (canonical form).
        try:
            c.execute(
                """INSERT INTO si_charges
                   (charge_id, buyer_id, processor, customer_ref, payment_ref,
                    head, reason, amount_cents, currency, status,
                    processor_response, attempt_count, created_at, paid_at)
                   VALUES (?, ?, 'usdc', '', ?, 2, ?, ?, 'USDC', 'succeeded',
                           ?, 1, ?, ?)""",
                (charge_id, tenant_id, tx_signature,
                 f"attributed from unmatched deposit {tx_signature[:20]} "
                 f"({reason}; buyer input={buyer_id} resolved via "
                 f"{resolved['form']})",
                 dep["amount_cents"],
                 json.dumps({"tx_signature": tx_signature,
                             "via": "finance_reconcile",
                             "buyer_input": buyer_id,
                             "resolved_form": resolved["form"]}),
                 dep["received_at"], matched_at))
        except sqlite3.IntegrityError as e:
            return {"ok": False, "error": f"charge insert failed: {e}"}

        # Insert si_settlements with REAL tenant_id (was 'default' before —
        # that was a multi-tenant ledger bug).
        try:
            c.execute(
                """INSERT INTO si_settlements
                   (prospect_id, tenant_id, amount_cents, settled_at, settled_by, notes)
                   VALUES (?, ?, ?, ?, 'finance_reconcile', ?)""",
                (tenant_id, tenant_id, dep["amount_cents"], matched_at,
                 f"attributed from unmatched deposit tx={tx_signature[:20]}"))
        except sqlite3.IntegrityError:
            pass  # si_settlements may not have all columns; ignore

        # Flip deposit status
        c.execute(
            """UPDATE si_unmatched_deposits
               SET status='attributed', matched_buyer_id=?, matched_charge_id=?,
                   matched_at=?, notes=notes || ?
               WHERE tx_signature=?""",
            (tenant_id, charge_id, matched_at,
             f"\n[{matched_at}] attributed to tenant={tenant_id} "
             f"(input={buyer_id} via {resolved['form']}): {reason}",
             tx_signature))
        c.commit()

        return {"ok": True, "charge_id": charge_id, "buyer_id": tenant_id,
                "buyer_input": buyer_id,
                "resolved_form": resolved["form"],
                "tenant_email": resolved.get("email"),
                "amount_cents": dep["amount_cents"],
                "amount_usdc": dep["amount_usdc"],
                "matched_at": matched_at}
    finally:
        c.close()


def stats() -> dict:
    """Aggregate stats for the unmatched queue."""
    ensure_schema()
    c = _conn()
    try:
        rows = c.execute(
            """SELECT status, COUNT(*) as n,
                      COALESCE(SUM(amount_usdc), 0) as total_usdc
               FROM si_unmatched_deposits
               GROUP BY status""").fetchall()
        by_status = {r["status"]: {"count": r["n"], "total_usdc": r["total_usdc"]}
                     for r in rows}
        vault_balance = c.execute(
            """SELECT COALESCE(vault_balance_after_usdc, 0)
               FROM si_unmatched_deposits
               ORDER BY received_at DESC LIMIT 1""").fetchone()
        return {
            "by_status": by_status,
            "vault_balance_last_seen_usdc": vault_balance[0] if vault_balance else 0,
        }
    finally:
        c.close()


if __name__ == "__main__":
    import sys
    ensure_schema()
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for d in list_unmatched(limit=20):
            print(json.dumps({k: d[k] for k in (
                "tx_signature", "amount_usdc", "amount_cents",
                "sender_wallet", "vault_wallet", "received_at",
                "status", "matched_buyer_id")}, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(stats(), indent=2))
    else:
        print("finance_reconcile.py — unmatched deposit attribution")
        print("  list   - list unmatched deposits")
        print("  stats  - aggregate stats")