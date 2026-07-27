#!/usr/bin/env python3
"""payout_scheduler — Hourly USDC sweep from vault → founder wallet.

Reconciles the French cortex vision ($121+/hr flowing to YOUR WALLET)
with real code. Runs every hour via systemd timer.

Flow:
  1. Query si_settlements for amounts not yet paid out
  2. Calculate total pending USDC
  3. If >= MIN_PAYOUT_CENTS, send USDC from vault_ata → founder_wallet
  4. Record payout in payout_log table (prevents double-payouts)
  5. Log everything to stdout for journald

Env vars:
  SOLANA_RPC_URL          — RPC endpoint (default devnet)
  SOLANA_VAULT_WALLET     — vault wallet pubkey (source of USDC)
  SOLANA_VAULT_ATA        — vault's USDC token account (default derived)
  FOUNDER_WALLET          — recipient wallet for payouts
  FOUNDER_ATA             — recipient's USDC token account (default derived)
  SOLANA_PAYER_SECRET     — base58 keypair for signing (must own vault)
  MIN_PAYOUT_CENTS        — minimum trigger amount (default 100 = $1)
  DB_PATH                 — empire db path
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("payout_scheduler")

DB_PATH = os.getenv("DB_PATH", "/root/empire_os/empire_os.db")
MIN_PAYOUT_CENTS = int(os.getenv("MIN_PAYOUT_CENTS", "100"))  # $1 default
SOLANA_VAULT_WALLET = os.getenv("SOLANA_VAULT_WALLET", "")
FOUNDER_WALLET = os.getenv("FOUNDER_WALLET", SOLANA_VAULT_WALLET)
SOLANA_PAYER_SECRET = os.getenv("SOLANA_PAYER_SECRET", "")
USDC_MINT_STR = os.getenv("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")


def _derive_ata(owner: str) -> str:
    """Derive associated token account for owner + USDC mint."""
    try:
        from solders.pubkey import Pubkey
        from solders.associated_token_account import get_associated_token_address

        owner_pk = Pubkey.from_string(owner)
        mint_pk = Pubkey.from_string(USDC_MINT_STR)
        ata = get_associated_token_address(owner_pk, mint_pk)
        return str(ata)
    except ImportError:
        # Fallback: solders missing or no ATA module, use raw address
        logger.warning("solders ATA module not available, using raw wallet as ATA")
        return owner


def _ensure_log_table(c: sqlite3.Connection):
    """Create payout_log table if it doesn't exist."""
    c.execute("""
        CREATE TABLE IF NOT EXISTS payout_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            settled_at TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            usdc_amount REAL NOT NULL,
            from_wallet TEXT,
            to_wallet TEXT,
            tx_sig TEXT,
            status TEXT DEFAULT 'pending',
            meta TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
    c.commit()


def _get_pending_settlements(c: sqlite3.Connection) -> list[dict]:
    """Find settlements not yet paid out by checking payout_log."""
    # Get all settlement ids already paid — prospect_id identifies them
    paid = set()
    try:
        for row in c.execute("SELECT DISTINCT settled_at FROM payout_log WHERE status='confirmed'"):
            paid.add(row[0])
    except Exception:
        pass

    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT * FROM si_settlements ORDER BY settled_at ASC"
    ).fetchall()

    pending = []
    for r in rows:
        d = dict(r)
        if d.get("settled_at") not in paid:
            pending.append(d)
    return pending


def _get_paid_ppc_total(c: sqlite3.Connection) -> int:
    """Get total cents from paid PPC invoices not yet swept."""
    paid_at_set = set()
    try:
        for row in c.execute("SELECT DISTINCT settled_at FROM payout_log"):
            if row[0]:
                paid_at_set.add(row[0])
    except Exception:
        pass

    total = 0
    rows = c.execute(
        "SELECT SUM(amount_cents) as total, paid_at FROM si_ppc_invoices "
        "WHERE status='paid' GROUP BY paid_at"
    ).fetchall()
    for r in rows:
        if r["paid_at"] and r["paid_at"] not in paid_at_set:
            total += r["total"] or 0
    return total


def _get_a2a_released_total(c: sqlite3.Connection) -> int:
    """Get total USDC from A2A escrow-releases not yet swept."""
    try:
        # Quote IDs already swept
        swept = set()
        for row in c.execute("SELECT DISTINCT meta FROM payout_log WHERE meta LIKE 'a2a:%'"):
            swept.add(row[0].replace("a2a:", ""))
        # Get released quotes
        total = 0
        for row in c.execute("SELECT quote_id, amount_usdc FROM a2a_quotes WHERE status='released'"):
            if row["quote_id"] not in swept:
                total += int(row["amount_usdc"] * 100)
        return total
    except Exception:
        return 0


def _get_lease_active_total(c: sqlite3.Connection) -> int:
    """Get total USDC from active lease payments not yet swept."""
    try:
        swept = set()
        for row in c.execute("SELECT DISTINCT meta FROM payout_log WHERE meta LIKE 'lease:%'"):
            swept.add(row[0].replace("lease:", ""))
        total = 0
        for row in c.execute("SELECT lease_id, price_usdc FROM lead_leases WHERE status='active'"):
            if row["lease_id"] not in swept:
                total += int(row["price_usdc"] * 100)
        return total
    except Exception:
        return 0


def _get_affiliate_pending_total(c: sqlite3.Connection) -> list:
    """Get per-ref pending affiliate payouts (each gets own tx)."""
    try:
        return c.execute("""
            SELECT l.ref_code, r.wallet, SUM(l.amount_cents) as total_cents, COUNT(l.id) as n
            FROM affiliate_ledger l
            JOIN affiliate_refs r ON l.ref_code = r.code
            WHERE l.status = 'pending'
            GROUP BY l.ref_code
            HAVING total_cents >= ?
        """, (500,)).fetchall()
    except Exception:
        return []


async def run_sweep(dry_run: bool = False) -> dict:
    """Main sweep logic. Returns summary dict."""
    result = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pending_settlements": 0,
        "pending_cents": 0,
        "ppc_paid_cents": 0,
        "a2a_released_cents": 0,
        "lease_active_cents": 0,
        "affiliate_pending": 0,
        "total_cents": 0,
        "swept": False,
        "tx_sig": None,
        "error": None,
    }

    c = sqlite3.connect(DB_PATH, timeout=15)
    _ensure_log_table(c)

    # 1. Pending settlements
    pending = _get_pending_settlements(c)
    settlement_cents = sum(p["amount_cents"] for p in pending)
    result["pending_settlements"] = len(pending)
    result["pending_cents"] = settlement_cents

    # 2. Paid PPC invoices
    ppc_cents = _get_paid_ppc_total(c)
    result["ppc_paid_cents"] = ppc_cents

    # 3. A2A released escrow (new)
    a2a_cents = _get_a2a_released_total(c)
    result["a2a_released_cents"] = a2a_cents

    # 4. Active leases (new)
    lease_cents = _get_lease_active_total(c)
    result["lease_active_cents"] = lease_cents

    # 5. Affiliate pending (informational only - each gets own sweep tx)
    aff_count = len(_get_affiliate_pending_total(c))
    result["affiliate_pending"] = aff_count

    total_cents = settlement_cents + ppc_cents + a2a_cents + lease_cents
    result["total_cents"] = total_cents

    logger.info(
        "Sweep check: settlements=$%.2f PPC=$%.2f A2A=$%.2f Lease=$%.2f Affiliates=%d = $%.2f total",
        settlement_cents / 100, ppc_cents / 100, a2a_cents / 100, lease_cents / 100,
        aff_count, total_cents / 100,
    )

    if total_cents < MIN_PAYOUT_CENTS:
        logger.info(
            "Total $%.2f below min $%.2f — no sweep needed",
            total_cents / 100, MIN_PAYOUT_CENTS / 100,
        )
        c.close()
        return result

    if not SOLANA_PAYER_SECRET or SOLANA_PAYER_SECRET.startswith("CPmGjF"):
        logger.warning("SOLANA_PAYER_SECRET appears to be test/dev — dry mode")
        result["error"] = "test_payer_secret_no_real_sweep"
        c.close()
        return result

    if not SOLANA_VAULT_WALLET:
        logger.error("SOLANA_VAULT_WALLET not set — can't sweep")
        result["error"] = "no_vault_wallet"
        c.close()
        return result

    if dry_run:
        logger.info("DRY RUN: would sweep $%.2f → %s", total_cents / 100, FOUNDER_WALLET)
        result["swept"] = True
        c.close()
        return result

    # 3. Execute the payout
    vault_ata = os.getenv("SOLANA_VAULT_ATA") or _derive_ata(SOLANA_VAULT_WALLET)
    founder_ata = os.getenv("FOUNDER_ATA") or _derive_ata(FOUNDER_WALLET)
    amount_usd = total_cents / 100

    try:
        from empire_os.payout import usdc_transfer

        sig = await usdc_transfer(
            payer_secret_b58=SOLANA_PAYER_SECRET,
            sender_ata=vault_ata,
            recipient_ata=founder_ata,
            amount_usd=amount_usd,
        )
        result["tx_sig"] = sig
        result["swept"] = True
        logger.info("SWEPT $%.2f → %s | sig %s", amount_usd, founder_ata, sig)

        # Mark settlements as paid
        for p in pending:
            c.execute(
                "INSERT INTO payout_log (settled_at, amount_cents, usdc_amount, "
                "from_wallet, to_wallet, tx_sig, status) VALUES (?,?,?,?,?,?,?)",
                (
                    p["settled_at"], p["amount_cents"], p["amount_cents"] / 100,
                    vault_ata, founder_ata, sig, "confirmed",
                ),
            )
        # Note: earlier settlement mark uses 7-column INSERT (no meta). That's fine,
        # meta is optional. New code below uses 8-column.

        # Mark PPC invoices batch
        c.execute(
            "INSERT INTO payout_log (settled_at, amount_cents, usdc_amount, "
            "from_wallet, to_wallet, tx_sig, status, meta) VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                ppc_cents, ppc_cents / 100,
                vault_ata, founder_ata, sig, "confirmed", "ppc:batch",
            ),
        )

        # Mark A2A released quotes (mark all unreleased)
        for row in c.execute("SELECT quote_id FROM a2a_quotes WHERE status='released'"):
            c.execute(
                "INSERT INTO payout_log (settled_at, amount_cents, usdc_amount, "
                "from_wallet, to_wallet, tx_sig, status, meta) VALUES (?,?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    a2a_cents, a2a_cents / 100,
                    vault_ata, founder_ata, sig, "confirmed", f"a2a:{row['quote_id']}",
                ),
            )

        # Mark active leases
        for row in c.execute("SELECT lease_id FROM lead_leases WHERE status='active'"):
            c.execute(
                "INSERT INTO payout_log (settled_at, amount_cents, usdc_amount, "
                "from_wallet, to_wallet, tx_sig, status, meta) VALUES (?,?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    lease_cents, lease_cents / 100,
                    vault_ata, founder_ata, sig, "confirmed", f"lease:{row['lease_id']}",
                ),
            )

        c.commit()

    except Exception as e:
        logger.error("Sweep failed: %s", e)
        result["error"] = str(e)
        # Log the failed attempt
        c.execute(
            "INSERT INTO payout_log (settled_at, amount_cents, usdc_amount, "
            "from_wallet, to_wallet, tx_sig, status) VALUES (?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(),
                total_cents, amount_usd,
                vault_ata, founder_ata, "failed", "failed",
            ),
        )
        c.commit()
    finally:
        c.close()

    return result


async def main():
    dry = "--dry-run" in sys.argv
    result = await run_sweep(dry_run=dry)
    print(json.dumps(result, indent=2, default=str))
    if result.get("error") and "test" not in str(result["error"]):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
