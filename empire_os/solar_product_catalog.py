"""Backward-compatible Solar Opportunity Map catalog wrapper.

Country-native pricing in empire_os.market_pricing is the single source of
truth. This module remains only for older imports and delegates to the GB
localized SKU.
"""
from __future__ import annotations

from typing import Any, Callable

from empire_os.market_pricing import (
    market_price,
    sync_market_price,
)
from empire_os.qualification_worker_v2 import request_json


Request = Callable[..., Any]


def sync_solar_opportunity_map_product(
    request: Request = request_json,
) -> dict[str, Any]:
    result = sync_market_price(
        market_price("GB"),
        request=request,
    )
    return {
        "schema_version": "empire.solar-product-sync.v2",
        "compatibility_wrapper": True,
        "parent_product_code": "solar_opportunity_map",
        **result,
    }
