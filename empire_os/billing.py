"""
Billing — PayPal + Crypto subscription engine.

NO Stripe. Two payment rails:
  - PayPal Subscriptions API (requires PAYPAL_CLIENT_ID + PAYPAL_SECRET)
  - Crypto USDT on BSC (BEP20) (requires BSC_RPC + signer)

If neither is configured, subscriptions stay in 'pending' status until
manually marked paid via the dashboard / API.

Webhook handlers for both:
  - PayPal: BILLING.SUBSCRIPTION.CREATED, PAYMENT.SALE.COMPLETED, etc.
  - Crypto: payment-receipt webhook (custom, requires running a watcher)
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("billing")


# ── PayPal ────────────────────────────────────────────────────────

PAYPAL_API_BASE = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live":    "https://api-m.paypal.com",
}


@dataclass
class PayPalConfig:
    client_id: str = ""
    secret: str = ""
    mode: str = "sandbox"  # "sandbox" or "live"

    @classmethod
    def from_env(cls) -> "PayPalConfig":
        return cls(
            client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
            secret=os.environ.get("PAYPAL_SECRET", ""),
            mode=os.environ.get("PAYPAL_MODE", "sandbox"),
        )

    def configured(self) -> bool:
        return bool(self.client_id and self.secret)

    def base_url(self) -> str:
        return PAYPAL_API_BASE[self.mode]

    def _auth_header(self) -> str:
        creds = f"{self.client_id}:{self.secret}".encode()
        return "Basic " + base64.b64encode(creds).decode()


def _paypal_request(cfg: PayPalConfig, method: str, path: str,
                    payload: Optional[dict] = None,
                    expect_json: bool = True) -> dict:
    """Make an authenticated PayPal API request."""
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        f"{cfg.base_url()}{path}",
        data=data, method=method,
        headers={
            "Authorization": cfg._auth_header(),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if expect_json else {"raw": body}
    except urllib.error.HTTPError as e:
        return {"error": f"http_{e.code}", "body": e.read().decode()[:500]}


def paypal_create_subscription(cfg: PayPalConfig, plan_id: str,
                              return_url: str = "", cancel_url: str = "") -> dict:
    """Create a PayPal subscription.

    plan_id: the PayPal plan ID (created separately in PayPal dashboard)
    """
    payload = {
        "plan_id": plan_id,
        "application_context": {
            "brand_name": "Empire OS",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "payment_method": {
                "payer_selected": "PAYPAL",
                "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED",
            },
            "return_url": return_url or "https://empire-os.local/paypal/return",
            "cancel_url": cancel_url or "https://empire-os.local/paypal/cancel",
        },
    }
    return _paypal_request(cfg, "POST", "/v1/billing/subscriptions", payload)


def paypal_get_subscription(cfg: PayPalConfig, subscription_id: str) -> dict:
    """Get PayPal subscription status."""
    return _paypal_request(cfg, "GET", f"/v1/billing/subscriptions/{subscription_id}")


def paypal_cancel_subscription(cfg: PayPalConfig, subscription_id: str, reason: str = "") -> dict:
    """Cancel a PayPal subscription."""
    payload = {"reason": reason or "Cancelled by customer"}
    return _paypal_request(
        cfg, "POST",
        f"/v1/billing/subscriptions/{subscription_id}/cancel",
        payload, expect_json=False,
    )


def paypal_create_plan(cfg: PayPalConfig, plan_name: str, price_cents: int,
                       interval: str = "MONTH") -> dict:
    """Create a PayPal billing plan (one-time setup per plan tier).

    interval: MONTH | YEAR
    """
    payload = {
        "product_id": "EMPIRE-OS-PRODUCT",  # assumed product created in PayPal dashboard
        "name": plan_name,
        "description": f"Empire OS {plan_name} plan",
        "status": "ACTIVE",
        "billing_cycles": [{
            "frequency": {"interval_unit": interval, "interval_count": 1},
            "tenure_type": "REGULAR",
            "sequence": 1,
            "total_cycles": 0,  # 0 = infinite
            "pricing_scheme": {
                "fixed_price": {
                    "value": f"{price_cents / 100:.2f}",
                    "currency_code": "USD",
                },
            },
        }],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee": {"value": "0", "currency_code": "USD"},
            "setup_fee_failure_action": "CANCEL",
            "payment_failure_threshold": 3,
        },
    }
    return _paypal_request(cfg, "POST", "/v1/billing/plans", payload)


# ── Crypto (BSC USDT BEP20) ───────────────────────────────────────
# Authoritative revenue vault (must match the live bsc_listener). Never
# default to the banned placeholder — that silently mints uncollectable links.
BSC_WALLET_ADDR = os.environ.get("BSC_WALLET_ADDRESS",
    "0x1339b487046B0ad924a10c20b1791608EA8595a8")

@dataclass
class CryptoConfig:
    rpc_url: str = "https://bsc-dataseed.binance.org"
    usdt_contract: str = "0x55d398326f99059fF775485246999027B3197955"
    vault_wallet: str = ""        # Empire OS receiving wallet
    network: str = "bsc"          # BSC mainnet

    @classmethod
    def from_env(cls) -> "CryptoConfig":
        return cls(
            rpc_url=os.environ.get("BSC_RPC", cls.rpc_url),
            usdt_contract=os.environ.get("BSC_USDT_CONTRACT", cls.usdt_contract),
            vault_wallet=BSC_WALLET_ADDR,
            network="bsc",
        )

    def configured(self) -> bool:
        return bool(self.vault_wallet)


def crypto_payment_request(
    cfg: CryptoConfig, amount_cents: int, tenant_id: str,
    plan: str, billing_cycle: str = "monthly",
) -> dict:
    """Build a crypto payment request for a tenant (BSC USDT BEP20).

    Returns:
        amount_usdt       — the amount to send (USDT, 18 decimals on BSC)
        vault_wallet      — destination address
        usdt_contract     — token contract address
        memo              — memo to include in the transfer
        expires_at        — deadline for payment
    """
    amount_usdt = amount_cents / 100  # USDT is 1:1 with USD
    request_id = str(uuid.uuid4())[:12]
    memo = f"empire-os:{tenant_id}:{plan}:{request_id}"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    return {
        "payment_request_id": request_id,
        "amount_usdt": amount_usdt,
        "amount_cents": amount_cents,
        "vault_wallet": cfg.vault_wallet,
        "usdt_contract": cfg.usdt_contract,
        "memo": memo,
        "network": cfg.network,
        "expires_at": expires_at,
        "qr_data": (
            f"bsc:{cfg.vault_wallet}?amount={amount_usdt:.6f}"
            f"&contract={cfg.usdt_contract}&memo={memo}"
        ),
    }


def verify_crypto_payment(cfg: CryptoConfig, tx_signature: str,
                          expected_amount_cents: int, expected_memo: str,
                          sender_wallet: str) -> dict:
    """Verify a BSC USDT (BEP20) transfer.

    Uses BSC RPC eth_getTransactionReceipt to fetch the tx, then:
      1. Confirms the tx was successful (status=0x1)
      2. Parses Transfer event logs from the USDT contract
      3. Verifies amount + destination (vault)

    Returns: {"verified": bool, "amount_usdt": float, "details": ...}
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionReceipt",
        "params": [tx_signature],
    }
    try:
        req = urllib.request.Request(
            cfg.rpc_url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {"verified": False, "error": f"rpc_unreachable: {e}"}

    result = data.get("result")
    if not result:
        return {"verified": False, "error": "tx_not_found"}

    # Check status (0x1 = success)
    status = result.get("status", "0x0")
    if status != "0x1":
        return {"verified": False, "error": "tx_failed_on_chain"}

    # Parse Transfer event logs (USDT BEP20 Transfer: 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df8896efa)
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df8896efa"
    vault_hex = "0x" + ("0" * 24) + cfg.vault_wallet[2:].lower()
    logs = result.get("logs", [])

    for log in logs:
        topics = log.get("topics", [])
        if len(topics) < 3:
            continue
        if topics[0].lower() == transfer_topic:
            to_addr = topics[2].lower()
            if to_addr == vault_hex.lower():
                # USDT has 18 decimals on BSC
                raw_amount = int(log.get("data", "0x0"), 16)
                amount_usdt = raw_amount / 1e18
                amount_cents_onchain = int(amount_usdt * 100)
                if amount_cents_onchain < expected_amount_cents:
                    return {
                        "verified": False,
                        "error": "amount_too_low",
                        "received_cents": amount_cents_onchain,
                        "expected_cents": expected_amount_cents,
                    }
                return {
                    "verified": True,
                    "amount_usdt": amount_usdt,
                    "amount_cents": amount_cents_onchain,
                    "sender": sender_wallet,
                    "tx_hash": tx_signature,
                }

    return {"verified": False, "error": "no_usdt_transfer_to_vault"}


# ── Billing orchestrator ─────────────────────────────────────────

@dataclass
class PaymentMethod:
    """A billing/payment method attached to a tenant."""
    method: str  # "paypal" | "crypto_usdt"
    enabled: bool = False
    reference: str = ""  # PayPal subscription ID or wallet address
    last_payment_at: str = ""


class BillingEngine:
    """High-level billing engine — routes subscription payments to PayPal or Crypto."""

    def __init__(self):
        self.paypal = PayPalConfig.from_env()
        self.crypto = CryptoConfig.from_env()

    def available_methods(self) -> list:
        methods = []
        if self.paypal.configured():
            methods.append({"method": "paypal", "mode": self.paypal.mode})
        if self.crypto.configured():
            methods.append({"method": "crypto_usdt",
                           "vault": self.crypto.vault_wallet,
                           "network": "BSC",
                           "token": "USDT",
                           "contract": os.environ.get("BSC_USDT_CONTRACT",
                               "0x55d398326f99059fF775485246999027B3197955")})
        return methods

    def start_subscription(
        self, tenant_id: str, plan: str, billing_cycle: str,
        seats: int, method: str,
    ) -> dict:
        """Initiate a subscription via the chosen payment method.

        Returns dict with payment_url (PayPal) or payment_request (Crypto).
        """
        from empire_os.tenants import PLANS, compute_invoice_amount
        amount_cents = compute_invoice_amount(plan, seats, billing_cycle)

        if method == "paypal":
            if not self.paypal.configured():
                return {"error": "paypal_not_configured"}
            # Create a plan if not exists (caller pre-creates these)
            plan_id = f"EMPIRE-{plan.upper()}-{billing_cycle.upper()}"
            result = paypal_create_subscription(
                self.paypal, plan_id,
                return_url=f"https://hub.empire-os.local/v1/billing/return?tenant={tenant_id}",
                cancel_url=f"https://hub.empire-os.local/v1/billing/cancel?tenant={tenant_id}",
            )
            if "id" in result:
                return {
                    "method": "paypal",
                    "subscription_id": result["id"],
                    "approval_url": next(
                        (l["href"] for l in result.get("links", [])
                         if l.get("rel") == "approve"), None
                    ),
                    "amount_cents": amount_cents,
                    "plan": plan,
                    "billing_cycle": billing_cycle,
                }
            return {"error": "paypal_create_failed", "details": result}

        elif method in ("crypto_usdt", "crypto_usdc"):
            # Accept both names — crypto_usdt is current (BSC USDT BEP20),
            # crypto_usdc kept as legacy alias for existing callers.
            if not self.crypto.configured():
                return {"error": "crypto_not_configured"}
            req = crypto_payment_request(
                self.crypto, amount_cents, tenant_id, plan, billing_cycle,
            )
            return {
                "method": "crypto_usdt",
                "amount_cents": amount_cents,
                "plan": plan,
                "billing_cycle": billing_cycle,
                **req,
            }

        return {"error": f"unknown_method: {method}"}

    def verify_crypto_and_activate(
        self, cfg_store, tenant_id: str, subscription_id: str,
        tx_signature: str, sender_wallet: str,
    ) -> dict:
        """Verify a crypto payment and activate the subscription."""
        sub = cfg_store.get_active_subscription(tenant_id) or \
              cfg_store._conn.execute(
                  "SELECT * FROM si_subscription WHERE subscription_id=?",
                  (subscription_id,),
              ).fetchone()
        if not sub:
            return {"error": "subscription_not_found"}

        expected_memo = f"empire-os:{tenant_id}:{sub['plan']}:{subscription_id}"
        result = verify_crypto_payment(
            self.crypto, tx_signature,
            sub["price_cents"], expected_memo, sender_wallet,
        )

        if result.get("verified"):
            cfg_store.activate_subscription(
                subscription_id, payment_ref=tx_signature,
            )
            cfg_store.mark_invoice_paid(
                f"inv-{subscription_id}", reference=tx_signature,
            )
            # Upgrade tenant plan
            cfg_store.update_tenant(tenant_id, plan=sub["plan"])
            return {"ok": True, "subscription_id": subscription_id, "verified": result}

        return {"ok": False, "verification": result}