"""
Webhook handlers — PayPal + Crypto payment notifications.

Endpoint: POST /v1/billing/webhook

PayPal events handled:
  - BILLING.SUBSCRIPTION.CREATED — auto-activate subscription
  - BILLING.SUBSCRIPTION.ACTIVATED — confirm activation
  - PAYMENT.SALE.COMPLETED — record invoice paid
  - BILLING.SUBSCRIPTION.CANCELLED — mark cancelled
  - BILLING.SUBSCRIPTION.SUSPENDED — mark past_due

Crypto: we poll instead of receiving webhooks (no inbound webhook
support on most Solana RPC). The poll loop runs every 5 min and
checks pending payment requests.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("billing_webhook")


# ── PayPal webhook verification ───────────────────────────────────

PAYPAL_WEBHOOK_EVENTS = {
    "BILLING.SUBSCRIPTION.CREATED": "subscription_created",
    "BILLING.SUBSCRIPTION.ACTIVATED": "subscription_activated",
    "BILLING.SUBSCRIPTION.CANCELLED": "subscription_cancelled",
    "BILLING.SUBSCRIPTION.SUSPENDED": "subscription_suspended",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED": "payment_failed",
    "PAYMENT.SALE.COMPLETED": "invoice_paid",
    "PAYMENT.SALE.DENIED": "invoice_failed",
}


def verify_paypal_webhook(
    payload: bytes,
    headers: dict,
    webhook_id: str,
    cfg,  # PayPalConfig
) -> tuple:
    """Verify a PayPal webhook signature.

    Returns (is_valid, event_dict_or_error).
    """
    import urllib.request
    import base64

    auth_token = (
        _paypal_get_access_token(cfg) if not cfg._access_token_cached()
        else cfg._access_token
    )

    verify_payload = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO", ""),
        "cert_url": headers.get("PAYPAL-CERT-URL", ""),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
        "webhook_id": webhook_id,
        "webhook_event": json.loads(payload.decode()),
    }
    try:
        req = urllib.request.Request(
            f"{cfg.base_url()}/v1/notifications/verify-webhook-signature",
            data=json.dumps(verify_payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": cfg._auth_header(),
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
        if result.get("verification_status") == "SUCCESS":
            return True, verify_payload["webhook_event"]
        return False, {"error": "invalid_signature", "details": result}
    except Exception as e:
        return False, {"error": f"verify_failed: {e}"}


# ── Event handlers ───────────────────────────────────────────────

@dataclass
class WebhookResult:
    """Result of processing a webhook event."""
    handled: bool = False
    event_type: str = ""
    action: str = ""
    details: str = ""


def handle_paypal_event(event: dict, cfg_store) -> WebhookResult:
    """Apply a PayPal event to the tenant store."""
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    subscription_id = resource.get("id", "")
    custom_id = resource.get("custom_id", "")

    result = WebhookResult(event_type=event_type)

    if event_type == "BILLING.SUBSCRIPTION.CREATED":
        result.handled = True
        result.action = "subscription_created"
        result.details = f"subscription {subscription_id} created"

    elif event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        # Find by paypal_sub_id and activate
        row = cfg_store._conn.execute(
            "SELECT * FROM si_subscription WHERE payment_ref=?",
            (subscription_id,),
        ).fetchone()
        if row:
            cfg_store.activate_subscription(row["subscription_id"],
                                             payment_ref=subscription_id)
            cfg_store.update_tenant(row["tenant_id"], plan=row["plan"])
            result.handled = True
            result.action = "subscription_activated"
            result.details = f"activated {row['subscription_id']}"

    elif event_type == "PAYMENT.SALE.COMPLETED":
        # Mark the latest pending invoice as paid
        inv_id = resource.get("invoice_number", "")
        if inv_id:
            cfg_store.mark_invoice_paid(inv_id,
                                         reference=resource.get("id", ""))
            result.handled = True
            result.action = "invoice_paid"
            result.details = f"invoice {inv_id} paid"

    elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED",
                        "BILLING.SUBSCRIPTION.SUSPENDED"):
        cfg_store._conn.execute(
            "UPDATE si_subscription SET status=? WHERE payment_ref=?",
            ("cancelled" if "CANCELLED" in event_type else "past_due",
             subscription_id),
        )
        cfg_store._conn.commit()
        result.handled = True
        result.action = event_type.split(".")[-1].lower()

    else:
        result.handled = False
        result.details = f"unhandled event type: {event_type}"

    logger.info("paypal webhook: %s → %s", event_type, result.action)
    return result


def handle_crypto_payment(
    cfg_store, billing_engine,
    payment_request_id: str, tx_signature: str, sender_wallet: str,
) -> WebhookResult:
    """Apply a crypto payment notification."""
    result = WebhookResult(event_type="crypto.payment.confirmed")

    # Find the payment request and verify
    row = cfg_store._conn.execute(
        "SELECT * FROM si_subscription WHERE payment_ref=?",
        (payment_request_id,),
    ).fetchone()
    if not row:
        result.details = f"unknown payment_request: {payment_request_id}"
        return result

    verification = billing_engine.verify_crypto_and_activate(
        cfg_store, row["tenant_id"], row["subscription_id"],
        tx_signature, sender_wallet,
    )
    result.handled = verification.get("ok", False)
    result.action = "subscription_activated" if result.handled else "verification_failed"
    result.details = json.dumps(verification)
    return result