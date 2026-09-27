"""OBSERVE-only payment evidence preview. No writes, activation, or revenue recognition.

The service-role database is trusted for approved commercial terms; public callers
supply only a request UUID and transaction hash. Replay checks here are advisory:
the database UNIQUE constraints are the eventual race-safe reservation boundary.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from empire_os.bsc_usdt_verifier import (
    BscUsdtConfig, PaymentVerificationError, verify_payment, _address, _tx_hash,
)

CANONICAL_URL = "https://owbeinlfcfdtwcwrttjy.supabase.co"


def _uuid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PaymentVerificationError("invalid commercial identity") from exc


def _one(db, table, identity):
    columns = (
        "id,buyer_id,fulfilment_order_id,status,approved_by,approved_at,expires_at,"
        "commercial_terms_sha256,amount_usdt::text,min_block_number,payer_address,treasury_address"
    ) if table == "bsc_payment_requests" else "*"
    rows = db.select(table, columns=columns, filters={"id": identity}, limit=2)
    if not isinstance(rows, list) or len(rows) != 1:
        raise PaymentVerificationError(f"missing or ambiguous {table}")
    return rows[0]


def preview_payment(request_id, transaction_hash, *, db=None, config=None,
                    rpc_call=None, now=None):
    """Return unrecorded evidence only; injected dependencies are for offline tests."""
    if db is None:
        from empire_os import sb
        if sb.SUPABASE_URL.rstrip("/") != CANONICAL_URL or not sb.SUPABASE_KEY:
            raise PaymentVerificationError("canonical Supabase configuration required")
        db = sb
    request_id = _uuid(request_id)
    transaction_hash = _tx_hash(transaction_hash)
    request = _one(db, "bsc_payment_requests", request_id)
    buyer_id = _uuid(request.get("buyer_id"))
    order_id = _uuid(request.get("fulfilment_order_id"))
    if request.get("status") != "approved":
        raise PaymentVerificationError("approved payment request required")
    if not request.get("approved_by") or not request.get("approved_at"):
        raise PaymentVerificationError("human approval evidence required")
    terms = request.get("commercial_terms_sha256")
    if not isinstance(terms, str) or len(terms) != 64 or any(
            c not in "0123456789abcdef" for c in terms):
        raise PaymentVerificationError("commercial terms fingerprint required")
    try:
        expiry = datetime.fromisoformat(request["expires_at"].replace("Z", "+00:00"))
        approved = datetime.fromisoformat(request["approved_at"].replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        if expiry.tzinfo is None or approved.tzinfo is None or current.tzinfo is None:
            raise ValueError("timezone required")
        if not approved <= current < expiry:
            raise ValueError("expired or future approval")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PaymentVerificationError("invalid payment request window") from exc
    buyer = _one(db, "buyers", buyer_id)
    order = _one(db, "fulfilment_orders", order_id)
    if _uuid(buyer.get("id")) != buyer_id or _uuid(order.get("buyer_id")) != buyer_id:
        raise PaymentVerificationError("buyer/order mismatch")
    if order.get("state") not in {"accepted", "invoiced", "delivered", "confirmed"}:
        raise PaymentVerificationError("order is not eligible for payment")
    if order.get("commercial_payload", {}).get("commercial_terms_sha256") != terms:
        raise PaymentVerificationError("order commercial terms mismatch")
    try:
        if not isinstance(request["amount_usdt"], str):
            raise ValueError("amount must be lossless text")
        amount = Decimal(request["amount_usdt"])
        floor = request["min_block_number"]
        if not amount.is_finite() or amount <= 0:
            raise ValueError("amount")
        if type(floor) is not int or floor < 1:
            raise ValueError("block floor")
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise PaymentVerificationError("invalid approved amount or block floor") from exc
    cfg = config or BscUsdtConfig.from_env()
    if type(cfg.min_confirmations) is not int or cfg.min_confirmations < 12:
        raise PaymentVerificationError("payment evidence requires at least 12 confirmations")
    if _address(request.get("treasury_address")) != _address(cfg.treasury_address):
        raise PaymentVerificationError("request treasury mismatch")
    payer = _address(request.get("payer_address"))
    for filters in ({"transaction_hash": transaction_hash}, {"request_id": request_id}):
        rows = db.select("bsc_payment_evidence", filters=filters, limit=1)
        if not isinstance(rows, list):
            raise PaymentVerificationError("replay lookup failed")
        if rows:
            raise PaymentVerificationError("payment or request already recorded")
    proof = verify_payment(cfg, transaction_hash, amount,
                           expected_payer=payer, rpc_call=rpc_call)
    if proof.token_decimals != 18 or proof.block_number < floor:
        raise PaymentVerificationError("wrong token precision or payment predates request")
    evidence = proof.to_dict()
    evidence["amount_raw"] = str(proof.amount_raw)  # preserve uint256 through JSON
    evidence["commercial_terms_sha256"] = terms
    evidence["verified_at"] = datetime.now(timezone.utc).isoformat()
    return {
        "mode": "OBSERVE", "recorded": False, "actual_revenue": False,
        "request_id": request_id, "buyer_id": buyer_id,
        "fulfilment_order_id": order_id, "commercial_terms_sha256": terms,
        "evidence": evidence,
        "next_gate": "dedicated_verifier_atomic_recording",
    }
