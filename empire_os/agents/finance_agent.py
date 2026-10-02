"""Retired legacy vault-reconciliation agent.

Finance truth now comes from governed BSC/USDT payment evidence and canonical
Revenue Truth; this module performs no settlement or balance mutation.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def cycle() -> dict:
    return retired_component("legacy_finance_agent")


if __name__ == "__main__":
    print(json.dumps(cycle(), indent=2, sort_keys=True))
    raise SystemExit(2)
