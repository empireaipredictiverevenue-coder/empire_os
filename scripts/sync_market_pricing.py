#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.market_pricing import (
    pricing_matrix,
    sync_solar_market_pricing,
)


def main() -> int:
    result = sync_solar_market_pricing()
    print(json.dumps({
        **result,
        "matrix": pricing_matrix(),
    }, indent=2, sort_keys=True))
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
