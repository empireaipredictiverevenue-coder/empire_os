"""Retired legacy verification loop.

The old loop coupled SQLite onboarding to a retired payment rail. Current
verification belongs to Commercial Evidence, Buyer Capacity and Revenue Truth.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def cycle() -> dict:
    return retired_component("legacy_verify_loop")


if __name__ == "__main__":
    print(json.dumps(cycle(), indent=2, sort_keys=True))
    raise SystemExit(2)
