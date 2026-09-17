"""Governed BSC payment workflow adapters.

No public route imports this module. Proposal/cancellation writes require explicit
operator authorization. Approval and evidence recording require dedicated role
transports and never fall back to the Supabase service_role client.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from uuid import UUID

from empire_os.bsc_usdt_verifier import (
    BscUsdtConfig, PaymentVerificationError, _address, get_block_anchor,
)

CANONICAL_URL = "https://owbeinlfcfdtwcwrttjy.supabase.co"
MIN_EXPIRY = timedelta(minutes=10)
MAX_EXPIRY = timedelta(days=7)


class PaymentGovernanceError(RuntimeError):
    pass


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PaymentGovernanceError(f"invalid {field}") from exc


def _actor(value: Any, field: str = "actor") -> str:
    text = str(value or "").strip()
    if not 1 <= len(text) <= 200:
        raise PaymentGovernanceError(f"invalid {field}")
    return text

def _amount(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PaymentGovernanceError("invalid amount_usdt") from exc
    if not amount.is_finite() or amount <= 0:
        raise PaymentGovernanceError("invalid amount_usdt")
    exponent = amount.as_tuple().exponent
    if exponent < -18:
        raise PaymentGovernanceError("amount_usdt exceeds 18 decimal places")
    return format(amount, "f")


def _expires(value: datetime, *, now: datetime | None = None) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PaymentGovernanceError("timezone-aware expires_at required")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise PaymentGovernanceError("timezone-aware current time required")
    delta = value.astimezone(timezone.utc) - current.astimezone(timezone.utc)
    if delta < MIN_EXPIRY or delta > MAX_EXPIRY:
        raise PaymentGovernanceError("expires_at must be 10 minutes to 7 days in the future")
    return value.astimezone(timezone.utc).isoformat()


def _key(value: Any) -> str:
    text = str(value or "").strip()
    if not 8 <= len(text) <= 128:
        raise PaymentGovernanceError("invalid idempotency_key")
    return text


def _positive_block(value: Any) -> int:
    if type(value) is not int or value <= 0:
        raise PaymentGovernanceError("positive min_block_number required")
    return value

def build_payment_proposal(*, fulfilment_order_id: Any, amount_usdt: Any,
                           payer_address: Any, treasury_address: Any,
                           min_block_number: Any, expires_at: datetime,
                           idempotency_key: Any, actor: Any,
                           now: datetime | None = None) -> dict[str, Any]:
    try:
        payer = _address(payer_address)
        treasury = _address(treasury_address)
    except PaymentVerificationError as exc:
        raise PaymentGovernanceError("invalid BSC payer or treasury address") from exc
    if payer == treasury:
        raise PaymentGovernanceError("payer and treasury must differ")
    params = {
        "p_fulfilment_order_id": _uuid(fulfilment_order_id, "fulfilment_order_id"),
        "p_amount_usdt": _amount(amount_usdt),
        "p_payer_address": payer,
        "p_treasury_address": treasury,
        "p_min_block_number": _positive_block(min_block_number),
        "p_expires_at": _expires(expires_at, now=now),
        "p_idempotency_key": _key(idempotency_key),
        "p_actor": _actor(actor),
    }
    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "actual_revenue": False,
        "rpc": "propose_bsc_payment_request",
        "params": params,
    }


def _canonical_service_db(db: Any | None) -> Any:
    if db is not None:
        return db
    from empire_os import sb
    if sb.SUPABASE_URL.rstrip("/") != CANONICAL_URL or not sb.SUPABASE_KEY:
        raise PaymentGovernanceError("canonical Supabase service configuration required")
    return sb

def _expect_result(value: Any, decisions: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("decision") not in decisions:
        raise PaymentGovernanceError("unexpected payment governance response")
    if value.get("actual_revenue") is not False:
        raise PaymentGovernanceError("governance response attempted revenue recognition")
    return value


def submit_payment_proposal(plan: dict[str, Any], *, operator_authorized: bool = False,
                            db: Any | None = None) -> dict[str, Any]:
    if not operator_authorized:
        raise PaymentGovernanceError("explicit operator authorization required")
    if not isinstance(plan, dict) or plan.get("rpc") != "propose_bsc_payment_request":
        raise PaymentGovernanceError("invalid payment proposal plan")
    if plan.get("write_authorized") is not False or plan.get("actual_revenue") is not False:
        raise PaymentGovernanceError("unsafe payment proposal plan")
    result = _canonical_service_db(db).rpc(plan["rpc"], plan.get("params") or {})
    return _expect_result(result, {"proposed", "existing_request"})


def cancel_payment_request(request_id: Any, *, actor: Any, reason: Any,
                           operator_authorized: bool = False,
                           db: Any | None = None, cancel_rpc=None) -> dict[str, Any]:
    if not operator_authorized:
        raise PaymentGovernanceError("explicit operator authorization required")
    reason_text = str(reason or "").strip()
    if not 4 <= len(reason_text) <= 1000:
        raise PaymentGovernanceError("invalid cancellation reason")
    params = {
        "p_request_id": _uuid(request_id, "request_id"),
        "p_actor": _actor(actor),
        "p_reason": reason_text,
    }
    if cancel_rpc is not None and db is not None:
        raise PaymentGovernanceError("choose dedicated cancel transport or service database, not both")
    if cancel_rpc is not None:
        result = _role_rpc(cancel_rpc, "cancellation")("cancel_bsc_payment_request", params)
    else:
        result = _canonical_service_db(db).rpc("cancel_bsc_payment_request", params)
    return _expect_result(result, {"cancelled", "existing_cancellation", "already_expired"})


def validate_review_block_anchor(review: dict[str, Any], *, config=None, rpc_call=None,
                                 tolerance_seconds: int = 120) -> dict[str, Any]:
    if not isinstance(review, dict) or review.get("actual_revenue") is not False:
        raise PaymentGovernanceError("valid payment review required")
    if type(tolerance_seconds) is not int or tolerance_seconds < 1 or tolerance_seconds > 600:
        raise PaymentGovernanceError("invalid block anchor tolerance")
    try:
        block_number = int(review["min_block_number"])
        if block_number < 1:
            raise ValueError("block")
        created = datetime.fromisoformat(str(review["created_at"]).replace("Z", "+00:00"))
        if created.tzinfo is None:
            raise ValueError("timezone")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PaymentGovernanceError("invalid request block anchor metadata") from exc
    cfg = config or BscUsdtConfig.from_env()
    try:
        if _address(review.get("treasury_address")) != _address(cfg.treasury_address):
            raise PaymentGovernanceError("request treasury does not match configured treasury")
        anchor = get_block_anchor(cfg, block_number=block_number, rpc_call=rpc_call)
    except PaymentVerificationError as exc:
        raise PaymentGovernanceError("BSC block anchor verification failed") from exc
    delta = abs(created.astimezone(timezone.utc).timestamp() - anchor["timestamp"])
    if delta > tolerance_seconds:
        raise PaymentGovernanceError("request min block is not anchored to request creation time")
    return {
        "verified": True, "chain_id": anchor["chain_id"],
        "block_number": anchor["block_number"], "block_hash": anchor["block_hash"],
        "block_timestamp": anchor["timestamp"], "created_at": created.isoformat(),
        "delta_seconds": delta, "actual_revenue": False,
    }

def _role_rpc(transport: Callable[[str, dict[str, Any]], Any] | None,
              label: str) -> Callable[[str, dict[str, Any]], Any]:
    if transport is None or not callable(transport):
        raise PaymentGovernanceError(f"dedicated {label} transport required")
    return transport


def review_payment_request(request_id: Any, *, role_rpc=None) -> dict[str, Any]:
    rpc = _role_rpc(role_rpc, "approver/verifier")
    result = rpc("get_bsc_payment_request_review", {
        "p_request_id": _uuid(request_id, "request_id"),
    })
    if not isinstance(result, dict) or result.get("actual_revenue") is not False:
        raise PaymentGovernanceError("unexpected payment review response")
    return result


def approve_payment_request(request_id: Any, *, approved_by: Any,
                            approval_note: Any, operator_authorized: bool = False,
                            approver_rpc=None) -> dict[str, Any]:
    if not operator_authorized:
        raise PaymentGovernanceError("explicit operator authorization required")
    note = str(approval_note or "").strip()
    if not 4 <= len(note) <= 1000:
        raise PaymentGovernanceError("invalid approval_note")
    rpc = _role_rpc(approver_rpc, "approver")
    result = rpc("approve_bsc_payment_request", {
        "p_request_id": _uuid(request_id, "request_id"),
        "p_approved_by": _actor(approved_by, "approved_by"),
        "p_approval_note": note,
    })
    return _expect_result(result, {"approved", "existing_approval", "expired"})


def record_payment_preview(preview: dict[str, Any], *, verifier_authorized: bool = False,
                           verifier_rpc=None) -> dict[str, Any]:
    if not verifier_authorized:
        raise PaymentGovernanceError("explicit verifier authorization required")
    if not isinstance(preview, dict) or preview.get("mode") != "OBSERVE":
        raise PaymentGovernanceError("verified OBSERVE preview required")
    if preview.get("recorded") is not False or preview.get("actual_revenue") is not False:
        raise PaymentGovernanceError("unsafe payment preview")
    evidence = preview.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("verified") is not True:
        raise PaymentGovernanceError("verified chain evidence required")
    if evidence.get("token_decimals") != 18:
        raise PaymentGovernanceError("canonical BSC USDT precision required")
    rpc = _role_rpc(verifier_rpc, "verifier")
    result = rpc("record_bsc_payment_evidence", {
        "p_request_id": _uuid(preview.get("request_id"), "request_id"),
        "p_evidence": evidence,
    })
    return _expect_result(result, {"recorded", "already_recorded"})