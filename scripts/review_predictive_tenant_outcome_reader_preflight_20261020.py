"""Read-only authenticated EmpireDB tenant reader policy inventory.

Requires a dedicated least-privilege login provided in one fixed environment
variable. No root/postgres fallback; never logs DSN or tenant identity.
"""
from __future__ import annotations

import argparse
import json
import os

from empire_os.predictive_tenant_outcome_reader_preflight import (
    SCHEMA, TenantEvidencePolicyHold, review_tenant_outcome_reader_policy,
)

DSN_ENV = "EMPIREDB_TENANT_OUTCOME_READER_DSN"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.parse_args(argv)
    dsn = os.environ.get(DSN_ENV, "")
    if not dsn:
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": "HELD_DEDICATED_TENANT_OUTCOME_READER_CREDENTIAL_MISSING",
            "mode": "OBSERVE",
            "tenant_safe_data_reader_activated": False,
            "customer_forecast_eligible": False,
            "database_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 0
    try:
        report = review_tenant_outcome_reader_policy(dsn=dsn)
    except (TenantEvidencePolicyHold, OSError, TypeError, ValueError):
        report = {
            "schema_version": SCHEMA,
            "status": "HELD_TENANT_OUTCOME_READER_POLICY_UNVERIFIED",
            "mode": "OBSERVE",
            "tenant_safe_data_reader_activated": False,
            "customer_forecast_eligible": False,
            "database_writes": False,
            "execution_authority": "none",
        }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
