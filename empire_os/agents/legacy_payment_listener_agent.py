"""Retired legacy payment listener.

Canonical settlement is USDT on BSC through payment_governance and
bsc_usdt_verifier. This module performs no network, payment or database action.
"""
from __future__ import annotations

import json

from empire_os.payment_rail_policy import retired_component


def status() -> dict:
    return retired_component("legacy_payment_listener_agent")


def cycle() -> dict:
    return status()


if __name__ == "__main__":
    print(json.dumps(status(), indent=2, sort_keys=True))
    raise SystemExit(2)
