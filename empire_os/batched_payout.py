"""Retired legacy batched payout transaction builder."""
from __future__ import annotations
from empire_os.payment_rail_policy import RetiredPaymentRailError, retired_component

def status() -> dict:
    return retired_component("legacy_batched_payout")

def build_batched_payout_tx(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy batched payout retired; use governed USDT/BSC treasury flow")

def verify_batched_payout_tx(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy batched payout verifier retired; use BSC/USDT verifier")
