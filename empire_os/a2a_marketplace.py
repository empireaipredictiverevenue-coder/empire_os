#!/usr/bin/env python3
"""a2a_marketplace — Signed quotes + escrow ledger for A2A products.

Each A2A product (lead_lane, strike_pack, ai_closer, etc.) gets a
signed quote with vault signature, amount, expiry. On deposit to vault
with matching memo, escrow state flips to 'held'. On delivery (manual
or programmatic), state flips to 'released' and the platform fee is
retained.

Tables:
  a2a_quotes(quote_id, product, buyer_wallet, amount_usdc, signed_payload,
             vault_sig, expires_at, status, created_at)
  a2a_escrow(quote_id, deposit_tx, held_at, released_at, refunded_at,
             delivery_proof)

Status: pending → funded → delivered → released
                ↓
              refunded
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
VAULT_WALLET = os.getenv("SOLANA_VAULT_WALLET", "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM")
QUOTE_TTL_MINUTES = int(os.getenv("A2A_QUOTE_TTL_MINUTES", "30"))
PLATFORM_FEE_BPS = int(os.getenv("A2A_PLATFORM_FEE_BPS", "1500"))  # 15%

PRODUCT_PRICING = {
    "lead_lane": {"unit": "lead", "base_usdc": 12.0},
    "satellite_wastage": {"unit": "report", "base_usdc": 35.0},
    "warehouse_asset": {"unit": "month", "base_usdc": 99.0},
    "strike_pack": {"unit": "pack", "base_usdc": 250.0},
    "ai_closer": {"unit": "month", "base_usdc": 599.0},
    "leadflow_saas_t2": {"unit": "month", "base_usdc": 1499.0},
    "imperium_conversion_os": {"unit": "month", "base_usdc": 4999.0},
    "empire_os_v4_beta": {"unit": "month", "base_usdc": 999.0},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c


def ensure_tables(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS a2a_quotes (
            quote_id TEXT PRIMARY KEY,
            product TEXT NOT NULL,
            buyer_wallet TEXT NOT NULL,
            amount_usdc REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            signed_payload TEXT NOT NULL,
            vault_sig TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            meta TEXT
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS a2a_escrow (
            quote_id TEXT PRIMARY KEY,
            deposit_tx TEXT,
            held_at TEXT,
            released_at TEXT,
            refunded_at TEXT,
            delivery_proof TEXT,
            FOREIGN KEY(quote_id) REFERENCES a2a_quotes(quote_id)
        )""")
    c.commit()


def compute_amount(product: str, quantity: int = 1) -> float:
    """Total USDC for product + qty, including platform fee."""
    cfg = PRODUCT_PRICING.get(product)
    if not cfg:
        raise ValueError(f"Unknown product: {product}")
    subtotal = cfg["base_usdc"] * quantity
    fee = subtotal * PLATFORM_FEE_BPS / 10000
    return round(subtotal + fee, 2)


def _sign_payload(payload: dict) -> str:
    """Sign payload with vault keypair (HMAC fallback if no keypair)."""
    secret = os.getenv("SOLANA_PAYER_SECRET", "")
    body = json.dumps(payload, sort_keys=True)
    if secret:
        try:
            import base58
            from solders.keypair import Keypair
            kp = Keypair.from_bytes(base58.b58decode(secret))
            sig = kp.sign_message(body.encode())
            return base58.b58encode(bytes(sig)).decode()
        except Exception:
            pass
    # HMAC fallback (development mode)
    h = hashlib.sha256((body + secret).encode()).hexdigest()
    return f"hmac:{h[:64]}"


def create_quote(product: str, buyer_wallet: str, quantity: int = 1,
                 meta: Optional[dict] = None) -> dict:
    """Build a signed quote for buyer to pay into vault."""
    c = db()
    try:
        ensure_tables(c)
        quote_id = f"q_{uuid.uuid4().hex[:12]}"
        amount = compute_amount(product, quantity)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=QUOTE_TTL_MINUTES)).isoformat()

        payload = {
            "quote_id": quote_id,
            "product": product,
            "quantity": quantity,
            "amount_usdc": amount,
            "buyer_wallet": buyer_wallet,
            "vault": VAULT_WALLET,
            "expires_at": expires,
            "ts": _now(),
        }
        signed = json.dumps(payload, sort_keys=True)
        vault_sig = _sign_payload(payload)

        memo = f"a2a:{quote_id}"
        pay_url = (
            f"solana:{VAULT_WALLET}"
            f"?amount={amount:.2f}"
            f"&label=Empire%20A2A%20{product}"
            f"&memo={memo}"
        )

        c.execute(
            "INSERT INTO a2a_quotes (quote_id, product, buyer_wallet, amount_usdc, "
            "quantity, signed_payload, vault_sig, expires_at, meta) VALUES (?,?,?,?,?,?,?,?,?)",
            (quote_id, product, buyer_wallet, amount, quantity, signed,
             vault_sig, expires, json.dumps(meta) if meta else None),
        )
        c.execute("INSERT INTO a2a_escrow (quote_id) VALUES (?)", (quote_id,))
        c.commit()

        return {
            "quote_id": quote_id,
            "product": product,
            "quantity": quantity,
            "amount_usdc": amount,
            "buyer_wallet": buyer_wallet,
            "vault": VAULT_WALLET,
            "expires_at": expires,
            "signed_payload": signed,
            "vault_sig": vault_sig,
            "pay_url": pay_url,
            "memo": memo,
            "status": "pending",
        }
    finally:
        c.close()


