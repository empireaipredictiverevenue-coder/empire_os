#!/usr/bin/env python3
"""Retired legacy listener entrypoint.

Use the governed BSC/USDT verifier and payment-governance workflow.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def main() -> int:
    print(json.dumps(
        retired_component("scripts/legacy_payment_listener.py"),
        indent=2,
        sort_keys=True,
    ))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
