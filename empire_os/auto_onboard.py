"""Retired legacy buyer auto-onboarding path.

Canonical buyer activation requires verified commercial evidence and governed
USDT/BSC payment evidence. This module cannot create buyers, subscriptions,
seats, invoices or payment state.
"""
from __future__ import annotations

from empire_os.payment_rail_policy import RetiredPaymentRailError, retired_component


def status() -> dict:
    return retired_component("legacy_auto_onboard")


def onboard(*_args, **_kwargs):
    raise RetiredPaymentRailError(
        "legacy auto-onboard retired; use buyer commercial evidence, "
        "capacity readiness and governed USDT/BSC activation"
    )