def get_quote(quote_id: str) -> Optional[dict]:
    c = db()
    try:
        ensure_tables(c)
        row = c.execute("SELECT * FROM a2a_quotes WHERE quote_id = ?", (quote_id,)).fetchone()
        if not row:
            return None
        escrow_row = c.execute(
            "SELECT * FROM a2a_escrow WHERE quote_id = ?", (quote_id,)
        ).fetchone()
        d = dict(row)
        if escrow_row:
            d["escrow"] = dict(escrow_row)
        return d
    finally:
        c.close()


def fund_quote(quote_id: str, deposit_tx: str) -> dict:
    """Mark quote as funded after solana_listener detects deposit."""
    c = db()
    try:
        ensure_tables(c)
        q = c.execute("SELECT * FROM a2a_quotes WHERE quote_id = ?", (quote_id,)).fetchone()
        if not q:
            return {"ok": False, "error": "quote_not_found"}
        if q["status"] not in ("pending",):
            return {"ok": False, "error": f"invalid_status:{q['status']}"}
        # Check expiry
        expires = datetime.fromisoformat(q["expires_at"])
        if datetime.now(timezone.utc) > expires:
            c.execute("UPDATE a2a_quotes SET status='expired' WHERE quote_id=?", (quote_id,))
            c.commit()
            return {"ok": False, "error": "expired"}

        c.execute("UPDATE a2a_quotes SET status='funded' WHERE quote_id=?", (quote_id,))
        c.execute(
            "UPDATE a2a_escrow SET deposit_tx=?, held_at=? WHERE quote_id=?",
            (deposit_tx, _now(), quote_id),
        )
        c.commit()
        return {"ok": True, "status": "funded", "deposit_tx": deposit_tx}
    finally:
        c.close()


def release_escrow(quote_id: str, delivery_proof: Optional[str] = None) -> dict:
    """Mark escrow released after delivery. Triggers payout."""
    c = db()
    try:
        ensure_tables(c)
        q = c.execute("SELECT * FROM a2a_quotes WHERE quote_id = ?", (quote_id,)).fetchone()
        if not q:
            return {"ok": False, "error": "quote_not_found"}
        if q["status"] != "funded":
            return {"ok": False, "error": f"not_funded:{q['status']}"}
        c.execute("UPDATE a2a_quotes SET status='released' WHERE quote_id=?", (quote_id,))
        c.execute(
            "UPDATE a2a_escrow SET released_at=?, delivery_proof=? WHERE quote_id=?",
            (_now(), delivery_proof, quote_id),
        )
        c.commit()
        return {"ok": True, "status": "released", "delivery_proof": delivery_proof}
    finally:
        c.close()


def refund_escrow(quote_id: str, reason: str = "") -> dict:
    """Mark refunded (e.g. dispute / expiry)."""
    c = db()
    try:
        ensure_tables(c)
        q = c.execute("SELECT * FROM a2a_quotes WHERE quote_id = ?", (quote_id,)).fetchone()
        if not q:
            return {"ok": False, "error": "quote_not_found"}
        if q["status"] in ("released", "refunded"):
            return {"ok": False, "error": f"already_terminal:{q['status']}"}
        c.execute("UPDATE a2a_quotes SET status='refunded' WHERE quote_id=?", (quote_id,))
        c.execute(
            "UPDATE a2a_escrow SET refunded_at=?, delivery_proof=? WHERE quote_id=?",
            (_now(), f"refund:{reason}"),
        )
        c.commit()
        return {"ok": True, "status": "refunded", "reason": reason}
    finally:
        c.close()


def list_quotes(limit: int = 50, status: Optional[str] = None) -> list:
    c = db()
    try:
        ensure_tables(c)
        if status:
            rows = c.execute(
                "SELECT * FROM a2a_quotes WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM a2a_quotes ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()