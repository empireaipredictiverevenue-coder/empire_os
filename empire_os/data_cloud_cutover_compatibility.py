"""Read-only compatibility audit for an EmpireDB canonical cutover.

This audit answers the question that vendor-coupling scans cannot:
will legacy compatibility callers still resolve after the canonical backend is
switched to EmpireDB?

It discovers literal /rest/v1 table and RPC paths from runtime Python, excludes
explicit legacy/recovery/audit boundaries, then verifies:
- every referenced table exists in EmpireDB; and
- every referenced RPC is explicitly mapped by the EmpireDB provider.

No data mutation and no cutover authority.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from empire_os.data_backends.empiredb import _RPC_PARAMS
from empire_os.data_backends.postgres import PostgresConnectionConfig, PostgresConnector


TABLE_RE = re.compile(
    r"""["']?/rest/v1/([A-Za-z_][A-Za-z0-9_]*)(?:\?|["'])"""
)
RPC_RE = re.compile(
    r"""["']?/rest/v1/rpc/([A-Za-z_][A-Za-z0-9_]*)"""
)

ROOTS = ("empire_os", "scripts")
EXCLUDED_PARTS = {
    ".git", ".venv", "__pycache__", "node_modules", "tests", "docs",
    "migrations", "recovery", "toop", "runtime",
}
CLASSIFIED_EXCEPTIONS = {
    "empire_os/activate_idle_leads.py",
    "empire_os/astra_preflight.py",
    "empire_os/data_backends/supabase_legacy.py",
    "empire_os/data_cloud_discovery.py",
    "empire_os/data_cloud_runtime_dependency_inventory.py",
    "empire_os/data_cloud_vendor_coupling_audit.py",
    "empire_os/migrate_prospects.py",
    "empire_os/sb.py",
    "empire_os/supabase_egress_guard.py",
    "empire_os/legacy_permit_recovery.py",
    "scripts/astra_observer.py",
}


def iter_files(root: Path):
    for root_name in ROOTS:
        base = root / root_name
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            relative = str(path.relative_to(root))
            if relative in CLASSIFIED_EXCEPTIONS:
                continue
            yield path


def discover(root: Path) -> tuple[set[str], set[str]]:
    tables: set[str] = set()
    rpcs: set[str] = set()

    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in RPC_RE.finditer(text):
            rpcs.add(match.group(1))
        for match in TABLE_RE.finditer(text):
            name = match.group(1)
            if name != "rpc":
                tables.add(name)

    return tables, rpcs


def empiredb_tables() -> set[str]:
    connector = PostgresConnector(PostgresConnectionConfig.from_env())
    connection = connector._open_connection()
    try:
        rows = connection.execute(
            """
            SELECT tablename
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'public'
            """
        ).fetchall()
        return {str(row[0]) for row in rows}
    finally:
        connection.close()


def main() -> int:
    root = Path.cwd()
    tables, rpcs = discover(root)
    existing_tables = empiredb_tables()
    mapped_rpcs = set(_RPC_PARAMS)

    missing_tables = sorted(tables - existing_tables)
    unmapped_rpcs = sorted(rpcs - mapped_rpcs)

    report = {
        "schema_version": "empire.cutover-compatibility.v1",
        "read_only": True,
        "production_cutover_authority": False,
        "compatibility_tables_referenced": len(tables),
        "compatibility_rpcs_referenced": len(rpcs),
        "missing_empiredb_tables": missing_tables,
        "missing_empiredb_table_count": len(missing_tables),
        "unmapped_empiredb_rpcs": unmapped_rpcs,
        "unmapped_empiredb_rpc_count": len(unmapped_rpcs),
        "verified": not missing_tables and not unmapped_rpcs,
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
