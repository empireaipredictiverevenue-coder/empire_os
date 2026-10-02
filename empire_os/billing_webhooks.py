"""Retired legacy billing webhook surface."""
from __future__ import annotations
from empire_os.payment_rail_policy import RetiredPaymentRailError, retired_component
PAYPAL_WEBHOOK_EVENTS = frozenset()

def status() -> dict:
    return retired_component("legacy_billing_webhooks")

def handle_paypal_event(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy billing webhook retired; use governed USDT/BSC evidence")

def handle_crypto_payment(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy crypto webhook retired; use BSC/USDT verifier")
