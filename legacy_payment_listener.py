#!/usr/bin/env python3
"""Retired legacy root listener.

Canonical settlement is USDT on BSC. No chain polling or payment mutation is
performed here.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def main() -> int:
    print(json.dumps(
        retired_component("legacy_payment_listener"),
        indent=2,
        sort_keys=True,
    ))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
