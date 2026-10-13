"""Offline buyer-authenticated direct USDT status contract. NOT a public route.

Caller must privately retrieve the persisted binding by keyed HMAC fingerprint.
No persistent storage, wallet movement, or payment activation in this module.
"""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re
import secrets
from collections.abc import Mapping
from uuid import UUID

TOKEN_RE = re.compile(r"^ecs1_[A-Za-z0-9_-]{43}$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")
ADDRESS_RE = re.compile(r"^0x[0-9a-f]{40}$")
DOMAIN = b"empire:direct-bsc:buyer-status:v1:"


class BuyerAccessDenied(ValueError):
    pass


def deny():
    raise BuyerAccessDenied("payment_status_unavailable")


def aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        deny()
    return value.astimezone(timezone.utc)


def uid(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        deny()


def fingerprint(token, key):
    if not isinstance(key, bytes) or len(key) < 32:
        deny()
    if not isinstance(token, str) or TOKEN_RE.fullmatch(token) is None:
        deny()
    raw64 = token[5:]
    try:
        decoded = base64.b64decode(raw64 + "=", altchars=b"-_", validate=True)
    except (ValueError, UnicodeError):
        deny()
    if len(decoded) != 32 or base64.urlsafe_b64encode(decoded).rstrip(b"=").decode() != raw64:
        deny()
    return hmac.new(key, DOMAIN + decoded, hashlib.sha256).hexdigest()


def issue(*, key: bytes, order_id: str, now: datetime, expires_at: datetime):
    issued = aware(now)
    expiry = aware(expires_at)
    if not issued < expiry <= issued + timedelta(hours=48):
        deny()
    order = uid(order_id)
    raw = secrets.token_bytes(32)
    token = "ecs1_" + base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    return {
        "deliver_token_once": token,
        "persist_only": {
            "token_fingerprint": fingerprint(token, key),
            "order_id": order,
            "issued_at": issued,
            "expires_at": expiry,
            "revoked_at": None,
        },
    }


def _amount(value):
    if isinstance(value, (float, bool)) or not isinstance(value, (str, int, Decimal)):
        deny()
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n <= 0 or n.as_tuple().exponent < -18:
            deny()
        return format(n, "f")
    except (InvalidOperation, ValueError):
        deny()


def status(*, token, key, access, order, payment, evidence, treasury, now):
    current = aware(now)
    if not isinstance(access, Mapping) or not isinstance(order, Mapping):
        deny()
    digest = access.get("token_fingerprint")
    if not isinstance(digest, str) or not HEX_RE.fullmatch(digest):
        deny()
    if not hmac.compare_digest(fingerprint(token, key), digest):
        deny()
    issued, expiry = aware(access.get("issued_at")), aware(access.get("expires_at"))
    if access.get("revoked_at") is not None or not issued <= current < expiry or expiry > issued + timedelta(hours=48):
        deny()
    oid = uid(access.get("order_id"))
    if uid(order.get("id")) != oid or order.get("state") not in {"accepted", "invoiced", "delivered", "confirmed"}:
        deny()
    terms = (order.get("commercial_payload") or {}).get("commercial_terms_sha256")
    if not isinstance(terms, str) or not HEX_RE.fullmatch(terms):
        deny()
    # The retained order must identify the same authorized sending wallet
    # and exact USD-cent price as the approved direct-USDT payment request.
    original_payer = str((order.get("commercial_payload") or {}).get("payer_wallet") or "").lower()
    if not ADDRESS_RE.fullmatch(original_payer):
        deny()
    price_cents = order.get("price_cents")
    if type(price_cents) is not int or not 1 <= price_cents <= 29900:
        deny()
    if payment is None:
        if access.get("request_id") is not None or evidence is not None:
            deny()
        return {"status": "awaiting_payment_request", "payment_instructions_ready": False}
    if not isinstance(payment, Mapping):
        deny()
    rid = uid(payment.get("id"))
    receiver = str(treasury).lower()
    if (access.get("request_id") is None or uid(access["request_id"]) != rid or
            uid(payment.get("fulfilment_order_id")) != oid or
            uid(payment.get("buyer_id")) != uid(order.get("buyer_id")) or
            payment.get("settlement_mode") != "direct" or
            payment.get("commercial_terms_sha256") != terms or
            str(payment.get("payer_address") or "").lower() != original_payer or
            Decimal(_amount(payment.get("amount_usdt"))) != Decimal(price_cents) / Decimal(100) or
            not ADDRESS_RE.fullmatch(receiver) or
            str(payment.get("treasury_address") or "").lower() != receiver):
        deny()
    pstatus = payment.get("status")
    expiry = aware(payment.get("expires_at"))
    if pstatus not in {"pending", "approved", "cancelled", "expired"}:
        deny()
    if pstatus == "approved":
        # Even a recorded receipt must be traceable to an independently
        # approved, non-future payment request with a valid approval window.
        approval_time = aware(payment.get("approved_at"))
        if (not isinstance(payment.get("approved_by"), str) or
                not payment["approved_by"].strip() or
                not issued <= approval_time <= current or
                not approval_time < expiry):
            deny()
    if evidence is not None:
        if (not isinstance(evidence, Mapping) or pstatus != "approved" or
                uid(evidence.get("request_id")) != rid or
                uid(evidence.get("fulfilment_order_id")) != oid or
                evidence.get("chain_id") != 56 or
                str(evidence.get("token_contract") or "").lower() !=
                "0x55d398326f99059ff775485246999027b3197955" or
                str(evidence.get("treasury_address") or "").lower() != receiver or
                evidence.get("commercial_terms_sha256") != terms or
                type(evidence.get("confirmations")) is not int or
                evidence["confirmations"] < 12):
            deny()
        return {"status": "payment_evidence_recorded", "payment_instructions_ready": False}
    if pstatus in {"cancelled", "expired"} or current >= expiry:
        return {"status": "payment_request_expired_or_cancelled", "payment_instructions_ready": False}
    if pstatus == "pending":
        return {"status": "awaiting_human_approval", "payment_instructions_ready": False}
    approved = aware(payment.get("approved_at"))
    if (not isinstance(payment.get("approved_by"), str) or
            not payment["approved_by"].strip() or not issued <= approved <= current < expiry):
        deny()
    return {
        "status": "approved_payment_instructions",
        "payment_instructions_ready": True,
        "amount_usdt": _amount(payment.get("amount_usdt")),
        "treasury_address": receiver,
        "network": "BSC",
        "asset": "USDT",
        "chain_id": 56,
    }
