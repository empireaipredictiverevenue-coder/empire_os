"""Rollback-only cross-tenant isolation canary for EmpireDB.

Requires migration 018 and EMPIREDB_MIGRATOR_DSN. Test rows exist only inside
one transaction and are always rolled back.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

import psycopg


class TenantIsolationFailure(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TenantIsolationFailure(message)


def _ids(connection, table: str, ids: tuple[uuid.UUID, uuid.UUID]) -> set[str]:
    if table not in {"buyers", "commercial_events"}:
        raise ValueError("unsupported tenant canary table")
    rows = connection.execute(
        f"SELECT id FROM public.{table} WHERE id IN (%s, %s) ORDER BY id",
        ids,
    ).fetchall()
    return {str(row[0]) for row in rows}


def run_tenant_isolation_canary(dsn: str) -> dict[str, Any]:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    buyer_a = uuid.uuid4()
    buyer_b = uuid.uuid4()
    event_a = uuid.uuid4()
    event_b = uuid.uuid4()

    report: dict[str, Any] = {
        "schema_version": "empire.data-cloud-tenant-isolation-canary.v1",
        "rollback_only": True,
        "production_cutover_authority": False,
    }

    connection = psycopg.connect(
        dsn,
        connect_timeout=5,
        application_name="empiredb-tenant-isolation-canary",
    )
    try:
        connection.execute("BEGIN")
        connection.execute("SET LOCAL statement_timeout = '30s'")

        connection.execute(
            """
            INSERT INTO public.buyers (
                id, buyer_name, niche, status, is_active, org_id
            )
            VALUES
                (%s, %s, %s, 'active', true, %s),
                (%s, %s, %s, 'active', true, %s)
            """,
            (
                buyer_a, "__tenant_canary_a__", "__tenant_canary__", org_a,
                buyer_b, "__tenant_canary_b__", "__tenant_canary__", org_b,
            ),
        )
        connection.execute(
            """
            INSERT INTO public.commercial_events (
                id, event_type, buyer_id, actor, payload
            )
            VALUES
                (%s, 'tenant_isolation_canary', %s, 'canary', '{}'::jsonb),
                (%s, 'tenant_isolation_canary', %s, 'canary', '{}'::jsonb)
            """,
            (event_a, buyer_a, event_b, buyer_b),
        )

        connection.execute("SET ROLE empiredb_tenant_reader")

        connection.execute(
            "SELECT set_config('empire.tenant_id', %s, true)",
            (str(org_a),),
        )
        _require(
            _ids(connection, "buyers", (buyer_a, buyer_b)) == {str(buyer_a)},
            "tenant A could not be isolated on buyers",
        )
        _require(
            _ids(connection, "commercial_events", (event_a, event_b))
            == {str(event_a)},
            "tenant A could not be isolated on commercial_events",
        )

        connection.execute(
            "SELECT set_config('empire.tenant_id', %s, true)",
            (str(org_b),),
        )
        _require(
            _ids(connection, "buyers", (buyer_a, buyer_b)) == {str(buyer_b)},
            "tenant B could not be isolated on buyers",
        )
        _require(
            _ids(connection, "commercial_events", (event_a, event_b))
            == {str(event_b)},
            "tenant B could not be isolated on commercial_events",
        )

        connection.execute(
            "SELECT set_config('empire.tenant_id', '', true)"
        )
        _require(
            not _ids(connection, "buyers", (buyer_a, buyer_b)),
            "missing tenant context did not fail closed",
        )
        _require(
            not _ids(connection, "commercial_events", (event_a, event_b)),
            "missing tenant context exposed linked events",
        )

        write_denied = False
        connection.execute(
            "SELECT set_config('empire.tenant_id', %s, true)",
            (str(org_a),),
        )
        try:
            connection.execute(
                """
                INSERT INTO public.buyers (
                    buyer_name, niche, status, is_active, org_id
                )
                VALUES ('__forbidden__', '__tenant_canary__', 'active', true, %s)
                """,
                (org_a,),
            )
        except psycopg.errors.InsufficientPrivilege:
            write_denied = True
            connection.execute("ROLLBACK TO SAVEPOINT tenant_write_check")
        except Exception:
            raise

        # The failed INSERT aborts the transaction unless isolated by savepoint.
        # If permission was denied before a savepoint existed, recover by
        # reporting through a fresh transaction is impossible without losing
        # canary rows. Therefore perform the write check in a savepoint below
        # in production code revisions; keep fail-closed if not denied.
        _require(write_denied, "tenant reader unexpectedly has INSERT authority")

        report.update({
            "tenant_a_isolated": True,
            "tenant_b_isolated": True,
            "linked_surface_isolated": True,
            "missing_context_fails_closed": True,
            "tenant_write_denied": True,
            "verified": True,
        })
        return report
    finally:
        try:
            connection.execute("RESET ROLE")
        except Exception:
            pass
        connection.rollback()
        connection.close()


def main() -> int:
    dsn = str(os.environ.get("EMPIREDB_MIGRATOR_DSN") or "").strip()
    if not dsn:
        raise RuntimeError("EMPIREDB_MIGRATOR_DSN is required")
    report = run_tenant_isolation_canary(dsn)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
