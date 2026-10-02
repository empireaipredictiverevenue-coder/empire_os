#!/usr/bin/env python3
"""Retired legacy bulk lead activation script.

The former script mixed canonical prospects with hard-coded pricing, local CRM
state and automatic outreach. Lead generation remains active through canonical
source/qualification pipelines; monetization is governed by Commercial Exchange.
"""
from __future__ import annotations
import json
from empire_os.payment_rail_policy import retired_component


def status() -> dict:
    payload = retired_component("legacy_supabase_lead_activation")
    payload["replacement"] = "canonical_lead_generation_and_commercial_exchange"
    return payload


def main() -> int:
    print(json.dumps(status(), indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
