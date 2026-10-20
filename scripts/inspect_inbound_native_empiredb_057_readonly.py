"""Read-only native EmpireDB 057 production-catalog preflight.

Only static PostgreSQL catalogs; never reads tenants, users, calendar rows,
OAuth tokens, payments, customer data or secret values.
Requires the trusted postgres OS peer role. No sudo helper is included.
A READY catalog is NOT permission to execute the held DDL.
"""
from __future__ import annotations

import json
import os
import pwd
import sys

TABLES = (
    "inbound_recovery_tenants",
    "inbound_recovery_events",
    "inbound_recovery_signed_callbacks",
    "inbound_recovery_management_access_audit",
    "inbound_booking_workflow_events",
    "inbound_recovery_contact_suppression",
    "inbound_recovery_calendar_bindings",
    "inbound_recovery_calendar_links",
    "inbound_recovery_calendar_status_evidence",
    "inbound_recovery_calendar_projection_delivery",
)


def classify(facts: dict) -> dict:
    """Fail closed on incomplete, inconsistent or unexpected catalog facts."""
    identity = facts.get("database_identity")
    role = facts.get("migration_role")
    crm = facts.get("crm_membership")
    resolver = facts.get("crm_resolvers")
    existing = facts.get("existing_inbound_tables")
    checks = {
        "canonical_primary_empiredb":
            identity == ["empiredb", "postgres", False],
        "migration_role_nonlogin_nonprivileged":
            role == [False, False, False, False, False],
        "migration_role_can_create_schema":
            facts.get("migrator_can_create_public") is True,
        "native_crm_membership_rls_present":
            crm == ["empiredb_migrator", True, "r"],
        "canonical_crm_membership_reader_present":
            resolver == [True, True],
        "recovery_tables_not_preexisting":
            isinstance(existing, list) and existing == [],
        "db_057_catalog_source_checked":
            facts.get("catalog_source_checked") is True,
    }
    return {
        "schema": "empire.inbound.recovery.empiredb057.preflight.v1",
        "mode": "READ_ONLY_PG_CATALOG",
        "status": (
            "READY_FOR_INDEPENDENT_DBA_MIGRATION_REVIEW"
            if all(checks.values())
            else "HELD_NATIVE_EMPIREDB_057_RELEASE_GATES"
        ),
        "gates": checks,
        # No raw tenant UUID, user, secret, passwords, DSN or commercial rows.
        "existing_057_table_count": len(existing) if isinstance(existing, list) else None,
        "database_migration_executed": False,
        "customer_calendar_enabled": False,
        "external_actions": False,
        "revenue_verified": False,
        "requires_explicit_dba_and_founder_approval": True,
    }


def inspect_native_catalog() -> dict:
    import psycopg

    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb "
        "user=postgres connect_timeout=5 "
        "options='-c default_transaction_read_only=on'",
    ) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout='3500ms'")
            cur.execute("SET LOCAL lock_timeout='1000ms'")
            cur.execute("""
                SELECT current_database(),current_user,pg_catalog.pg_is_in_recovery()
            """)
            db = list(cur.fetchone())
            cur.execute("""
                SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole
                FROM pg_catalog.pg_roles
                WHERE rolname='empiredb_migrator'
            """)
            role = cur.fetchone()
            cur.execute("""
                SELECT pg_catalog.has_schema_privilege(
                    'empiredb_migrator','public','CREATE')
            """)
            can_create = cur.fetchone()[0] if role is not None else False
            cur.execute("""
                SELECT owner.rolname,c.relrowsecurity,c.relkind
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
                WHERE c.oid=pg_catalog.to_regclass(
                  'public.empire_crm_tenant_memberships')
            """)
            crm = cur.fetchone()
            cur.execute("""
                SELECT pg_catalog.to_regprocedure(
                  'public.empire_crm_read_member(text,uuid)') IS NOT NULL,
                       pg_catalog.to_regprocedure(
                  'public.empire_current_tenant_id()') IS NOT NULL
            """)
            resolvers = cur.fetchone()
            cur.execute("""
                SELECT c.relname FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relname=ANY(%s)
                ORDER BY c.relname
            """, (list(TABLES),))
            inbound = [r[0] for r in cur.fetchall()]
            con.rollback()

    return classify({
        "database_identity": db,
        "migration_role": list(role) if role is not None else None,
        "migrator_can_create_public": can_create,
        "crm_membership": list(crm) if crm is not None else None,
        "crm_resolvers": list(resolvers),
        "existing_inbound_tables": inbound,
        "catalog_source_checked": True,
    })


def main(argv: list[str]) -> int:
    if argv != ["--read-only", "--pg-catalog-only"]:
        print(json.dumps({"status": "EXACT_READ_ONLY_FLAGS_REQUIRED"}))
        return 3
    if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({
            "mode": "READ_ONLY_PG_CATALOG",
            "status": "HELD_POSTGRES_OS_ROLE_REQUIRED",
            "database_migration_executed": False,
        }))
        return 3
    try:
        report = inspect_native_catalog()
    except Exception:
        report = {
            "status": "HELD_CANONICAL_CATALOG_PROBE_UNAVAILABLE",
            "mode": "READ_ONLY_PG_CATALOG",
            "database_migration_executed": False,
        }
        print(json.dumps(report, sort_keys=True))
        return 4
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].startswith("READY_") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
