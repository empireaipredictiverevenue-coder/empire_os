#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.solar_economics_policy import (
    build_market_economics_proposal,
)


def main() -> int:
    print(json.dumps(
        build_market_economics_proposal(),
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
