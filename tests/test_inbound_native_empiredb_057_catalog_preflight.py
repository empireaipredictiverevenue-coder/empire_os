"""Deterministic catalog-only release gate for held EmpireDB 057."""
import json
import subprocess
import sys

import pytest
from scripts.inspect_inbound_native_empiredb_057_readonly import (
    TABLES, classify,
)


def catalog(**updates):
    source = {
        "database_identity": ["empiredb", "postgres", False],
        "migration_role": [False, False, False, False, False],
        "migrator_can_create_public": True,
        "crm_membership": ["empiredb_migrator", True, "r"],
        "crm_resolvers": [True, True],
        "existing_inbound_tables": [],
        "catalog_source_checked": True,
    }
    source.update(updates)
    return source


def test_all_verified_catalog_facts_are_only_ready_for_review():
    summary = classify(catalog())
    assert summary["status"] == "READY_FOR_INDEPENDENT_DBA_MIGRATION_REVIEW"
    assert summary["database_migration_executed"] is False
    assert summary["customer_calendar_enabled"] is False
    assert summary["revenue_verified"] is False
    assert summary["requires_explicit_dba_and_founder_approval"] is True
    assert all(summary["gates"].values())


@pytest.mark.parametrize("changed", [
    {"database_identity": ["otherdb", "postgres", False]},
    {"database_identity": ["empiredb", "some_login", False]},
    {"database_identity": ["empiredb", "postgres", True]},
    {"migration_role": [True, False, False, False, False]},
    {"migration_role": [False, False, True, False, False]},
    {"migration_role": None},
    {"migrator_can_create_public": False},
    {"crm_membership": ["wrong_owner", True, "r"]},
    {"crm_membership": ["empiredb_migrator", False, "r"]},
    {"crm_membership": None},
    {"crm_resolvers": [True, False]},
    {"crm_resolvers": [False, True]},
    {"existing_inbound_tables": ["inbound_recovery_tenants"]},
    {"existing_inbound_tables": None},
    {"catalog_source_checked": False},
])
def test_catalog_mismatch_always_held(changed):
    report = classify(catalog(**changed))
    assert report["status"] == "HELD_NATIVE_EMPIREDB_057_RELEASE_GATES"
    assert not all(report["gates"].values())
    assert report["database_migration_executed"] is False


def test_redacted_results_do_not_expose_names_or_identifier_values():
    report = classify(catalog(
        existing_inbound_tables=["inbound_recovery_tenants"],
    ))
    text = json.dumps(report)
    assert "inbound_recovery_tenants" not in text
    assert "postgres" not in text
    assert "empiredb_migrator" not in text
    assert report["existing_057_table_count"] == 1
    assert len(TABLES) == 10


def test_cli_requires_exact_flags_and_never_uses_service_credentials():
    args = [sys.executable, "-B", "-m",
            "scripts.inspect_inbound_native_empiredb_057_readonly"]
    process = subprocess.run(args, capture_output=True, text=True)
    assert process.returncode == 3
    assert json.loads(process.stdout)["status"] == "EXACT_READ_ONLY_FLAGS_REQUIRED"
