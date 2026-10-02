"""Retired legacy billing collector.

Canonical payment collection is USDT on BSC and requires verified chain evidence.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def cycle() -> dict:
    return retired_component("billing_collector_agent")


if __name__ == "__main__":
    print(json.dumps(cycle(), indent=2, sort_keys=True))
    raise SystemExit(2)
