"""Read-only pg_catalog preflight: original Predictive Cloud 066 role and object gates.

Operator-only inspection; no DDL, rights grants, credentials, data reads,
source admissions, service modification or migration. Prints only booleans.
"""
from __future__ import annotations

import json
import subprocess

SQL = """
SELECT
  (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolname =
   'empire_predictive_rights_reader') AS reader_roles,
  (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolname =
   'empire_predictive_rights_login') AS login_roles,
  (SELECT COUNT(*) FROM pg_catalog.pg_roles WHERE rolname =
   'empiredb_migrator') AS migration_owner_roles,
  pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held')
     IS NOT NULL AS candidate_rights_table_exists,
  pg_catalog.to_regclass('public.empire_predictive_source_revocations_held')
     IS NOT NULL AS revocations_table_exists,
  pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)')
     IS NOT NULL AS source_rights_reader_function_exists;
"""
READ_ONLY = (
    "sudo", "-n", "runuser", "-u", "postgres", "--",
    "psql", "-XAt", "-w", "-v", "ON_ERROR_STOP=1",
    "-d", "empiredb", "-c", SQL,
)


def inspect() -> dict[str, object]:
    result = subprocess.run(
        READ_ONLY, capture_output=True, text=True,
        timeout=8, check=False,
    )
    if result.returncode != 0:
        return {"status": "UNAVAILABLE_READ_ONLY", "production_changes": False,
                "existing_owner_review_required": True}
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise RuntimeError("unexpected_catalog_cardinality")
    fields = rows[0].split("|")
    if (len(fields) != 6 or any(value not in ("0", "1", "t", "f")
                              for value in fields)):
        raise RuntimeError("unexpected_catalog_response")
    return {
        "status": "READ_ONLY_CATALOG_OBSERVED",
        "dedicated_reader_capability_present": fields[0] == "1",
        "dedicated_restricted_login_present": fields[1] == "1",
        "migration_owner_role_present": fields[2] == "1",
        "candidate_rights_table_present": fields[3] == "t",
        "revocation_table_present": fields[4] == "t",
        "source_rights_function_present": fields[5] == "t",
        "real_source_licence_verified_by_this": False,
        "tenant_source_admitted": False,
        "production_changes": False,
        "existing_owner_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
