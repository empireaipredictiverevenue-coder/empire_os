"""Read-only production gate for HELD EmpireDB 047 buyer-capability schema.

This inspector never applies migrations, reads buyer rows, or changes roles.
Run as postgres OS user; database connection is transaction READ ONLY.
"""
from __future__ import annotations
import json
import os
import sys


MIGRATOR_FLAG_NAMES = (
    "can_login", "inherits_membership", "superuser", "create_database",
    "create_role", "replication", "bypass_rls",
)
# Production's existing 2026-10-13 membership is intentional:
# migrator NOLOGIN, INHERIT, member of exactly one NOLOGIN tenant-reader
# with INHERIT/SET but no ADMIN. Never broaden this to arbitrary members.
EXPECTED_MIGRATOR_FLAGS = (False, True, False, False, False, False, False)
EXPECTED_READER_FLAGS = (False,) * len(MIGRATOR_FLAG_NAMES)
EXPECTED_MEMBERSHIP = (("empiredb_tenant_reader", True, True, False, True),)


def classify(facts: dict) -> dict:
    canonical = (
        facts.get("database") == "empiredb"
        and facts.get("user") == "postgres"
        and facts.get("standby") is False
    )
    flags = facts.get("migrator")
    valid_flags = (
        isinstance(flags, tuple) and
        len(flags) == len(MIGRATOR_FLAG_NAMES) and
        all(type(value) is bool for value in flags)
    )
    # Explain the exact mismatch without granting or relaxing any authority.
    migrator_attributes = (
        dict(zip(MIGRATOR_FLAG_NAMES, flags)) if valid_flags else None
    )
    mismatched_flags = (
        [name for name, actual, expected in
         zip(MIGRATOR_FLAG_NAMES, flags, EXPECTED_MIGRATOR_FLAGS)
         if actual is not expected]
        if valid_flags else ["missing_or_unreadable_migrator"]
    )
    migrator = valid_flags and flags == EXPECTED_MIGRATOR_FLAGS
    reader_flags = facts.get("tenant_reader")
    reader_restricted = (
        isinstance(reader_flags, tuple) and
        reader_flags == EXPECTED_READER_FLAGS and
        all(type(flag) is bool for flag in reader_flags)
    )
    exact_direct_membership = facts.get("migrator_memberships") == EXPECTED_MEMBERSHIP
    no_reader_transitive_memberships = facts.get("tenant_reader_memberships") == ()
    tables = facts.get("parent_tables") == (True, True)
    privileges = facts.get("privileges") == (True, True, True, True, True)
    targets_absent = facts.get("targets_absent") == (True, True)
    checks = {
        "canonical_empiredb": canonical,
        "restricted_migrator": migrator,
        "tenant_reader_role_restricted": reader_restricted,
        "exact_existing_tenant_reader_membership": exact_direct_membership,
        "no_transitive_reader_memberships": no_reader_transitive_memberships,
        "canonical_parent_tables": tables,
        "parent_fk_and_read_permissions": privileges,
        "new_table_and_guard_function_absent": targets_absent,
    }
    return {
        "schema_version": "empire.direct-bsc-buyer-capability-migration-preflight.v2",
        "mode": "READ_ONLY",
        "migrator_attributes": migrator_attributes,
        "migrator_mismatched_flags": mismatched_flags,
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
          SELECT granted.rolname, m.inherit_option, m.set_option,
                 m.admin_option,
                 pg_catalog.pg_has_role('empiredb_migrator',granted.oid,'USAGE')
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
          WHERE member.rolname='empiredb_migrator'
          ORDER BY granted.rolname
        """)
        migrator_memberships = tuple(tuple(row) for row in cur.fetchall())
        cur.execute("""
          SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,
                 rolcreaterole,rolreplication,rolbypassrls
          FROM pg_catalog.pg_roles WHERE rolname='empiredb_tenant_reader'
        """)
        tenant_reader = cur.fetchone()
        cur.execute("""
          SELECT granted.rolname
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
          WHERE member.rolname='empiredb_tenant_reader'
          ORDER BY granted.rolname
        """)
        tenant_reader_memberships = tuple(row[0] for row in cur.fetchall())
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
                         migrator_memberships=migrator_memberships,
                         tenant_reader=tuple(tenant_reader) if tenant_reader else None,
                         tenant_reader_memberships=tenant_reader_memberships,
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
