#!/usr/bin/env python3
"""Recover only the failed portfolio-optimizer coding lane."""
from __future__ import annotations

import json
from pathlib import Path

from empire_os.execution_plane_dispatcher import dispatch_execution_request
from empire_os.predictive_coding_team import predictive_cloud_coding_team_requests


ROOT = Path("/srv/empire_os")
RECOVERY_IDS = {
    "predictive-action-portfolio-design-v1",
    "predictive-action-portfolio-implementation-v2",
}


def main() -> int:
    requests = [
        request
        for request in predictive_cloud_coding_team_requests()
        if request.request_id in RECOVERY_IDS
    ]
    results = [
        dispatch_execution_request(
            ROOT,
            request,
            execute_pi=False,
        )
        for request in requests
    ]
    print(json.dumps({
        "schema_version": "empire.coding_team_recovery.v1",
        "recovery": "predictive_action_portfolio_optimizer",
        "request_count": len(results),
        "results": results,
        "external_execution_performed": False,
        "production_deploy": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
