#!/usr/bin/env python3
"""Carrier config + failover for Empire OS PPC switchboard.

G-2 gate: adds Telnyx as redundant carrier alongside Vonage.
Configures carrier priority + failover routing.

Usage:
  - Set TELNYX_API_KEY in social.env
  - Set TELNYX_CONNECTION_ID (SIP connection ID)
  - Set TELNYX_DID_POOL (comma-separated DIDs)
  - Vonage remains primary until 1k+ calls/day
"""
from __future__ import annotations
import os, json
from pathlib import Path

FEEDBACK = Path("/root/feedback")
CARRIER_LOG = FEEDBACK / "carrier_failover.jsonl"

# ── Carrier configuration ──────────────────────────────────────────────────
CARRIERS = {
    "vonage": {
        "priority": 1,  # primary
        "api_key": os.environ.get("VONAGE_API_KEY", ""),
        "api_secret": os.environ.get("VONAGE_API_SECRET", ""),
        "number_a": os.environ.get("VONAGE_NUMBER_A", ""),
        "number_b": os.environ.get("VONAGE_NUMBER_B", ""),
        "number_c": os.environ.get("VONAGE_NUMBER_C", ""),
        "track_a": os.environ.get("VONAGE_TRACK_A", ""),
        "track_b": os.environ.get("VONAGE_TRACK_B", ""),
        "track_c": os.environ.get("VONAGE_TRACK_C", ""),
        "cost_per_min": 0.015,  # USD
        "active": bool(os.environ.get("VONAGE_API_KEY", "")),
    },
    "telnyx": {
        "priority": 2,  # failover
        "api_key": os.environ.get("TELNYX_API_KEY", ""),
        "connection_id": os.environ.get("TELNYX_CONNECTION_ID", ""),
        "did_pool": os.environ.get("TELNYX_DID_POOL", "").split(",") if os.environ.get("TELNYX_DID_POOL") else [],
        "cost_per_min": 0.010,  # USD (cheaper than Vonage)
        "active": bool(os.environ.get("TELNYX_API_KEY", "")),
    },
}

# ── Failover logic ─────────────────────────────────────────────────────────
_failover_history = []

def get_carrier(lane_key: str = "") -> dict:
    """Get best available carrier for a lane.

    Priority order: vonage (primary) → telnyx (failover).
    If primary is down, use failover.
    """
    primary = CARRIERS["vonage"] if CARRIERS["vonage"]["active"] else None
    failover = CARRIERS["telnyx"] if CARRIERS["telnyx"]["active"] else None

    if primary and primary["active"]:
        return primary
    if failover and failover["active"]:
        _log_failover("vonage_down", lane_key, "switched to telnyx")
        return failover
    # No active carrier
    return {"name": "none", "active": False, "priority": 99}

def _log_failover(reason: str, lane_key: str, action: str):
    """Log failover events for audit."""
    import json
    from datetime import datetime, timezone
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "lane_key": lane_key,
        "action": action,
    }
    _failover_history.append(entry)
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    with open(CARRIER_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def health_check() -> dict:
    """Check carrier health."""
    result = {}
    for name, cfg in CARRIERS.items():
        result[name] = {
            "active": cfg["active"],
            "priority": cfg["priority"],
            "cost_per_min": cfg["cost_per_min"],
            "has_api_key": bool(cfg.get("api_key", "")),
        }
    return result

def get_did(carrier_name: str = "vonage") -> str:
    """Get an available DID from the carrier's pool."""
    carrier = CARRIERS.get(carrier_name, {})
    if carrier_name == "vonage":
        # Round-robin Vonage numbers
        nums = [carrier.get(f"number_{c}", "") for c in "abc"]
        nums = [n for n in nums if n]
        return nums[0] if nums else ""
    elif carrier_name == "telnyx":
        dids = carrier.get("did_pool", [])
        return dids[0] if dids else ""
    return ""

if __name__ == "__main__":
    print("Carrier config:")
    for name, cfg in CARRIERS.items():
        print(f"  {name}: active={cfg['active']} priority={cfg['priority']} cost=${cfg['cost_per_min']}/min")
    print(f"\nHealth: {json.dumps(health_check(), indent=2)}")
    print(f"\nBest carrier: {get_carrier()['name'] if get_carrier().get('name') else 'none'}")
    print("G-2 Telnyx carrier config: OK")
