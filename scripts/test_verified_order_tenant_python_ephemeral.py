#!/usr/bin/env python3
"""Integration test: actual original Postgres read-only provider with tenant RLS.

ONLY for the pg_virtualenv PostgreSQL 18 synthetic empiredb DB.
"""
from __future__ import annotations

import os
from uuid import UUID

from empire_os.data_query import DataFilter
from empire_os.commercial_order_tenant_session import TenantOrderSessionHeld
from scripts.review_verified_commercial_order_20261020 import _canonical_read_only_repository


def main() -> int:
    if (
        os.environ.get("PGPORT") in (None, "", "5432")
        or os.environ.get("PGHOST") != "localhost"
        or os.environ.get("PGUSER") != "order_fixture_a"
        or os.environ.get("ORDER056_EPHEMERAL_FIXTURE") != "YES"
    ):
        raise RuntimeError("ORDER056_EPHEMERAL_ENVIRONMENT_REQUIRED")
    dsn = (
        f"dbname=empiredb host=localhost "
        f"port={int(os.environ['PGPORT'])} user=order_fixture_a"
    )
    tenant_a = "10000000-0000-4000-8000-000000000001"
    tenant_b = "20000000-0000-4000-8000-000000000002"
    with _canonical_read_only_repository(dsn, tenant_id=tenant_a) as repo:
        rows = repo._gateway.query("bsc_payment_evidence", "id", limit=5)
        assert len(rows) == 1
        other = repo._gateway.query("commercial_outcomes", "id",
            filters=(DataFilter.eq("id", "80000000-0000-4000-8000-000000000008"),),
            limit=1)
        assert not other
    try:
        with _canonical_read_only_repository(dsn, tenant_id=tenant_b):
            raise AssertionError("cross-tenant session was accepted")
    except TenantOrderSessionHeld as exc:
        assert str(exc) == "TENANT_READER_ACL_OR_RLS_HOLD"
    print("ORDER056_PYTHON_TENANT_SESSION_RLS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
