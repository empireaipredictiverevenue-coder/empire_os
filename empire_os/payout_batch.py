"""Retired legacy payout batch surface.

No payout transaction is constructed here. Treasury movement remains operator/
founder governed and must use the canonical USDT/BSC treasury workflow.
"""
from __future__ import annotations
from empire_os.payment_rail_policy import RetiredPaymentRailError, retired_component

def status() -> dict:
    return retired_component("legacy_payout_batch")

def build_payout_batch(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy payout batch retired; use governed USDT/BSC treasury flow")
