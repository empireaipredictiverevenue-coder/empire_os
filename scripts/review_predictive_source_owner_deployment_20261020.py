"""Read-only production writer vs immutable candidate readiness."""
from __future__ import annotations
import argparse
import json
from empire_os.predictive_source_owner_deployment_preflight import (
    SCHEMA, SourceDeploymentHold, review_original_source_deployment,
)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", required=True, action="store_true")
    p.parse_args(argv)
    try:
        report = review_original_source_deployment()
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, UnicodeError, SourceDeploymentHold, TypeError, ValueError):
        print(json.dumps({
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "ORIGINAL_SOURCE_DEPLOYMENT_INVENTORY_HELD",
            "source_bytes_equal": False,
            "original_tenant_reader_role_verified": False,
            "customer_forecast_eligible": False,
            "database_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
