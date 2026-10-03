"""Read-only EmpireDB readiness probe for outbound deliverability persistence."""
from __future__ import annotations

from typing import Any, Callable


REQUIRED_TABLES = (
    "public.outbound_deliverability_observations",
    "public.outbound_ringleader_decisions",
    "public.outbound_sender_pool_observations",
    "public.outbound_provider_policy_snapshots",
    "public.outbound_reputation_economic_events",
    "public.outbound_contact_pressure_events",
    "public.outbound_policy_manifests",
    "public.outbound_policy_shadow_runs",
    "public.outbound_transports",
    "public.outbound_domains",
    "public.outbound_mailboxes",
    "public.outbound_sender_pools",
    "public.outbound_pool_members",
    "public.outbound_capacity_ledger",
    "public.outbound_seed_mailboxes",
    "public.outbound_source_reputation_events",
    "public.outbound_source_reputation_snapshots",
    "public.outbound_content_family_events",
    "public.outbound_content_family_snapshots",
    "public.outbound_claim_verification_events",
    "public.outbound_fleet_readiness_certificates",
    "public.outbound_telemetry_heartbeats",
    "public.outbound_telemetry_sla_snapshots",
)

REQUIRED_COLUMNS = {
    "public.outbound_capacity_ledger": (
        "reservation_key",
        "idempotency_key",
        "lease_expires_at",
    ),
    "public.outbound_contact_pressure_events": (
        "parent_company_key",
        "corridor_key",
        "event_kind",
    ),
}

REQUIRED_ROLES = (
    "empire_outbound_deliverability_reader",
    "empire_outbound_deliverability_writer",
)


class EmpireDBActivationProbeError(RuntimeError):
    pass


def probe_empiredb_deliverability(
    dsn: str,
    *,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    connection_string = str(dsn or "").strip()
    if not connection_string:
        raise EmpireDBActivationProbeError("empiredb_probe_dsn_required")

    if connect_factory is None:
        try:
            import psycopg
        except ImportError as exc:
            raise EmpireDBActivationProbeError(
                "psycopg_required_for_empiredb_probe"
            ) from exc
        connect_factory = psycopg.connect

    try:
        with connect_factory(connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")

                table_state: dict[str, bool] = {}
                for table in REQUIRED_TABLES:
                    cursor.execute(
                        "SELECT to_regclass(%s) IS NOT NULL",
                        (table,),
                    )
                    row = cursor.fetchone()
                    table_state[table] = bool(row and row[0])

                column_state: dict[str, bool] = {}
                for table, columns in REQUIRED_COLUMNS.items():
                    schema, table_name = table.split(".", 1)
                    for column in columns:
                        key = f"{table}.{column}"
                        cursor.execute(
                            """
                            SELECT EXISTS (
                              SELECT 1
                                FROM information_schema.columns
                               WHERE table_schema = %s
                                 AND table_name = %s
                                 AND column_name = %s
                            )
                            """,
                            (schema, table_name, column),
                        )
                        row = cursor.fetchone()
                        column_state[key] = bool(row and row[0])

                role_state: dict[str, bool] = {}
                for role in REQUIRED_ROLES:
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)",
                        (role,),
                    )
                    row = cursor.fetchone()
                    role_state[role] = bool(row and row[0])

                privileges: dict[str, dict[str, bool]] = {}
                if (
                    all(role_state.values())
                    and all(table_state.values())
                    and all(column_state.values())
                ):
                    for table in REQUIRED_TABLES:
                        cursor.execute(
                            """
                            SELECT
                              has_table_privilege(%s, %s, 'SELECT'),
                              has_table_privilege(%s, %s, 'INSERT')
                            """,
                            (
                                REQUIRED_ROLES[0],
                                table,
                                REQUIRED_ROLES[1],
                                table,
                            ),
                        )
                        row = cursor.fetchone() or (False, False)
                        privileges[table] = {
                            "reader_select": bool(row[0]),
                            "writer_insert": bool(row[1]),
                        }

        missing_tables = sorted(
            table for table, ready in table_state.items() if not ready
        )
        missing_columns = sorted(
            column for column, ready in column_state.items() if not ready
        )
        missing_roles = sorted(
            role for role, ready in role_state.items() if not ready
        )
        privilege_gaps = sorted(
            table
            for table, state in privileges.items()
            if not state["reader_select"] or not state["writer_insert"]
        )

        ready = (
            not missing_tables
            and not missing_columns
            and not missing_roles
            and not privilege_gaps
        )
        return {
            "status": "READY" if ready else "BLOCKED",
            "schema_ready": not missing_tables and not missing_columns,
            "tables_ready": not missing_tables,
            "columns_ready": not missing_columns,
            "roles_ready": not missing_roles,
            "privileges_ready": not privilege_gaps if privileges else False,
            "missing_tables": missing_tables,
            "missing_columns": missing_columns,
            "missing_roles": missing_roles,
            "privilege_gaps": privilege_gaps,
            "required_tables": list(REQUIRED_TABLES),
            "required_columns": {
                table: list(columns)
                for table, columns in REQUIRED_COLUMNS.items()
            },
            "required_roles": list(REQUIRED_ROLES),
            "mutation_authorized": False,
        }
    except EmpireDBActivationProbeError:
        raise
    except Exception as exc:
        raise EmpireDBActivationProbeError(
            "empiredb_deliverability_probe_failed"
        ) from exc
