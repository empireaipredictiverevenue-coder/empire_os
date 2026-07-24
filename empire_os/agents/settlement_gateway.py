#!/usr/bin/env python3
"""
Empire OS v3 — Settlement Gateway

Handles USDC settlement for delivered leads.
- Receives lead_id from solana_listener (via memo matching)
- Marks si_funnel_event for that lead as 'settled'
- Writes si_settlements row for audit trail
- Idempotent on (tx_signature, lead_id)

Memo formats supported:
  LEAD_<lead_id>          — direct lead settlement
  INV_<invoice_id>        — invoice-based (falls back to lead via invoice)
  SEAT_<sub_id>           — subscription seat (not a lead settlement)
  EVAL_<buyer>__<lead_ref> — evaluation product settlement
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/root/empire_os")

# ── Config ──────────────────────────────────────────────────────────
DB = "/root/empire_os/empire_os.db"
LOG_DIR = Path("/root/empire_os/logs")
LOG_FILE = LOG_DIR / "settlement_gateway.jsonl"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(level: str, msg: str, **fields):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry), flush=True)


# ── Core settlement logic ──────────────────────────────────────────

def settle_lead_by_id(lead_id: str, tx_signature: str, amount_usdc: float, memo: str = "") -> dict:
    """
    Settle a delivered lead by its lead_id.

    Args:
        lead_id: The lead identifier from lane_leads or crm_leads
        tx_signature: Solana transaction signature
        amount_usdc: USDC amount received
        memo: Original memo from the transaction

    Returns:
        dict with settlement status and details
    """
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")

    try:
        with conn:
            # 1. Check if already settled for this tx_signature + lead_id
            existing = conn.execute(
                """SELECT id FROM si_settlements
                   WHERE notes LIKE ? AND prospect_id = ?""",
                (f"%{tx_signature[:20]}%", lead_id),
            ).fetchone()
            if existing:
                return {
                    "ok": True,
                    "duplicate": True,
                    "settlement_id": existing["id"],
                    "lead_id": lead_id,
                    "message": "already settled",
                }

            # 2. Find the prospect_id / lead_id in si_funnel_event
            # lead_id could be lane_leads.id, crm_leads.id, or lane_leads.prospect_id
            prospect_row = conn.execute(
                """SELECT DISTINCT prospect_id FROM si_funnel_event
                   WHERE prospect_id = ? OR prospect_id LIKE ? OR prospect_id LIKE ?""",
                (lead_id, f"%{lead_id}%", f"lead_{lead_id}%"),
            ).fetchone()

            if not prospect_row:
                # Try crm_leads table for the lead_uid
                crm_row = conn.execute(
                    "SELECT id, lead_uid FROM crm_leads WHERE id = ? OR lead_uid = ?",
                    (lead_id, lead_id),
                ).fetchone()
                if crm_row:
                    prospect_id = crm_row["lead_uid"] or str(crm_row["id"])
                else:
                    # Try lane_leads
                    lane_row = conn.execute(
                        "SELECT id, prospect_id FROM lane_leads WHERE id = ? OR prospect_id = ?",
                        (lead_id, lead_id),
                    ).fetchone()
                    if lane_row:
                        prospect_id = lane_row["prospect_id"]
                    else:
                        return {
                            "ok": False,
                            "error": f"no prospect found for lead_id={lead_id}",
                            "lead_id": lead_id,
                        }
            else:
                prospect_id = prospect_row["prospect_id"]

            # 3. Check current funnel state
            current_state = conn.execute(
                """SELECT to_state FROM si_funnel_event
                   WHERE prospect_id = ? ORDER BY id DESC LIMIT 1""",
                (prospect_id,),
            ).fetchone()

            if current_state and current_state["to_state"] == "settled":
                return {
                    "ok": True,
                    "duplicate": True,
                    "lead_id": lead_id,
                    "prospect_id": prospect_id,
                    "message": "already in settled state",
                }

            # 4. Write si_funnel_event transition to 'settled'
            occurred_at = datetime.now(timezone.utc).isoformat()
            cursor = conn.execute(
                """INSERT INTO si_funnel_event
                   (prospect_id, from_state, to_state, actor, notes, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    prospect_id,
                    current_state["to_state"] if current_state else "claimed",
                    "settled",
                    "solana_listener",
                    json.dumps({
                        "lead_id": lead_id,
                        "amount_usdc": amount_usdc,
                        "tx_signature": tx_signature,
                        "memo": memo,
                        "settled_at": occurred_at,
                    }),
                    occurred_at,
                ),
            )
            funnel_event_id = cursor.lastrowid

            # 5. Write si_settlements row for audit/revenue tracking
            amount_cents = int(round(amount_usdc * 100))
            cursor = conn.execute(
                """INSERT INTO si_settlements
                   (prospect_id, tenant_id, amount_cents, settled_at, settled_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    prospect_id,
                    "",  # tenant_id unknown at this stage; could be looked up
                    amount_cents,
                    occurred_at,
                    "solana_listener",
                    f"USDC settlement for lead {lead_id} via tx {tx_signature[:20]}",
                ),
            )
            settlement_id = cursor.lastrowid

            log(
                "INFO",
                "lead_settled",
                lead_id=lead_id,
                prospect_id=prospect_id,
                amount_usdc=amount_usdc,
                tx_signature=tx_signature,
                settlement_id=settlement_id,
                funnel_event_id=funnel_event_id,
            )

            return {
                "ok": True,
                "settlement_id": settlement_id,
                "funnel_event_id": funnel_event_id,
                "lead_id": lead_id,
                "prospect_id": prospect_id,
                "amount_usdc": amount_usdc,
                "tx_signature": tx_signature,
            }

    except Exception as e:
        log("ERROR", "settle_lead_failed", lead_id=lead_id, error=str(e)[:200])
        return {"ok": False, "error": str(e)[:200], "lead_id": lead_id}
    finally:
        conn.close()


def settle_lead_by_invoice(invoice_id: str, tx_signature: str, amount_usdc: float, memo: str = "") -> dict:
    """
    Settle a lead by finding the lead_id from an si_ppc_invoices row.
    """
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row

    try:
        inv = conn.execute(
            "SELECT invoice_id, lead_id, buyer_id, amount_usdc FROM si_ppc_invoices WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()

        if not inv:
            return {"ok": False, "error": f"invoice not found: {invoice_id}", "invoice_id": invoice_id}

        # Verify amount matches (within tolerance)
        if abs(float(inv["amount_usdc"]) - amount_usdc) > 0.01:
            log(
                "WARN",
                "settlement_amount_mismatch",
                invoice_id=invoice_id,
                expected=inv["amount_usdc"],
                received=amount_usdc,
            )

        lead_id = inv["lead_id"]
        if not lead_id:
            return {"ok": False, "error": f"invoice {invoice_id} has no lead_id", "invoice_id": invoice_id}

        # Delegate to settle_lead_by_id
        result = settle_lead_by_id(lead_id, tx_signature, amount_usdc, memo)
        result["invoice_id"] = invoice_id
        return result

    except Exception as e:
        log("ERROR", "settle_by_invoice_failed", invoice_id=invoice_id, error=str(e)[:200])
        return {"ok": False, "error": str(e)[:200], "invoice_id": invoice_id}
    finally:
        conn.close()


def extract_lead_id_from_memo(memo: str) -> Optional[str]:
    """
    Parse lead_id from transaction memo.

    Supported formats:
      LEAD_<lead_id>           -> direct lead settlement
      INV_<invoice_id>         -> invoice-based settlement
      SEAT_<sub_id>            -> subscription (not a lead)
      EVAL_<buyer>__<lead_ref>  -> evaluation product
      SKU_<sku>                -> product subscription
    """
    if not memo:
        return None

    memo = memo.strip()

    if memo.startswith("LEAD_"):
        return memo[len("LEAD_"):].strip()
    if memo.startswith("INV_"):
        return None  # handled by invoice path
    if memo.startswith("SEAT_") or memo.startswith("EVAL_") or memo.startswith("SKU_"):
        return None  # not a lead settlement

    return None


def process_settlement(memo: str, tx_signature: str, amount_usdc: float) -> dict:
    """
    Main entry point: route settlement based on memo format.

    Returns dict with settlement result.
    """
    if not memo:
        log("WARN", "settlement_no_memo", tx_signature=tx_signature, amount_usdc=amount_usdc)
        return {"ok": False, "error": "empty memo", "tx_signature": tx_signature}

    # 1. Direct lead memo: LEAD_<lead_id>
    if memo.startswith("LEAD_"):
        lead_id = memo[len("LEAD_"):].strip()
        log("INFO", "settlement_lead_memo", lead_id=lead_id, tx_signature=tx_signature, amount_usdc=amount_usdc)
        return settle_lead_by_id(lead_id, tx_signature, amount_usdc, memo)

    # 2. Invoice memo: INV_<invoice_id>
    if memo.startswith("INV_"):
        invoice_id = memo[len("INV_"):].strip()
        log("INFO", "settlement_invoice_memo", invoice_id=invoice_id, tx_signature=tx_signature, amount_usdc=amount_usdc)
        return settle_lead_by_invoice(invoice_id, tx_signature, amount_usdc, memo)

    # 3. Other memo types (SEAT_, EVAL_, SKU_) - not lead settlements
    if memo.startswith(("SEAT_", "EVAL_", "SKU_", "LANE_", "EVALBUY_")):
        log("INFO", "settlement_non_lead_memo", memo_prefix=memo.split("_")[0], tx_signature=tx_signature)
        return {"ok": True, "lead_settlement": False, "memo_type": memo.split("_")[0], "message": "not a lead settlement"}

    # 4. No recognizable memo - could be a blind payment, log for reconciliation
    log("WARN", "settlement_unrecognized_memo", memo=memo[:50], tx_signature=tx_signature, amount_usdc=amount_usdc)
    return {"ok": False, "error": "unrecognized memo format", "memo": memo[:50]}


def get_settlement_status(lead_id: str) -> dict:
    """Check if a lead has been settled."""
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row

    try:
        # Check funnel state
        funnel = conn.execute(
            """SELECT to_state, occurred_at FROM si_funnel_event
               WHERE prospect_id = ? OR prospect_id LIKE ?
               ORDER BY id DESC LIMIT 1""",
            (lead_id, f"%{lead_id}%"),
        ).fetchone()

        # Check settlements table
        settlement = conn.execute(
            """SELECT * FROM si_settlements
               WHERE prospect_id = ? OR prospect_id LIKE ?
               ORDER BY id DESC LIMIT 1""",
            (lead_id, f"%{lead_id}%"),
        ).fetchone()

        return {
            "lead_id": lead_id,
            "funnel_state": funnel["to_state"] if funnel else None,
            "funnel_at": funnel["occurred_at"] if funnel else None,
            "settled": bool(settlement),
            "settlement_id": settlement["id"] if settlement else None,
            "settled_at": settlement["settled_at"] if settlement else None,
            "amount_cents": settlement["amount_cents"] if settlement else None,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Settlement Gateway CLI")
    parser.add_argument("--memo", required=True, help="Transaction memo")
    parser.add_argument("--tx", required=True, help="Transaction signature")
    parser.add_argument("--amount", type=float, required=True, help="USDC amount")
    parser.add_argument("--check", help="Check settlement status for lead_id")
    args = parser.parse_args()

    if args.check:
        print(json.dumps(get_settlement_status(args.check), indent=2))
    else:
        result = process_settlement(args.memo, args.tx, args.amount)
        print(json.dumps(result, indent=2))