#!/usr/bin/env python3
"""Refresh the Phase 4 Buyer Acquisition Team runtime plan."""
from __future__ import annotations

import argparse
import json

from empire_os.buyer_acquisition_team import (
    refresh_buyer_acquisition_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_buyer_acquisition_plan(args.repo_root)
    print(json.dumps({
        "ok": True,
        "phase": payload["phase"],
        "demand_gap_count": payload["demand_gap_count"],
        "priority_target_count": len(payload["priority_targets"]),
        "team_role_count": payload["team_role_count"],
        "buyer_pool_count": len(payload["buyer_pools"]),
        "live_outbound_send": payload["automation"]["live_outbound_send"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
