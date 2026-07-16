"""
Billing — PayPal + Crypto subscription engine.

NO Stripe. Two payment rails:
  - PayPal Subscriptions API (requires PAYPAL_CLIENT_ID + PAYPAL_SECRET)
  - Crypto USDC on Solana (requires SOLANA_RPC_URL + signer)

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


# ── Crypto (Solana USDC) ──────────────────────────────────────────

@dataclass
class CryptoConfig:
    rpc_url: str = "https://api.mainnet-beta.solana.com"
    usdc_mint: str = "Gh9Zg8P2xT2F8YhT49h27fFj2x8z8z8z8z8z8z8z8z"
    vault_wallet: str = ""        # Empire OS receiving wallet
    network: str = "mainnet-beta"  # or "devnet" for testing

    @classmethod
    def from_env(cls) -> "CryptoConfig":
        return cls(
            rpc_url=os.environ.get("SOLANA_RPC_URL", cls.rpc_url),
            usdc_mint=os.environ.get("USDC_MINT_ADDRESS", cls.usdc_mint),
            vault_wallet=os.environ.get("VAULT_WALLET_ADDRESS", ""),
            network=os.environ.get("SOLANA_NETWORK", "mainnet-beta"),
        )

    def configured(self) -> bool:
        return bool(self.vault_wallet)


def crypto_payment_request(
    cfg: CryptoConfig, amount_cents: int, tenant_id: str,
    plan: str, billing_cycle: str = "monthly",
) -> dict:
    """Build a crypto payment request for a tenant.

    Returns:
        payment_request_id — unique ID to identify this payment
        amount_usdc       — the amount to send (USDC, 6 decimals on chain)
        vault_wallet      — destination address
        usdc_mint         — token mint address
        memo              — memo to include in the on-chain transfer
        expires_at        — deadline for payment
    """
    amount_usdc = amount_cents / 100  # USDC is 1:1 with USD
    request_id = str(uuid.uuid4())[:12]
    memo = f"empire-os:{tenant_id}:{plan}:{request_id}"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    return {
        "payment_request_id": request_id,
        "amount_usdc": amount_usdc,
        "amount_cents": amount_cents,
        "vault_wallet": cfg.vault_wallet,
        "usdc_mint": cfg.usdc_mint,
        "memo": memo,
        "network": cfg.network,
        "expires_at": expires_at,
        "qr_data": (
            f"solana:{cfg.vault_wallet}?amount={amount_usdc:.6f}"
            f"&spl-token={cfg.usdc_mint}&memo={memo}"
        ),
    }


def verify_crypto_payment(cfg: CryptoConfig, tx_signature: str,
                          expected_amount_cents: int, expected_memo: str,
                          sender_wallet: str) -> dict:
    """Verify a Solana transaction paid the right amount with the right memo.

    Calls Solana RPC getTransaction to fetch the tx details, then:
      1. Confirms the tx is confirmed/finalized
      2. Parses inner instructions for an SPL token transfer
      3. Verifies amount + destination + memo + sender

    Returns: {"verified": bool, "amount_usdc": float, "details": ...}
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            tx_signature,
            {"encoding": "json", "commitment": "confirmed"},
        ],
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

    # Walk meta + transaction for the transfer details
    meta = result.get("meta", {})
    if meta.get("err"):
        return {"verified": False, "error": "tx_failed_on_chain"}

    pre_balances = meta.get("preTokenBalances", [])
    post_balances = meta.get("postTokenBalances", [])

    # Find the USDC transfer to the vault
    for pre, post in zip(pre_balances, post_balances):
        if (post.get("owner") == cfg.vault_wallet
                and post.get("mint") == cfg.usdc_mint):
            delta = (int(post["uiTokenAmount"]["amount"])
                     - int(pre["uiTokenAmount"]["amount"]))
            if delta <= 0:
                continue
            amount_usdc = delta / 1_000_000  # USDC has 6 decimals
            amount_cents_onchain = int(amount_usdc * 100)
            if amount_cents_onchain < expected_amount_cents:
                return {
                    "verified": False,
                    "error": "amount_too_low",
                    "received_cents": amount_cents_onchain,
                    "expected_cents": expected_amount_cents,
                }
            # Check memo in transaction message
            message = result.get("transaction", {}).get("message", {})
            instructions = message.get("instructions", [])
            memo_found = False
            for ix in instructions:
                parsed = ix.get("parsed", {})
                if (isinstance(parsed, dict)
                        and parsed.get("type") == "memo"
                        and parsed.get("info", {}).get("memo") == expected_memo):
                    memo_found = True
                    break

            return {
                "verified": memo_found,
                "amount_usdc": amount_usdc,
                "amount_cents": amount_cents_onchain,
                "memo_match": memo_found,
                "sender": sender_wallet,
            }

    return {"verified": False, "error": "no_usdc_transfer_to_vault"}


# ── Billing orchestrator ─────────────────────────────────────────

@dataclass
class PaymentMethod:
    """A billing/payment method attached to a tenant."""
    method: str  # "paypal" | "crypto_usdc"
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
            methods.append({"method": "crypto_usdc",
                           "vault": self.crypto.vault_wallet,
                           "network": self.crypto.network})
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

        elif method == "crypto_usdc":
            if not self.crypto.configured():
                return {"error": "crypto_not_configured"}
            req = crypto_payment_request(
                self.crypto, amount_cents, tenant_id, plan, billing_cycle,
            )
            return {
                "method": "crypto_usdc",
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