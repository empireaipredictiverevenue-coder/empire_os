#!/usr/bin/env python3
"""Retired legacy A2A settlement bridge.

The former implementation created legacy payment charges from file-backed
A2A quotes. EmpireOS canonical settlement is BSC/USDT and all payment/accounting
actions must flow through governed canonical payment evidence.
"""
from __future__ import annotations

import sys

RETIRED_REASON = (
    "retired_legacy_a2a_settlement_use_canonical_bsc_usdt"
)


def main() -> int:
    print(RETIRED_REASON, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
