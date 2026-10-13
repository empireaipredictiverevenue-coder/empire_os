"""Read-only production gate for HELD EmpireDB 047 buyer-capability schema.

This inspector never applies migrations, reads buyer rows, or changes roles.
Run as postgres OS user; database connection is transaction READ ONLY.
"""
from __future__ import annotations
import json
import os
import sys


def classify(facts: dict) -> dict:
    canonical = (
        facts.get("database") == "empiredb"
        and facts.get("user") == "postgres"
        and facts.get("standby") is False
    )
    migrator = facts.get("migrator") == (
        False, False, False, False, False, False, False
    )
    # migrator flags:
    # can_login, inherit, super, create_db, create_role, replication, bypass_rls
    tables = facts.get("parent_tables") == (True, True)
    privileges = facts.get("privileges") == (True, True, True, True, True)
    targets_absent = facts.get("targets_absent") == (True, True)
    checks = {
        "canonical_empiredb": canonical,
        "restricted_migrator": migrator,
        "canonical_parent_tables": tables,
        "parent_fk_and_read_permissions": privileges,
        "new_table_and_guard_function_absent": targets_absent,
    }
    return {
        "schema_version": "empire.direct-bsc-buyer-capability-migration-preflight.v1",
        "mode": "READ_ONLY",
        "status": (
            "READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION"
            if all(checks.values()) else "HELD_SCHEMA_OR_AUTHORITY_DRIFT"
        ),
        **checks,
        "migration_applied": False,
        "checkout_activated": False,
        "payment_or_customer_mutation": False,
        "release_gates": "MIGRATION_APPROVAL_REQUIRED",
    }


def inspect() -> dict:
    import psycopg
    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5"
    ) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        database, user, standby = cur.fetchone()
        cur.execute("""
          SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,
                 rolcreaterole,rolreplication,rolbypassrls
          FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
        """)
        flags = cur.fetchone()
        cur.execute("""
          SELECT pg_catalog.to_regclass('public.fulfilment_orders') IS NOT NULL,
                 pg_catalog.to_regclass('public.bsc_payment_requests') IS NOT NULL
        """)
        parent_tables = tuple(cur.fetchone())
        cur.execute("""
          SELECT pg_catalog.has_schema_privilege('empiredb_migrator','public','CREATE'),
                 pg_catalog.has_table_privilege('empiredb_migrator','public.fulfilment_orders','SELECT'),
                 pg_catalog.has_table_privilege('empiredb_migrator','public.fulfilment_orders','REFERENCES'),
                 pg_catalog.has_table_privilege('empiredb_migrator','public.bsc_payment_requests','SELECT'),
                 pg_catalog.has_table_privilege('empiredb_migrator','public.bsc_payment_requests','REFERENCES')
        """)
        privileges = tuple(cur.fetchone())
        cur.execute("""
          SELECT pg_catalog.to_regclass('public.direct_bsc_buyer_capabilities') IS NULL,
                 pg_catalog.to_regprocedure('public.guard_direct_bsc_buyer_capability()') IS NULL
        """)
        targets_absent = tuple(cur.fetchone())
        conn.rollback()
    return classify(dict(database=database, user=user, standby=standby,
                         migrator=tuple(flags) if flags else None,
                         parent_tables=parent_tables,
                         privileges=privileges,
                         targets_absent=targets_absent))


def main(argv: list[str]) -> int:
    if argv != ["--preflight"]:
        print(json.dumps({"status": "HELD_EXACT_READONLY_FLAG_REQUIRED"}))
        return 3
    import pwd
    if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({"status": "HELD_POSTGRES_OS_IDENTITY_REQUIRED"}))
        return 3
    try:
        report = inspect()
    except Exception:
        print(json.dumps({"status": "HELD_CANONICAL_CATALOG_UNAVAILABLE",
                          "mode": "READ_ONLY", "migration_applied": False}))
        return 4
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].startswith("READY_") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
