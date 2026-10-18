#!/usr/bin/env python3
"""Read-only existing Search Fabric cache inventory; never a live rank lookup."""
from __future__ import annotations

import argparse
import json

from empire_os.search_intelligence.serp_cache_inventory import (
    SCHEMA, SerpCacheInventoryHeld, inspect_cache,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_cache()
    except (SerpCacheInventoryHeld, Exception):
        result = {
            "schema_version": SCHEMA,
            "status": "CACHE_SOURCE_HELD",
            "mode": "READ_ONLY",
            "independent_google_rank_positions_verified": False,
            "live_serp_engine_probed": False,
            "paid_api_calls": 0,
            "database_writes": False,
            "execution_authority": "NONE",
        }
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"] == "CACHE_INVENTORY_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
