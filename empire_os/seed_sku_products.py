"""Retired legacy SQLite SKU seeder.

Canonical sellable products and prices are owned by the Commercial Catalog.
This compatibility entrypoint performs no database mutation.
"""
from __future__ import annotations
import json
from empire_os.payment_rail_policy import retired_component

def status() -> dict:
    payload = retired_component("legacy_sku_price_seeder")
    payload["replacement"] = "canonical_commercial_catalog"
    return payload

def main() -> int:
    print(json.dumps(status(), indent=2, sort_keys=True))
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
