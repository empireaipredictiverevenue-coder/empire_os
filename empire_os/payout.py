#!/usr/bin/env python3
"""payout — BSC USDT payout engine for Empire OS.

BSC USDT (BEP20) does NOT require gas for receiving — only for sending.
Payouts are handled by the settlement_gateway_daemon + bsc_listener
(balance reconciliation). This module provides the PayoutEngine class
that hub.py imports, with no-op safe methods until full BSC web3
signing is wired.

Functions:
  PayoutEngine — class imported by hub.py for payout batch management
"""
from __future__ import annotations
import os, sqlite3, logging, json
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("empire_payout")

BSC_WALLET = os.getenv("BSC_WALLET_ADDRESS",
    "0x1339b487046B0ad924a10c20b1791608EA8595a8")
BSC_USDT_CONTRACT = os.getenv("BSC_USDT_CONTRACT",
    "0x55d398326f99059fF775485246999027B3197955")
BSC_RPC = os.getenv("BSC_RPC", "https://bsc-dataseed.binance.org")
USDT_DECIMALS = 18


class PayoutEngine:
    """BSC USDT payout engine — manages payout batches in the DB.

    On-chain sending is handled by settlement_gateway_daemon which
    reconciles balances via the bsc_listener. This class handles the
    DB-side batch management.
    """

    def __init__(self, db_path: str = "/root/empire_os/empire_os.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")

    def list_pending(self, limit: int = 50) -> list:
        """List pending payouts."""
        rows = self.conn.execute(
            "SELECT * FROM si_payouts WHERE status='pending' "
            "ORDER BY created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_paid(self, payout_id: int, tx_hash: str) -> bool:
        """Mark a payout as paid with BSC tx hash."""
        self.conn.execute(
            "UPDATE si_payouts SET status='paid', tx_hash=?, "
            "paid_at=datetime('now') WHERE id=?",
            (tx_hash, payout_id)
        )
        self.conn.commit()
        return True

    def create_batch(self, payouts: list) -> int:
        """Create a batch of pending payouts."""
        count = 0
        for p in payouts:
            self.conn.execute(
                "INSERT OR IGNORE INTO si_payouts "
                "(buyer_id, amount_usdt, wallet, status, created_at) "
                "VALUES (?, ?, ?, 'pending', datetime('now'))",
                (p.get("buyer_id"), p.get("amount"), p.get("wallet"))
            )
            count += 1
        self.conn.commit()
        return count

    def close(self):
        self.conn.close()


def pay_invoice(invoice_id: str) -> dict:
    """Pay an invoice via BSC USDT.

    With BSC, receiving USDT requires no gas. The bsc_listener monitors
    wallet balance and reconciles. This function marks the invoice as
    pending reconciliation.
    """
    conn = sqlite3.connect(
        os.getenv("DB_PATH", "/root/empire_os/empire_os.db"),
        timeout=30
    )
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM si_ppc_invoices WHERE invoice_id=?",
            (invoice_id,)
        ).fetchone()
        if not row:
            return {"error": "invoice_not_found"}

        conn.execute(
            "UPDATE si_ppc_invoices SET status='pending_reconciliation' "
            "WHERE invoice_id=?",
            (invoice_id,)
        )
        conn.commit()
        return {
            "invoice_id": invoice_id,
            "status": "pending_reconciliation",
            "wallet": BSC_WALLET,
            "token": "USDT",
            "network": "BSC",
            "note": f"Send USDT to {BSC_WALLET} on BSC. "
                    f"bsc_listener will reconcile automatically.",
        }
    finally:
        conn.close()
