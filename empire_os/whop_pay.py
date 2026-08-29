"""Whop payment integration for Empire OS invoices.

Whop is a fiat rail (card / PayPal / Apple Pay) that settles to the operator's
Whop balance, complementing the crypto (BSC-USDT) rail. It is offered on the
hosted /pay/{invoice_id} page as the 'pay with card' option.

Design rules (revenue lockdown):
- Whop is OPTIONAL and fails CLOSED: if WHOP_API_KEY / product IDs are unset,
  the pay page silently omits the Whop button and keeps the crypto rail.
- The crypto vault remains the canonical settlement address (pay_link.vault_address()).
- Whop webhooks mark si_invoice.paid via verified HMAC (header whop-signature).
"""
from __future__ import annotations
import os
import json
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone

DB = "/root/empire_os/empire_os.db"


def _plan_product_map():
    raw = os.environ.get("WHOP_PLAN_PRODUCTS", "")
    out = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        plan, pid = pair.split("=", 1)
        out[plan.strip().lower()] = pid.strip()
    return out


def whop_configured():
    return bool(os.environ.get("WHOP_API_KEY")) and bool(_plan_product_map())


def plan_product_id(plan):
    return _plan_product_map().get((plan or "").strip().lower())


def whop_enabled_for_plan(plan):
    return whop_configured() and bool(plan_product_id(plan))


def build_whop_url(plan):
    """Return a Whop checkout/product URL for the plan, or None if not configured."""
    pid = plan_product_id(plan)
    if not pid:
        return None
    return "https://whop.com/product/%s" % pid


def verify_webhook(raw_body, signature):
    """Verify a Whop webhook signature (HMAC-SHA256 of raw body with WHOP_API_KEY)."""
    key = os.environ.get("WHOP_API_KEY", "")
    if not key or not signature:
        return False
    digest = hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def mark_invoice_paid_by_whop(order_id, plan=None):
    """Mark the invoice referenced by a Whop order as paid.

    Whop orders carry a metadata/memo field; we store the invoice_id there at
    checkout-creation time. Falls back to matching a stored mapping table
    si_whop_order(order_id, invoice_id).
    """
    c = sqlite3.connect(DB, timeout=30)
    try:
        row = c.execute(
            "SELECT invoice_id FROM si_whop_order WHERE order_id=?", (order_id,)
        ).fetchone()
        inv_id = row[0] if row else None
        if not inv_id:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            "UPDATE si_invoice SET paid=1, paid_at=?, paid_method='whop', "
            "paid_ref=? WHERE invoice_id=? AND (paid IS NULL OR paid=0)",
            (now, order_id, inv_id),
        )
        n = c.total_changes
        c.commit()
        return n
    finally:
        c.close()
