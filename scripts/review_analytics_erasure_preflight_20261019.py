#!/usr/bin/env python3
"""Read-only source gate for HELD EmpireDB Analytics055 erasure migration.

Never connects to a database, runs a migration, activates a role or
treats this source candidate as an approved privacy/retention policy.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/"migrations/empiredb/055_first_party_analytics_erasure_held.sql"
PREDECESSOR=ROOT/"migrations/empiredb/054_first_party_analytics_ledger_held.sql"
EXPECTED={
    CURRENT.name:"a49f84cb2b4875df23f4b499de721d750e99066c5d0f10f2b112a0e34be9dd76",
    PREDECESSOR.name:"3a7ae044eba0e30fdaa532bcda1208668712293dfa2a61e3a483505c0de64113",
}

def safe_hash(path:Path)->str|None:
    try:
        if path.is_symlink() or not path.is_file() or not 5000<=path.stat().st_size<=20000:
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def audit(*, current:Path=CURRENT, predecessor:Path=PREDECESSOR)->dict:
    parent=safe_hash(predecessor)==EXPECTED[PREDECESSOR.name]
    source=safe_hash(current)==EXPECTED[CURRENT.name]
    ready=bool(parent and source)
    return {
        "schema_version":"empire.analytics.erasure_retention_preflight.v1",
        "status":("ANALYTICS055_ERASURE_SOURCE_PREPARED_PRIVILEGED_APPROVAL_HELD"
                  if ready else "HELD_ANALYTICS055_MIGRATION_SOURCE_DRIFT"),
        "mode":"READ_ONLY",
        "canonical_database":"EmpireDB PostgreSQL",
        "analytics054_parent_source_verified":parent,
        "analytics055_erasure_source_verified":source,
        "isolated_postgresql_tests_separate":True,
        "real_production_analytics054_applied_verified":False,
        "real_production_analytics055_applied_verified":False,
        "maintenance_login_provisioned_by_this_migration":False,
        "runtime_execute_grants_by_this_migration":False,
        "retention_interval_approved":False,
        "consent_ui_and_lawful_basis_verified":False,
        "data_subject_erasure_workflow_verified":False,
        "privacy_recovery_and_legal_hold_review_complete":False,
        "public_collector_active":False,
        "visitor_sessions_verified":False,
        "realised_revenue_verified":False,
        "service_restarted":False,
        "database_connection_opened":False,
        "database_writes":False,
        "website_changed":False,
        "execution_authority":"NONE",
        "next_gate":"FOUNDER_DBA_AND_PRIVACY_RETENTION_ERASURE_APPROVAL",
    }


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.parse_args(argv)
    result=audit()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"].startswith("ANALYTICS055_ERASURE_SOURCE_PREPARED") else 2

if __name__=="__main__":
    raise SystemExit(main())
