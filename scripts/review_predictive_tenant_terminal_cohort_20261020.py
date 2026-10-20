"""Read bounded canonical EmpireDB outcome candidates for the authenticated tenant.

Runs only when an existing dedicated tenant reader credential is configured.
Candidate counts do not become forecasts, training labels or realized revenue.
"""
from __future__ import annotations

import argparse
import json
import os

from empire_os.predictive_tenant_terminal_cohort_reader import (
    SCHEMA, TenantCohortSourceHold, read_tenant_terminal_candidates,
)

DSN_ENV = "EMPIREDB_TENANT_OUTCOME_READER_DSN"


def held(status: str) -> dict:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "original_rows_read_in_memory_only": False,
        "source_rows_exported_to_scientific_training": False,
        "customer_forecast_eligible": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps(held("HELD_EXPLICIT_READ_ONLY_REQUIRED")))
        return 2
    dsn = os.environ.get(DSN_ENV, "")
    if not dsn:
        result = held("HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING")
    else:
        try:
            result = read_tenant_terminal_candidates(dsn=dsn)
        except (TenantCohortSourceHold, ValueError, TypeError, OSError):
            result = held("HELD_ORIGINAL_TENANT_TERMINAL_COHORT_UNVERIFIED")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
