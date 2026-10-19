#!/usr/bin/env python3
"""One-shot, read-only source integrity audit of HELD Analytics054 migration.

Does not connect to ANY PostgreSQL server or read service credentials.
The isolated PostgreSQL 18 fixture test is a SEPARATE intentional step;
source presence is not evidence a production schema has been activated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "empire.analytics.ledger_schema_preflight.v1"
MIGRATION = (Path(__file__).resolve().parents[1]
             /"migrations/empiredb/054_first_party_analytics_ledger_held.sql")
PINNED_SHA256 = "3a7ae044eba0e30fdaa532bcda1208668712293dfa2a61e3a483505c0de64113"
MAX_BYTES = 20_000


def audit(path: Path = MIGRATION) -> dict[str, object]:
    valid=False
    try:
        if (not path.is_symlink() and path.is_file()
                and 5_000 < path.stat().st_size <= MAX_BYTES):
            valid=hashlib.sha256(path.read_bytes()).hexdigest()==PINNED_SHA256
    except OSError:
        valid=False
    return {
        "schema_version":SCHEMA,
        "status":("ANALYTICS054_SCHEMA_STAGED_FOUNDER_DB_APPROVAL_REQUIRED"
                  if valid else "HELD_ANALYTICS054_SCHEMA_SOURCE_CHANGED"),
        "source":"additive_empiredb_analytics_054_schema",
        "mode":"READ_ONLY",
        "migration_source_integrity_verified":valid,
        "isolated_pg18_database_tests_are_separate":True,
        "canonical_database":"EmpireDB PostgreSQL",
        "migration_applied_to_production_verified":False,
        "schema_activation_authorised":False,
        "runtime_ingest_role_granted":False,
        "public_collector_active":False,
        "website_analytics_consent_verified":False,
        "tenant_authority_live_verified":False,
        "data_retention_and_erasure_policy_approved":False,
        "real_visitor_sessions_verified":False,
        "crm_attribution_verified":False,
        "realised_revenue_verified":False,
        "database_connections_opened":False,
        "database_writes":False,
        "services_restarted":False,
        "public_website_changed":False,
        "execution_authority":"NONE",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args(argv)
    report=audit()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["migration_source_integrity_verified"] else 2


if __name__=="__main__":
    raise SystemExit(main())
