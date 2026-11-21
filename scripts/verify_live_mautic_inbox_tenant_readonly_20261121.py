#!/usr/bin/env python3
"""Production tenant-bound read-only inbox probe. No founder impersonation.

Gets original live CRM service's existing private config + PGPASSFILE and
reuses the original dedicated tenant login through its canonical Postgres
transport, never direct superuser SELECT. Only aggregate counts and static
security flags are returned. The separately authenticated browser/login
test is NOT satisfied by this server-side probe.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from uuid import UUID

from empire_os.mautic_crm_review_api import INBOX_SELECT_SQL
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository


def run() -> dict[str, object]:
    output: dict[str, object] = {
        "schema_version": "empire.mautic.live_tenant_reader_probe.v1",
        "status": "HELD_OR_UNAVAILABLE",
        "mode": "READ_ONLY",
        "database_writes": False,
        "outbound_sent": False,
        "founder_bearer_session_authenticated": False,
        "customer_identifiers_disclosed": False,
    }
    if os.geteuid() != 0:
        return output
    try:
        pid = int(subprocess.run(
            ["systemctl", "show", "empire-revenue-crm-pilot.service",
             "--value", "-p", "MainPID"], capture_output=True,
            check=True, text=True, timeout=4,
        ).stdout.strip())
        if pid < 2:
            return output
        values = dict(
            entry.split(b"=", 1)
            for entry in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            if b"=" in entry
        )
        config_file = values.get(b"EMPIRE_CRM_PILOT_CONFIG_FILE")
        passfile = values.get(b"PGPASSFILE")
        if not config_file or not passfile:
            return output
        configuration = json.loads(Path(config_file.decode()).read_text())
        tenant_dsns = configuration.get("tenant_dsns", {})
        if not isinstance(tenant_dsns, dict) or len(tenant_dsns) != 1:
            return output
        tenant, dsn = next(iter(tenant_dsns.items()))
        if str(UUID(tenant)) != tenant:
            return output
        previous = os.environ.get("PGPASSFILE")
        try:
            os.environ["PGPASSFILE"] = passfile.decode()
            # This transport uses SET TRANSACTION READ ONLY, SET LOCAL ROLE
            # empire_revenue_crm_reader and session-user tenant enforcement.
            reader = PostgresRevenueCrmRepository(dsn, tenant_id=tenant)
            records = reader._fetch_all(INBOX_SELECT_SQL, (tenant, 5))
            if not isinstance(records, list):
                return output
            if any(str(row.get("tenant_id")) != tenant for row in records):
                return output
            if len(records) > 5:
                return output
            return {
                **output,
                "status": "ACTUAL_TENANT_BOUND_READER_PASS",
                "canonical_authenticated_tenant_db_role_read": True,
                "review_rows_returned": len(records),
                "founder_bearer_session_authenticated": False,
            }
        finally:
            if previous is None:
                os.environ.pop("PGPASSFILE", None)
            else:
                os.environ["PGPASSFILE"] = previous
    except Exception:
        return output

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
