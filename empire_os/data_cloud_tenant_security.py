"""Rollback-only cross-tenant isolation canary for EmpireDB.

Tenant identity is derived from empire.tenant_role_bindings for current_user.
The tenant reader has no authority to change its own binding. Canary rows and
temporary bindings exist only inside one transaction and are always rolled back.
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


def _bind_reader(connection, tenant_id: uuid.UUID | None) -> None:
    if tenant_id is None:
        connection.execute(
            "DELETE FROM empire.tenant_role_bindings "
            "WHERE role_name='empiredb_tenant_reader'"
        )
        return
    connection.execute(
        """
        INSERT INTO empire.tenant_role_bindings(
            role_name, tenant_id, active, evidence_ref
        )
        VALUES ('empiredb_tenant_reader', %s, true, 'rollback-canary')
        ON CONFLICT (role_name)
        DO UPDATE SET
            tenant_id=EXCLUDED.tenant_id,
            active=true,
            evidence_ref=EXCLUDED.evidence_ref,
            updated_at=clock_timestamp()
        """,
        (tenant_id,),
    )


def run_tenant_isolation_canary(dsn: str) -> dict[str, Any]:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    buyer_a = uuid.uuid4()
    buyer_b = uuid.uuid4()
    event_a = uuid.uuid4()
    event_b = uuid.uuid4()

    report: dict[str, Any] = {
        "schema_version": "empire.data-cloud-tenant-isolation-canary.v2",
        "identity_source": "trusted_db_role_binding",
        "caller_tenant_guc_trusted": False,
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

        _bind_reader(connection, org_a)
        connection.execute("SET ROLE empiredb_tenant_reader")
        _require(
            _ids(connection, "buyers", (buyer_a, buyer_b)) == {str(buyer_a)},
            "tenant A could not be isolated on buyers",
        )
        _require(
            _ids(connection, "commercial_events", (event_a, event_b))
            == {str(event_a)},
            "tenant A could not be isolated on commercial_events",
        )

        binding_write_denied = False
        connection.execute("SAVEPOINT tenant_binding_write_check")
        try:
            connection.execute(
                """
                UPDATE empire.tenant_role_bindings
                SET tenant_id=%s
                WHERE role_name='empiredb_tenant_reader'
                """,
                (org_b,),
            )
        except psycopg.errors.InsufficientPrivilege:
            binding_write_denied = True
            connection.execute(
                "ROLLBACK TO SAVEPOINT tenant_binding_write_check"
            )
        _require(
            binding_write_denied,
            "tenant reader can change its own trusted tenant binding",
        )

        connection.execute("RESET ROLE")
        _bind_reader(connection, org_b)
        connection.execute("SET ROLE empiredb_tenant_reader")
        _require(
            _ids(connection, "buyers", (buyer_a, buyer_b)) == {str(buyer_b)},
            "tenant B could not be isolated on buyers",
        )
        _require(
            _ids(connection, "commercial_events", (event_a, event_b))
            == {str(event_b)},
            "tenant B could not be isolated on commercial_events",
        )

        connection.execute("RESET ROLE")
        _bind_reader(connection, None)
        connection.execute("SET ROLE empiredb_tenant_reader")
        _require(
            not _ids(connection, "buyers", (buyer_a, buyer_b)),
            "missing trusted tenant binding did not fail closed",
        )
        _require(
            not _ids(connection, "commercial_events", (event_a, event_b)),
            "missing trusted tenant binding exposed linked events",
        )

        write_denied = False
        connection.execute("SAVEPOINT tenant_write_check")
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
        _require(write_denied, "tenant reader unexpectedly has INSERT authority")

        report.update({
            "tenant_a_isolated": True,
            "tenant_b_isolated": True,
            "linked_surface_isolated": True,
            "missing_binding_fails_closed": True,
            "binding_mutation_denied": True,
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
