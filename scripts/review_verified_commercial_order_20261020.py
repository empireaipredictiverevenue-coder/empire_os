#!/usr/bin/env python3
"""Original owner order proof review, explicit-tenant, read-only transaction.

No buyer discovery, global database sweep, prospect lookup, writes, sends,
tenant inference or command-line credentials. The original owner controls the
canonical reader and row-level access. Safe even while owner reader is pending.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from empire_os.authenticated_commercial_outcome_intelligence import (
    _uuid, MAX_ORDERS, inspect_canonical_order_outcomes,
)
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository
from empire_os.canonical_order_reader_release_integrity import (
    inspect_canonical_reader_release_integrity,
)
from empire_os.commercial_order_tenant_session import (
    TenantOrderSessionHeld, prove_exact_tenant_readonly_session,
)

SCHEMA = "empire.commercial.verified_order_operator.v1"


@contextmanager
def _canonical_read_only_repository(dsn: str, *, tenant_id: str):
    """Tenant-proven original read-only DB transaction; rolls back on exit."""
    from empire_os.canonical_data_gateway import CanonicalDataGateway
    from empire_os.data_backends.empiredb import EmpireDbProvider
    from empire_os.data_backends.postgres import PostgresConnectionConfig, PostgresConnector

    provider = EmpireDbProvider(PostgresConnector(PostgresConnectionConfig(
        dsn=dsn, application_name="empire-commercial-outcome-observe-only",
    )))
    with provider.read_only_snapshot() as source:
        prove_exact_tenant_readonly_session(source, tenant_id=tenant_id)
        yield ExecutionBusDataRepository(CanonicalDataGateway(source))


def review_explicit_order_request(
    *,
    repository: ExecutionBusDataRepository,
    tenant_id: str,
    order_ids: list[str],
    now: datetime,
    repo_root: Path,
) -> dict:
    """Source-validated data read using exactly the requested canonical IDs."""
    report = inspect_canonical_order_outcomes(
        repository=repository,
        tenant_id=tenant_id,
        exact_order_ids=order_ids,
        repo_root=str(repo_root),
        now=now,
    )
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": report["status"],
        "original_order_proof": report,
        "original_prediction_provenance_checked": False,
        "financial_or_model_optimisation_executed": False,
        "owner_handoff_required_for_prediction": True,
        "operator_supplied_exact_canonical_scope": True,
        "no_customer_identifiers_emitted": True,
        "outbound_authorized": False,
        "payment_execution": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exact canonical tenant/order proof; READ ONLY, no discovery"
    )
    parser.add_argument("--read-only", action="store_true", required=True)
    parser.add_argument("--tenant-id", required=True, help="authorised canonical tenant UUID")
    parser.add_argument("--order-id", action="append", required=True,
                        help="exact known original fulfilment-order UUID (up to 20)")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    # Fail before any connection, without reflecting sensitive supplied IDs.
    try:
        tenant = _uuid(args.tenant_id)
        if len(args.order_id) > MAX_ORDERS:
            raise ValueError("over order bound")
        orders = [_uuid(x) for x in args.order_id]
        if len(set(orders)) != len(orders):
            raise ValueError("duplicate canonical order")
        root = Path(args.repo_root).resolve(strict=True)
    except (ValueError, OSError):
        print(json.dumps({"schema_version": SCHEMA,
                          "status": "INVALID_OR_UNAUTHORIZED_REQUEST_SCOPE",
                          "execution_authority": "none"}))
        return 2
    release = inspect_canonical_reader_release_integrity(root)
    if release["status"] != "COMMITTED_READER_PRESENT_OWNER_APPROVAL_REQUIRED":
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": (
                "CANONICAL_OWNER_READER_NOT_DEPLOYED"
                if release["status"] == "VERIFIED_ORDER_READER_NOT_COMMITTED"
                else "ORIGINAL_OWNER_READER_COMMIT_INTEGRITY_HOLD"
            ),
            "original_owner_release_integrity": release["status"],
            "next_existing_owner": "execution_bus_data_repository",
            "verified_financial_results": None,
            "outbound_authorized": False,
            "database_writes": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 0
    # Never accept the broad application data-cloud DSN as order-read authority.
    # This MUST be a dedicated tenant-bound nonprivileged login; in-transaction
    # role/tenant/ACL/RLS checks run before the first commercial SELECT.
    dsn = str(os.environ.get("EMPIRE_COMMERCIAL_OUTCOME_TENANT_DSN") or "").strip()
    if not dsn:
        print(json.dumps({"schema_version": SCHEMA,
                          "status": "RESTRICTED_CANONICAL_CONNECTION_UNAVAILABLE",
                          "execution_authority": "none"}))
        return 2
    try:
        with _canonical_read_only_repository(dsn, tenant_id=tenant) as owner:
            report = review_explicit_order_request(
                repository=owner, tenant_id=tenant, order_ids=orders,
                repo_root=root, now=datetime.now(timezone.utc),
            )
    except TenantOrderSessionHeld as exc:
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": str(exc),
            "outbound_authorized": False, "database_writes": False,
            "execution_authority": "none",
        }))
        return 2
    except Exception:
        # Original DB errors can contain tenant identifiers, SQL or credentials.
        # No raw exception, DSN or parameter is printed.
        print(json.dumps({
            "schema_version": SCHEMA,
            "status": "CANONICAL_ORDER_OWNER_READ_FAILED_CLOSED",
            "outbound_authorized": False, "database_writes": False,
            "execution_authority": "none",
        }))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
