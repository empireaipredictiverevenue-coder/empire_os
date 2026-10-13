"""One-time buyer status receipt for a NEW canonical BSC checkout order.

The checkout writer has already committed a unique pending payment request.
This module only adds an optional buyer-held bearer to that *same* successful
response after a separate restricted 050 issuer has committed its fingerprint.
Never uses an order UUID or email as bearer recovery, and never reissues on
idempotent checkout retries. No mail or payment execution here.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.direct_bsc_buyer_status import (
    BuyerAccessDenied, uid, deny, aware,
)
from empire_os.direct_bsc_buyer_status_private_issuer import (
    mint_private_buyer_access,
)


def with_new_buyer_status_receipt(
    checkout_result: Mapping[str,Any],
    *,
    enabled: bool,
    hmac_key: bytes,
    request_lookup: Callable[[str],Mapping[str,Any]|None],
    persist_fingerprint: Callable[[dict[str,Any]],Mapping[str,Any]],
    now: datetime|None=None,
) -> dict[str,Any]:
    """No token on replay/error/escrow/approval. Strict first-issued only.

    Never mutates input. Failed token issuance leaves the already-committed
    checkout order intact, but does NOT suggest payment instructions.
    """
    out=dict(checkout_result)
    out["buyer_status_token_delivered"]=False
    out["buyer_status_release_active"]=False
    if enabled is not True:
        return out
    try:
        if (out.get("decision")!="order_created"
            or out.get("settlement_mode")!="direct"
            or out.get("payment_request_created") is not True
            or out.get("payment_request_status")!="pending"
            or out.get("payment_instructions_ready") is not False
            or out.get("actual_revenue") is not False):
            return out
        oid=uid(out.get("order_id"))
        rid=uid(out.get("payment_request_id"))
        if not callable(request_lookup) or not callable(persist_fingerprint):
            deny()
        evidence=request_lookup(rid)
        if not isinstance(evidence,Mapping) or set(evidence)!={
            "id","fulfilment_order_id","settlement_mode","status",
            "created_at","expires_at"
        }:
            deny()
        # The database 050 issuer independently revalidates all conditions
        # on the actual canonical request under SECURITY DEFINER.
        token=mint_private_buyer_access(
            approved_order_id=oid,
            approved_request_id=rid,
            payment_request=evidence,
            hmac_key=hmac_key,
            persist=persist_fingerprint,
            now=aware(now or datetime.now(timezone.utc)),
        )
        out["buyer_status_token"]=token
        out["buyer_status_token_delivered"]=True
        out["buyer_status_release_active"]=True
        out["buyer_status_delivery_method"]="first_party_checkout_response_once"
        out["buyer_status_recovery"]="founder_verified_email_review_only"
    except Exception:
        # Payment request was ALREADY created; do not resubmit, silently
        # invent a receipt or disclose any partial issuer/DB details.
        out["buyer_status_unavailable"]=True
        out["buyer_status_recovery"]="founder_verified_email_review_only"
    return out
