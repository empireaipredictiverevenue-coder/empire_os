#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

from empire_os.predictive_cloud_materializer import (
    refresh_predictive_cloud_materializers,
)
from empire_os.predictive_cloud_status import (
    refresh_predictive_cloud_status,
)
from empire_os.optimization_status import refresh_optimization_status


ROOT = Path("/srv/empire_os")


def main() -> int:
    materialized = (
        refresh_predictive_cloud_materializers(
            ROOT
        )
    )

    # Refresh the existing, local-only optimization capability inventory.
    # This is status evidence, NOT a solver run or QPU invocation.
    optimization = refresh_optimization_status(ROOT)
    assert optimization["external_qpu_called"] is False
    assert optimization["third_party_runtime_allowed"] is False
    assert optimization["automatic_production_routing"] is False
    assert optimization["execution_authority"] == "none"

    status = refresh_predictive_cloud_status(
        ROOT
    )

    print(
        json.dumps(
            {
                "materializer": materialized,
                "optimization_fabric": {
                    "status": optimization.get("status"),
                    "external_qpu_called": False,
                    "execution_authority": "none",
                },
                "predictive_cloud": {
                    "component_count": (
                        status.get("component_count")
                    ),
                    "available_component_count": (
                        status.get(
                            "available_component_count"
                        )
                    ),
                    "unavailable_components": (
                        status.get(
                            "unavailable_components"
                        )
                    ),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
