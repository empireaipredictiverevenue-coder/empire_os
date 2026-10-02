"""Retired legacy local marketplace connector.

Canonical buyer identity, capacity, pricing, delivery and settlement belong to
Buyer Acquisition, Commercial Evidence, Commercial Exchange, Revenue Exchange,
fulfilment orders and governed USDT/BSC payment verification.
"""
from __future__ import annotations

from empire_os.payment_rail_policy import RetiredPaymentRailError, retired_component


def status() -> dict:
    payload = retired_component("legacy_marketplace_connector")
    payload["replacement"] = "canonical_commercial_exchange"
    return payload


class BuyerMarketplaceConnector:
    def __init__(self, *_args, **_kwargs):
        raise RetiredPaymentRailError(
            "legacy marketplace connector retired; use canonical Commercial Exchange"
        )
