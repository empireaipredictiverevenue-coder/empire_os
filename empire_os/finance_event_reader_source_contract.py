"""Repository-only read model for the *existing* EmpireDB event reader contract.

A migration/source-code reference is never a running database role, an
audited event, a settlement, or a customer entitlement. No DB credentials or
connections are used.
"""
from __future__ import annotations

import re
from pathlib import Path

READER = "empire_os/predictive_revenue_canonical_reader.py"
SQL_DIR = "migrations/empiredb"
DEFINITION = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+"
    r"(?:public\.)?read_predictive_revenue_event_v1\s*\(",
    re.IGNORECASE,
)


def review_source(root: Path) -> dict:
    root = Path(root).resolve()
    reader = root / READER
    migrations = root / SQL_DIR
    reader_found = False
    defined = []
    try:
        if reader.is_file() and not reader.is_symlink() and reader.stat().st_size < 60_000:
            source = reader.read_text("utf-8")
            reader_found = ("def read_recognized_revenue_event(" in source
                            and "read_predictive_revenue_event_v1" in source)
        if migrations.is_dir() and not migrations.is_symlink():
            for file in sorted(migrations.glob("*.sql"))[:200]:
                if file.is_symlink() or not file.is_file() or file.stat().st_size > 1_000_000:
                    continue
                if DEFINITION.search(file.read_text("utf-8")):
                    defined.append(file.name)
    except (OSError, UnicodeError):
        reader_found = False
        defined = []
    return {
        "schema_version": "empire.revenue_event_source_inventory.v1",
        "status": ("SOURCE_DECLARATION_PRESENT_DB_UNVERIFIED" if defined else
                   "HOLD_NO_FUNCTION_DDL_IN_LOCAL_MIGRATION_INVENTORY"),
        "canonical_database": "EmpireDB",
        "reader_code_present": reader_found,
        "expected_function": "public.read_predictive_revenue_event_v1(uuid,text)",
        "matching_function_ddl_filenames": defined,
        "local_artifact_is_live_function_evidence": False,
        "live_role_or_function_verified": False,
        "customer_finance_evidence_verified": False,
        "event_records_read": 0,
        "customer_delivery_authorized": False,
        "database_query_executed": False,
        "mode": "OBSERVE",
        "execution_authority": "none",
    }
