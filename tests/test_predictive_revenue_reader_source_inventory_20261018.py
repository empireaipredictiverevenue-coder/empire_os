"""Source inventory and passive catalog SQL: no implied DB activation."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.review_predictive_revenue_reader_source_inventory_readonly import (
    review_source, main,
)

SQL = Path(__file__).resolve().parents[1] / (
    "scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql"
)


def _fixture(tmp_path, *, definition=None, source=True):
    migrations = tmp_path / "migrations/empiredb"
    migrations.mkdir(parents=True)
    if definition is not None:
        (migrations / "held_only.sql").write_text(definition)
    if source:
        reader = tmp_path / "empire_os/predictive_revenue_canonical_reader.py"
        reader.parent.mkdir(parents=True)
        reader.write_text(
            "def read_recognized_revenue_event():\n"
            "    return 'read_predictive_revenue_event_v1'\n"
        )
    return tmp_path


def test_readonly_inventory_reports_no_migration_without_claiming_live_absence(tmp_path):
    root = _fixture(tmp_path)
    report = review_source(root)
    assert report["reader_code_present"]
    assert report["status"] == "HOLD_NO_FUNCTION_DDL_IN_LOCAL_MIGRATION_INVENTORY"
    assert report["matching_function_ddl_filenames"] == []
    assert report["live_role_or_function_verified"] is False
    assert report["database_query_executed"] is False
    assert report["event_records_read"] == 0
    assert report["customer_delivery_authorized"] is False


def test_staged_sql_file_never_means_applied_or_verified(tmp_path):
    root = _fixture(
        tmp_path,
        definition="CREATE OR REPLACE FUNCTION public.read_predictive_revenue_event_v1("
                   "event_id uuid, tenant text) RETURNS text LANGUAGE sql AS $$ SELECT '' $$;",
    )
    report = review_source(root)
    assert report["status"] == "SOURCE_DECLARATION_PRESENT_DB_UNVERIFIED"
    assert report["matching_function_ddl_filenames"] == ["held_only.sql"]
    assert report["live_role_or_function_verified"] is False


def test_readonly_flag_required_and_no_unexpected_files(tmp_path,capsys):
    root = _fixture(tmp_path)
    before = sorted(x.as_posix() for x in root.rglob("*"))
    assert main([],root=root) == 2
    assert json.loads(capsys.readouterr().out)["status"] == (
        "HOLD_EXPLICIT_READ_ONLY_REQUIRED"
    )
    assert main(["--read-only"],root=root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"].startswith("HOLD_")
    assert sorted(x.as_posix() for x in root.rglob("*")) == before


def test_missing_reader_and_escaped_symlinks_never_pass(tmp_path):
    root = _fixture(tmp_path, source=False)
    assert review_source(root)["reader_code_present"] is False
    reader = root / "empire_os/predictive_revenue_canonical_reader.py"
    reader.parent.mkdir()
    other = tmp_path / "original.py"
    other.write_text(
        "def read_recognized_revenue_event():\n"
        "    return 'read_predictive_revenue_event_v1'"
    )
    reader.symlink_to(other)
    assert review_source(root)["reader_code_present"] is False


def test_postgres_catalog_probe_has_no_data_mutation_or_event_query():
    sql = SQL.read_text()
    statements = "\n".join(
        line.split("--",1)[0] for line in sql.splitlines()
    ).upper()
    assert "BEGIN READ ONLY;" in statements
    assert statements.strip().endswith("ROLLBACK;")
    for token in (
        "INSERT INTO", "UPDATE PUBLIC.", "DELETE FROM", "CREATE ROLE",
        "ALTER ROLE", "GRANT EXECUTE", "REVOKE", "CREATE FUNCTION",
        "DROP FUNCTION", "SET ROLE", "COPY ", "SELECT * FROM PUBLIC.COMMERCIAL_EVENTS",
    ):
        assert token not in statements
    assert "PG_CATALOG.PG_PROC" in statements
    assert "PG_CATALOG.PG_ROLES" in statements
    assert "PG_CATALOG.ACLEXPLODE" in statements
    assert "HAS_TABLE_PRIVILEGE" in statements
    assert "TO_REGPROCEDURE" in statements
    assert "READ_PREDICTIVE_REVENUE_EVENT_V1(UUID,TEXT)" in statements
    assert "HOLD_EVENT_READER_CATALOG_NOT_PROVEN" in statements
    assert "CATALOG_PREREQUISITES_PRESENT_NOT_EVENT_PROVEN" in statements
    assert "'CUSTOMER_REPORT_RELEASE_AUTHORIZED',FALSE" in statements
    assert "'ROWS_READ_FROM_FINANCIAL_SOURCE_TABLES',0" in statements


def test_live_checkout_source_inventory_never_claims_database_proof():
    report=review_source(Path("/srv/empire_os"))
    assert report["canonical_database"]=="EmpireDB"
    assert report["live_role_or_function_verified"] is False
    assert report["event_records_read"] == 0
    assert report["execution_authority"] == "none"



def test_finance_readiness_reuses_same_repo_source_inventory(tmp_path):
    from datetime import datetime, timezone
    from empire_os.enterprise_finance_evidence_readiness import (
        review_finance_source_readiness,
    )
    fixture=_fixture(tmp_path)
    payload=review_finance_source_readiness(
        fixture,as_of=datetime(2026,10,18,14,0,tzinfo=timezone.utc)
    )
    reader=payload["single_event_reader_repository_prerequisites"]
    assert reader["reader_code_present"] is True
    assert reader["status"]=="HOLD_NO_FUNCTION_DDL_IN_LOCAL_MIGRATION_INVENTORY"
    assert reader["live_role_or_function_verified"] is False
    assert not payload["empiredb_reads_performed"]
    assert not payload["actual_recognised_revenue_independently_verified"]
    assert payload["required_proofs_not_admitted_count"]==7
