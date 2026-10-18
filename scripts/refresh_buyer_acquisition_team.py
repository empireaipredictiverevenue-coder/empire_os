#!/usr/bin/env python3
"""Refresh the Phase 4 Buyer Acquisition Team runtime plan."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from empire_os.buyer_acquisition_team import (
    refresh_buyer_acquisition_plan,
)


def refresh_existing_workspace_reply_snapshot() -> dict:
    """Bounded read-only provider scan using the existing five-minute timer.

    A tracking failure must not fail the canonical buyer-acquisition plan,
    and provider text/errors must not leak into the regular service journal.
    This does not qualify leads, send email, create CRM records or alter
    the separate historic personal Gmail buyer importer.
    """
    cmd = (
        sys.executable, "-B", "-m",
        "scripts.poll_workspace_solar_outreach_readonly", "--write",
    )
    try:
        completed = subprocess.run(
            cmd, cwd="/srv/empire_os", capture_output=True, text=True,
            timeout=35, check=False,
        )
        if completed.returncode != 0 or len(completed.stdout) > 5000:
            raise ValueError("INCOMPLETE_WORKSPACE_REPLY_SNAPSHOT")
        data = json.loads(completed.stdout.strip())
        if (not isinstance(data, dict)
                or data.get("status") != "WORKSPACE_SENT_ANCHORS_VERIFIED_REVIEW_ONLY"
                or data.get("source_scan_complete") is not True
                or data.get("snapshot_written") is not True
                or data.get("verified_sent_anchors_in_live_mailbox") != 6
                or type(data.get("new_inbound_header_candidates")) is not int
                or data.get("new_inbound_header_candidates") < 0
                or data.get("outbound_sent") is not False
                or data.get("database_writes") is not False):
            raise ValueError("WORKSPACE_REPLY_SNAPSHOT_UNVERIFIED")
        return {
            "status": "SIX_THREAD_WORKSPACE_SNAPSHOT_REFRESHED",
            "verified_sent_anchors": 6,
            "new_inbound_header_candidates": data["new_inbound_header_candidates"],
            "outbound_sent": False,
            "database_writes": False,
        }
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return {
            "status": "HELD_WORKSPACE_SNAPSHOT_NOT_REFRESHED",
            "verified_sent_anchors": 0,
            "new_inbound_header_candidates": None,
            "outbound_sent": False,
            "database_writes": False,
        }


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
        "product_demand_count": payload["product_demand_count"],
        "sellable_product_demand_count": payload[
            "sellable_product_demand_count"
        ],
        "market_validate_product_count": payload[
            "market_validate_product_count"
        ],
        "team_role_count": payload["team_role_count"],
        "buyer_pool_count": len(payload["buyer_pools"]),
        "icp_priority_target_count": payload[
            "icp_priority_target_count"
        ],
        "predictive_revenue_enterprise_target_count": payload[
            "predictive_revenue_enterprise_target_count"
        ],
        "icp_campaign_target_company_count": payload[
            "icp_buyer_trigger_intelligence"
        ]["target_company_count_per_campaign"],
        "live_outbound_send": payload["automation"]["live_outbound_send"],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    # Append a distinct optional, non-sending metadata-only reader result.
    # The existing five-minute systemd schedule already owns this process.
    print(json.dumps({"workspace_solar_reply_tracking":
                      refresh_existing_workspace_reply_snapshot()},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
