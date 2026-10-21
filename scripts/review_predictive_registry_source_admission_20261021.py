"""Review the existing tenant's forecast registry access without DB writes."""
from __future__ import annotations

import argparse
import json
import os

from empire_os.predictive_existing_tenant_registry_receipts import (
    SCHEMA, RegistrySourceHeld, read_existing_tenant_registry_receipts,
)

ENV = "EMPIREDB_TENANT_OUTCOME_READER_DSN"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)

    try:
        output = read_existing_tenant_registry_receipts(
            dsn=os.environ.get(ENV, "")
        )
    except (RegistrySourceHeld, ValueError, TypeError, OSError):
        output = {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": "HELD_ORIGINAL_REGISTRY_ACCESS_UNVERIFIED",
            "existing_reader_registry_source_admitted": False,
            "registry_candidate_count": None,
            "original_forecast_immutable_registration_verified": False,
            "forecast_registered_before_outcome_verified": False,
            "independent_revenue_settlement_verified": False,
            "customer_forecast_eligible": False,
            "database_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(output, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
