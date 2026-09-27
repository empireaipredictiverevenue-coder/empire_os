#!/usr/bin/env python3
"""Queue the Predictive Cloud / AGI / Quantum coding-team batch."""
from __future__ import annotations

import json
from pathlib import Path

from empire_os.execution_plane_dispatcher import dispatch_execution_request
from empire_os.predictive_coding_team import predictive_cloud_coding_team_requests


ROOT = Path("/srv/empire_os")


def main() -> int:
    results = [
        dispatch_execution_request(
            ROOT,
            request,
            execute_pi=False,
        )
        for request in predictive_cloud_coding_team_requests()
    ]
    print(json.dumps({
        "schema_version": "empire.coding_team_batch.v1",
        "batch": "predictive_cloud_agi_quantum",
        "request_count": len(results),
        "results": results,
        "external_execution_performed": False,
        "production_deploy": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
