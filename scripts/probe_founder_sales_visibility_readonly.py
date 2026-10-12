"""One-hit, aggregate-only founder CRM sales-enquiry visibility check.

Use only the existing Ubuntu-owned, least-privilege CRM reader login. This
never reads private customer rows into Python, never queries cross-tenant source
tables, and does not issue any lead ingest or commercial/CRM write.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import tempfile
from typing import Callable

from scripts import diagnose_crm_committed_login_sessions as diagnostic
from scripts.repair_crm_login_passfile_lookup import (
    DIR, PASSFILE, ROLES, inspect, patched,
)

SCHEMA = "empire.founder.sales_crm_visibility_readonly.v1"
SALES_COUNT_SQL = """BEGIN READ ONLY;
SET LOCAL statement_timeout='8000ms';
SET LOCAL ROLE empire_revenue_crm_reader;
SELECT
  count(*) FILTER (WHERE niche LIKE 'commercial_sales:%'),
  count(*) FILTER (WHERE niche LIKE 'predictive_revenue:%'),
  count(*)
FROM public.revenue_crm_prospects
WHERE tenant_id=public.empire_current_tenant_id();
ROLLBACK;"""


def parse_aggregate(rc: int, stdout: str) -> dict[str, int] | None:
    if rc != 0:
        return None
    lines = [row.strip() for row in stdout.splitlines() if "|" in row]
    if len(lines) != 1:
        return None
    parts = lines[0].split("|")
    if len(parts) != 3 or any(not p.isdecimal() for p in parts):
        return None
    commercial, predictive, total = map(int, parts)
    if not 0 <= commercial <= total or not 0 <= predictive <= total:
        return None
    if commercial + predictive > total:
        return None
    return {
        "visible_commercial_sales_prospects": commercial,
        "visible_predictive_revenue_prospects": predictive,
        "visible_total_prospects": total,
    }


def eligible_private_passfile() -> bytes:
    uid = pwd.getpwnam("ubuntu").pw_uid
    if os.geteuid() != uid:
        raise ValueError("DEDICATED_SERVICE_ACCOUNT_REQUIRED")
    if DIR.is_symlink() or PASSFILE.is_symlink() or not DIR.is_dir() or not PASSFILE.is_file():
        raise ValueError("PRIVATE_CRM_CREDENTIAL_FILE_UNAVAILABLE")
    if (DIR.stat().st_uid != uid or PASSFILE.stat().st_uid != uid
            or stat.S_IMODE(DIR.stat().st_mode) != 0o700
            or stat.S_IMODE(PASSFILE.stat().st_mode) != 0o600):
        raise ValueError("PRIVATE_CRM_CREDENTIAL_PERMISSIONS_UNSAFE")
    payload = PASSFILE.read_bytes()
    state = inspect(payload)
    if state not in ("ORIGINAL_THREE_ROWS", "REPAIRED_SIX_ROWS"):
        raise ValueError("UNEXPECTED_PRIVATE_CRM_CREDENTIAL_FORMAT")
    return patched(payload) if state == "ORIGINAL_THREE_ROWS" else payload


def classify(
    *, rc: int, output: str, db_error: str,
) -> dict:
    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "read_only": True,
        "raw_customer_rows_read": False,
        "tenant_binding_mutated": False,
        "prospect_ingest_performed": False,
        "outbound_authorized": False,
        "payment_authorized": False,
        "execution_authority": "NONE",
        "canonical_global_intake_count_proven": False,
        "website_to_founder_visibility_proven": False,
    }
    counts = parse_aggregate(rc, output)
    if counts is None:
        # Do not propagate even sanitized driver text into external evidence.
        result.update(
            status="UNVERIFIED",
            reason_code="DEDICATED_TENANT_CRM_AGGREGATE_UNAVAILABLE",
        )
        return result
    result.update(counts)
    result["status"] = (
        "TENANT_VISIBLE_SALES_PROSPECTS_PRESENT"
        if (counts["visible_commercial_sales_prospects"]
            or counts["visible_predictive_revenue_prospects"])
        else "NO_TENANT_VISIBLE_SALES_PROSPECTS"
    )
    # Even a positive count does not prove it came from THIS website form;
    # authenticated underlying acquisition/event provenance is still needed.
    result["reason_code"] = "CANONICAL_SOURCE_RECEIPTS_NOT_CHECKED"
    return result


def run(
    *, read_private: Callable[[], bytes] = eligible_private_passfile,
    query: Callable = diagnostic.psql,
    temporary_directory: Path = DIR,
) -> dict:
    try:
        secret = read_private()
    except (OSError, ValueError, TypeError):
        return classify(rc=1, output="", db_error="")
    # Temporary compatible host aliases only; never change canonical pgpass.
    fd, name = tempfile.mkstemp(prefix=".crm-sales-visibility-", dir=temporary_directory)
    try:
        with os.fdopen(fd, "wb") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(secret)
            file.flush()
            os.fsync(file.fileno())
        rc, stdout, error = query(ROLES[2], SALES_COUNT_SQL, Path(name))
        return classify(rc=rc, output=stdout, db_error=error)
    except (OSError, ValueError, TypeError):
        return classify(rc=1, output="", db_error="")
    finally:
        os.unlink(name)


def main() -> int:
    result = run()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] != "UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
