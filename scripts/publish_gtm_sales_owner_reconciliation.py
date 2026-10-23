#!/usr/bin/env python3
"""DB-owner-only one-shot read-only reconciliation -> GTM aggregate receipt.

Use original authorised EmpireDB/CRM probes, not a new query or permission.
Never record individual customer data, consent bodies or signed-in sessions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from empire_os.gtm_sales_owner_reconciliation import (
    RECEIPT, SCHEMA, OWNER_SCHEMA, ALL_KEYS, ALLOWED, public_review,
)
from scripts.reconcile_founder_sales_handoff_aggregate_readonly import run

ROOT = Path("/srv/empire_os")


def publish_owner_read(*, root: Path = ROOT) -> dict:
    no_change = {
        "status": "HELD_AUTHORISED_DB_OWNER_REVIEW_REQUIRED",
        "receipt_written": False, "db_mutation": False,
        "crm_mutation": False, "outbound_sent": False,
        "payments_executed": False, "execution_authority": "none",
    }
    # Never use the observer service's root privileges for an automatic source
    # probe. Only the explicit DBA-operated one-shot command invokes this.
    if os.geteuid() != 0 or root != ROOT:
        return no_change
    result = run()
    if (not isinstance(result, dict)
        or result.get("schema_version") != OWNER_SCHEMA
        or result.get("status") not in ALLOWED
        or result.get("read_only") is not True
        or result.get("database_writes") is not False
        or result.get("tenant_binding_changed") is not False
        or result.get("raw_customer_rows_read") is not False
        or result.get("customer_identifiers_disclosed") is not False
        or result.get("outbound_sent") is not False
        or result.get("payment_executed") is not False
        or result.get("founder_crm_delivery_verified") is not False
        or result.get("execution_authority") != "NONE"):
        return {**no_change, "status":"HELD_ORIGINAL_OWNER_RECONCILIATION_INCOMPLETE"}
    packet = {
        "schema_version": SCHEMA,
        "source_schema_version": OWNER_SCHEMA,
        "source_status": result["status"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True, "execution_authority": "none",
    }
    packet.update({k:result.get(k) for k in ALL_KEYS})
    reviewed = public_review(packet, now=datetime.now(timezone.utc))
    if not reviewed["source_and_tenant_aggregate_valid"]:
        return {**no_change,"status":"HELD_ORIGINAL_OWNER_COUNTS_INCONSISTENT"}
    target = root / RECEIPT
    folder = target.parent
    if (folder.is_symlink() or not folder.is_dir()
        or folder.stat().st_uid != 0 or target.is_symlink()):
        return {**no_change,"status":"HELD_OWNER_RECEIPT_DIRECTORY_UNSAFE"}
    fd, tmp = tempfile.mkstemp(prefix=".owner_gtm_", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            os.fchmod(stream.fileno(),0o600)
            json.dump(packet,stream,sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {
        **no_change,
        "status": reviewed["status"],
        "receipt_written": True,
        "canonical_sales_acquisitions": reviewed["canonical_sales_acquisitions"],
        "exact_enquiry_lineage_verified": False,
    }


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-only",required=True,action="store_true")
    parser.add_argument("--write-owner-aggregate",required=True,action="store_true")
    parser.parse_args()
    print(json.dumps(publish_owner_read(),sort_keys=True))


if __name__=="__main__":
    main()
