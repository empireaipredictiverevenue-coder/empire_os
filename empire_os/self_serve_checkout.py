"""Self-serve checkout for verified fixed-price Empire products.

The checkout path is intentionally narrow:
- only an allowlist of verified USD one-time catalog products;
- buyer explicitly accepts the catalog terms;
- a canonical fulfilment order is created idempotently;
- payment-request creation remains behind an explicit runtime standing-authority
  switch and the existing BSC governance adapter;
- no payment, fulfilment or revenue is inferred from checkout creation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from empire_os.bsc_usdt_verifier import BscUsdtConfig, get_block_anchor
from empire_os.bsc_escrow_verifier import BscEscrowConfig
from empire_os.payment_governance import (
    build_payment_proposal,
    build_escrow_proposal,
    submit_payment_proposal,
)
from empire_os.sb import request_json


Request = Callable[..., Any]

SELF_SERVE_PRODUCT_CODES = frozenset({
    "competitor_search_gap",
    "search_opportunity_map",
    "technical_search_audit",
    "solar_opportunity_map_us",
})
MAX_SELF_SERVE_USD_CENTS = 29900
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class CheckoutError(RuntimeError):
    pass


def _clean_text(value: Any, *, label: str, max_length: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > max_length:
        raise CheckoutError(f"invalid {label}")
    return text


def _email(value: Any) -> str:
    text = _clean_text(value, label="email", max_length=320).lower()
    if not EMAIL_RE.fullmatch(text):
        raise CheckoutError("invalid email")
    return text


def _domain(value: Any) -> str:
    text = _clean_text(value, label="domain", max_length=253).lower()
    text = text.removeprefix("https://").removeprefix("http://")
    text = text.split("/", 1)[0].split(":", 1)[0].strip(".")
    if not DOMAIN_RE.fullmatch(text):
        raise CheckoutError("invalid domain")
    return text


def _wallet(value: Any) -> str:
    text = _clean_text(value, label="payer_wallet", max_length=42).lower()
    if not EVM_RE.fullmatch(text):
        raise CheckoutError("invalid BSC payer wallet")
    return text


def _catalog_row(request: Request, product_code: str) -> dict[str, Any]:
    rows = request(
        "POST",
        "/rest/v1/rpc/get_commercial_product_catalog",
        payload={"p_product_code": product_code, "p_limit": 1},
    ) or []
    if isinstance(rows, Mapping):
        rows = [rows]
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise CheckoutError("catalog product unavailable")
    row = dict(rows[0])
    if product_code not in SELF_SERVE_PRODUCT_CODES:
        raise CheckoutError("product not enabled for self-serve")
    if row.get("active") is not True:
        raise CheckoutError("product inactive")
    if str(row.get("catalog_state") or "").upper() != "VERIFIED":
        raise CheckoutError("product catalog not verified")
    if str(row.get("version_state") or "").upper() != "VERIFIED":
        raise CheckoutError("product version not verified")
    if row.get("binding_terms_ready") is not True:
        raise CheckoutError("product terms not binding-ready")
    if str(row.get("billing_model") or "") != "one_time":
        raise CheckoutError("self-serve v1 supports one-time products only")

    price = row.get("price_basis")
    if not isinstance(price, Mapping):
        raise CheckoutError("verified price missing")
    if str(price.get("state") or "").upper() != "VERIFIED":
        raise CheckoutError("verified price missing")
    if str(price.get("currency") or row.get("currency") or "").upper() != "USD":
        raise CheckoutError("self-serve v1 supports USD catalog products only")
    try:
        amount_cents = int(price.get("amount_cents"))
    except (TypeError, ValueError) as exc:
        raise CheckoutError("invalid catalog price") from exc
    if amount_cents < 1 or amount_cents > MAX_SELF_SERVE_USD_CENTS:
        raise CheckoutError("product outside self-serve value limit")
    row["_amount_cents"] = amount_cents
    return row


def public_product(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "product_code": row.get("product_code"),
        "product_name": row.get("product_name"),
        "billing_model": row.get("billing_model"),
        "currency": "USD",
        "amount_cents": row.get("_amount_cents"),
        "amount_display": f"${int(row.get('_amount_cents') or 0) / 100:,.0f}",
        "version": row.get("version"),
        "binding_terms_ready": True,
    }


def self_serve_catalog(request: Request = request_json) -> dict[str, Any]:
    products: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for code in sorted(SELF_SERVE_PRODUCT_CODES):
        try:
            products.append(public_product(_catalog_row(request, code)))
        except Exception:
            unavailable.append(code)
    return {
        "schema_version": "empire.self-serve-catalog.v1",
        "products": products,
        "count": len(products),
        "unavailable": unavailable,
        "settlement": {
            "asset": "USDT",
            "network": "BSC",
            "chain_id": 56,
        },
        "actual_revenue": False,
    }


def _basis_amount(row: Mapping[str, Any], key: str) -> int:
    basis = row.get(key)
    if not isinstance(basis, Mapping):
        raise CheckoutError(f"{key} missing")
    if str(basis.get("state") or "").upper() != "VERIFIED":
        raise CheckoutError(f"{key} unverified")
    try:
        amount = int(basis.get("amount_cents"))
    except (TypeError, ValueError) as exc:
        raise CheckoutError(f"{key} invalid") from exc
    if amount < 0:
        raise CheckoutError(f"{key} invalid")
    return amount


def _minimum_margin_bps(row: Mapping[str, Any]) -> int:
    policy = row.get("margin_policy")
    if not isinstance(policy, Mapping):
        raise CheckoutError("margin policy missing")
    if str(policy.get("state") or "").upper() != "VERIFIED":
        raise CheckoutError("margin policy unverified")
    try:
        value = int(policy.get("minimum_margin_bps"))
    except (TypeError, ValueError) as exc:
        raise CheckoutError("margin policy invalid") from exc
    if value < 0 or value > 10000:
        raise CheckoutError("margin policy invalid")
    return value


def _terms_payload(
    *,
    row: Mapping[str, Any],
    buyer_email: str,
    business_name: str,
    target_domain: str,
    payer_wallet: str,
    settlement_mode: str = "direct",
) -> dict[str, Any]:
    if settlement_mode not in {"direct", "escrow"}:
        raise CheckoutError("unsupported settlement mode")
    return {
        "schema_version": "empire.self-serve-terms.v1",
        "product_code": row.get("product_code"),
        "product_version": row.get("version"),
        "product_name": row.get("product_name"),
        "billing_model": "one_time",
        "currency": "USD",
        "amount_cents": int(row["_amount_cents"]),
        "quantity": 1,
        "buyer_email": buyer_email,
        "business_name": business_name,
        "target_domain": target_domain,
        "payer_wallet": payer_wallet,
        "settlement_asset": "USDT",
        "settlement_network": "BSC",
        "settlement_mode": settlement_mode,
        "chain_id": 56,
    }


def _terms_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _buyer_id(email: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"empire:self-serve:buyer:{email}"))


def _order_id(idempotency_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"empire:self-serve:order:{idempotency_key}"))


def _find_or_create_buyer(
    request: Request,
    *,
    business_name: str,
    email: str,
) -> str:
    rows = request(
        "GET",
        "/rest/v1/buyers"
        f"?select=id,email,buyer_name&email=eq.{quote(email, safe='')}&limit=1",
    ) or []
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        return str(rows[0]["id"])

    buyer_id = _buyer_id(email)
    payload = {
        "id": buyer_id,
        "buyer_name": business_name,
        "niche": "self_serve_catalog",
        "email": email,
        "status": "PENDING_PAYMENT",
        "is_active": False,
        "commercial_activation_state": "prospective",
        "commercial_terms_source": "self_serve_catalog",
    }
    try:
        created = request(
            "POST",
            "/rest/v1/buyers",
            payload=payload,
            prefer="return=representation",
        ) or []
    except RuntimeError:
        existing = request(
            "GET",
            f"/rest/v1/buyers?select=id&id=eq.{buyer_id}&limit=1",
        ) or []
        if isinstance(existing, list) and existing:
            return str(existing[0]["id"])
        raise
    if isinstance(created, list) and created:
        return str(created[0]["id"])
    return buyer_id


def _find_existing_order(request: Request, order_id: str) -> dict[str, Any] | None:
    rows = request(
        "GET",
        "/rest/v1/fulfilment_orders"
        f"?select=id,product_id,buyer_id,state,price_cents,commercial_payload"
        f"&id=eq.{order_id}&limit=1",
    ) or []
    if isinstance(rows, list) and rows and isinstance(rows[0], Mapping):
        return dict(rows[0])
    return None


def prepare_checkout_order(
    *,
    product_code: str,
    business_name: str,
    email: str,
    target_domain: str,
    payer_wallet: str,
    terms_accepted: bool,
    idempotency_key: str,
    settlement_mode: str = "direct",
    request: Request = request_json,
    now: datetime | None = None,
) -> dict[str, Any]:
    if terms_accepted is not True:
        raise CheckoutError("terms acceptance required")
    if settlement_mode not in {"direct", "escrow"}:
        raise CheckoutError("unsupported settlement mode")
    code = _clean_text(product_code, label="product_code", max_length=100).lower()
    business = _clean_text(business_name, label="business_name", max_length=200)
    buyer_email = _email(email)
    domain = _domain(target_domain)
    wallet = _wallet(payer_wallet)
    key = _clean_text(idempotency_key, label="idempotency_key", max_length=128)
    if len(key) < 8:
        raise CheckoutError("invalid idempotency_key")

    row = _catalog_row(request, code)
    price_cents = int(row["_amount_cents"])
    acquisition_cents = _basis_amount(row, "acquisition_cost_basis")
    fulfilment_cents = _basis_amount(row, "fulfilment_cost_basis")
    margin_bps = _minimum_margin_bps(row)
    expected_margin_cents = price_cents - acquisition_cents - fulfilment_cents
    if expected_margin_cents < 0:
        raise CheckoutError("catalog economics invalid")
    realized_bps = (expected_margin_cents * 10000) // price_cents
    if realized_bps < margin_bps:
        raise CheckoutError("catalog margin below verified policy")

    buyer_id = _find_or_create_buyer(
        request,
        business_name=business,
        email=buyer_email,
    )
    terms = _terms_payload(
        row=row,
        buyer_email=buyer_email,
        business_name=business,
        target_domain=domain,
        payer_wallet=wallet,
        settlement_mode=settlement_mode,
    )
    terms_sha = _terms_hash(terms)
    order_id = _order_id(key)

    existing = _find_existing_order(request, order_id)
    if existing is not None:
        payload = existing.get("commercial_payload")
        payload = payload if isinstance(payload, Mapping) else {}
        if (
            str(existing.get("buyer_id")) != buyer_id
            or int(existing.get("price_cents") or -1) != price_cents
            or str(payload.get("commercial_terms_sha256") or "") != terms_sha
        ):
            raise CheckoutError("idempotency key belongs to different order")
        return {
            "decision": "existing_order",
            "order_id": order_id,
            "buyer_id": buyer_id,
            "product": public_product(row),
            "terms_sha256": terms_sha,
            "payer_wallet": wallet,
            "settlement_mode": settlement_mode,
            "state": existing.get("state"),
            "payment_request_created": False,
            "actual_revenue": False,
        }

    product_id = _clean_text(row.get("product_id"), label="product_id", max_length=36)
    accepted_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    order_payload = {
        "id": order_id,
        "product_id": product_id,
        "buyer_id": buyer_id,
        "state": "accepted",
        "quantity": 1,
        "price_cents": price_cents,
        "acquisition_cost_cents": acquisition_cents,
        "fulfilment_cost_cents": fulfilment_cents,
        "expected_margin_cents": expected_margin_cents,
        "allocation_key": f"self-serve:{key}",
        "delivery_payload": {
            "delivery_mode": "email_and_secure_link",
            "email": buyer_email,
            "target_domain": domain,
            # Payment approval, independently verified settlement and actual
            # report evidence are separate from order admission. No live
            # first-party fulfilment consumer exists for this request flag.
            "automatic_fulfilment_requested": False,
        },
        "commercial_payload": {
            "source": "self_serve_checkout_v1",
            "product_code": code,
            "product_version": row.get("version"),
            "catalog_state": row.get("catalog_state"),
            "version_state": row.get("version_state"),
            "binding_commercial_terms": True,
            "buyer_terms_accepted": True,
            "buyer_terms_accepted_at": accepted_at,
            "commercial_terms_sha256": terms_sha,
            "terms": terms,
            "payer_wallet": wallet,
            "settlement_asset": "USDT",
            "settlement_network": "BSC",
            "settlement_mode": settlement_mode,
            "actual_revenue": False,
        },
    }
    created = request(
        "POST",
        "/rest/v1/fulfilment_orders",
        payload=order_payload,
        prefer="return=representation",
    ) or []
    if not isinstance(created, list) or not created:
        raise CheckoutError("order creation returned no row")

    return {
        "decision": "order_created",
        "order_id": order_id,
        "buyer_id": buyer_id,
        "product": public_product(row),
        "terms_sha256": terms_sha,
        "state": "accepted",
        "payer_wallet": wallet,
        "settlement_mode": settlement_mode,
        "payment_request_created": False,
        "actual_revenue": False,
    }


def create_payment_request_for_order(
    order: Mapping[str, Any],
    *,
    standing_authority: bool,
    db: Any | None = None,
    config: BscUsdtConfig | BscEscrowConfig | None = None,
    rpc_call=None,
    now: datetime | None = None,
    settlement_mode: str = "direct",
) -> dict[str, Any]:
    if settlement_mode not in {"direct", "escrow"}:
        raise CheckoutError("unsupported settlement mode")
    if order.get("settlement_mode", settlement_mode) != settlement_mode:
        raise CheckoutError("order settlement mode mismatch")
    if order.get("decision") == "existing_order":
        # Existing SQL requires the original block number and expiry when
        # idempotently replaying a payment request. A new anchor/expiry
        # changes the financial terms and would fail or imply a new offer.
        # Hold for dedicated review instead of silently reproposing it.
        return {
            **dict(order),
            "payment_request_created": False,
            "payment_request_status": "existing_order_review_required",
            "payment_instructions_ready": False,
            "next_payment_step": "REVIEW_EXISTING_PAYMENT_REQUEST",
            "treasury_address": None,
            "amount_usdt": None,
            "actual_revenue": False,
        }
    if standing_authority is not True:
        return {
            **dict(order),
            "payment_request_created": False,
            "payment_request_status": "standing_authority_required",
            "actual_revenue": False,
        }
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    product = order.get("product")
    if not isinstance(product, Mapping):
        raise CheckoutError("order product missing")
    try:
        amount_cents = int(product.get("amount_cents"))
    except (TypeError, ValueError) as exc:
        raise CheckoutError("order price missing") from exc
    if amount_cents < 1 or amount_cents > MAX_SELF_SERVE_USD_CENTS:
        raise CheckoutError("order outside self-serve payment limit")
    if settlement_mode == "escrow":
        cfg = config or BscEscrowConfig.from_env()
        if not isinstance(cfg, BscEscrowConfig):
            raise CheckoutError("escrow configuration type mismatch")
    else:
        cfg = config or BscUsdtConfig.from_env()
        if not isinstance(cfg, BscUsdtConfig):
            raise CheckoutError("direct payment configuration type mismatch")
    anchor = get_block_anchor(cfg, rpc_call=rpc_call)
    order_id = _clean_text(order.get("order_id"), label="order_id", max_length=36)
    payer = _wallet(order.get("payer_wallet"))
    common = {
        "fulfilment_order_id": order_id,
        "amount_usdt": Decimal(amount_cents) / Decimal(100),
        "payer_address": payer,
        "min_block_number": int(anchor["block_number"]),
        "expires_at": current + timedelta(hours=24),
        "actor": "self-serve-checkout",
        "now": current,
    }
    if settlement_mode == "escrow":
        plan = build_escrow_proposal(
            **common,
            beneficiary_address=cfg.beneficiary,
            idempotency_key=f"checkout-escrow:{order_id}",
        )
    else:
        plan = build_payment_proposal(
            **common,
            treasury_address=cfg.treasury_address,
            idempotency_key=f"checkout-pay:{order_id}",
        )
    result = submit_payment_proposal(
        plan,
        operator_authorized=True,
        db=db,
    )
    status = result.get("status")
    if settlement_mode == "escrow" and result.get("settlement_mode") != "escrow":
        raise CheckoutError("escrow proposal settlement mode not confirmed")
    if settlement_mode == "direct" and result.get("settlement_mode", "direct") != "direct":
        raise CheckoutError("direct proposal settlement mode not confirmed")
    request_id = str(result.get("request_id") or "")
    try:
        from uuid import UUID
        request_id = str(UUID(request_id))
    except (ValueError, TypeError) as exc:
        raise CheckoutError("payment request identifier invalid") from exc
    if status not in {"pending", "approved"}:
        raise CheckoutError("payment request not in a payable review state")
    # An initially proposed request is PENDING and has not passed the
    # dedicated payment-approver role. Instructing the customer to transfer
    # USDT to an unapproved request would bypass the operator gate.
    # Approved *escrow* requests are still not payable: a separately
    # verified, on-chain EscrowCreated proof must exist before funding.
    ready = status == "approved" and settlement_mode == "direct"
    return {
        **dict(order),
        "settlement_mode": settlement_mode,
        "payment_request_created": True,
        "payment_request_status": status,
        "payment_request_id": request_id,
        "payment_instructions_ready": ready,
        "escrow_creation_verified": False if settlement_mode == "escrow" else None,
        "next_payment_step": (
            "INDEPENDENT_ESCROW_CREATION_PROOF_REQUIRED"
            if settlement_mode == "escrow" and status == "approved" else
            "HUMAN_PAYMENT_REQUEST_APPROVAL_REQUIRED"
            if status == "pending" else "APPROVED_DIRECT_PAYMENT_INSTRUCTIONS"
        ),
        "treasury_address": cfg.treasury_address if ready else None,
        "amount_usdt": (f"{Decimal(amount_cents) / Decimal(100):f}" if ready else None),
        "network": "BSC",
        "chain_id": 56,
        "actual_revenue": False,
    }
