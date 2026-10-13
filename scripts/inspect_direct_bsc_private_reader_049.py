"""Read-only canonical EmpireDB gate for HELD private buyer status reader 049.

No buyer/order rows, no migrations, no role mutation, no payment action.
Requires postgres OS peer connection and exact --preflight flag.
"""
from __future__ import annotations

import json
import os
import sys


def classify(f: dict) -> dict:
    checks = {
        "canonical_empiredb": f.get("identity") == ("empiredb", "postgres", False),
        "sealed_capability_table": f.get("capability") ==
            (True, True, "empiredb_migrator", 0, 0),
        "dedicated_reader_absent": f.get("reader_role_absent") is True,
        "private_reader_function_absent": f.get("reader_function_absent") is True,
        "migrator_has_zero_incoming_memberships":
            f.get("migrator_incoming_memberships") == 0,
        "canonical_source_tables_present": f.get("tables") == (True, True, True),
        "migrator_private_source_reads": f.get("selects") == (True, True, True),
    }
    return {
        "schema_version": "empire.direct-bsc-buyer-private-reader-049-preflight.v1",
        "mode": "READ_ONLY",
        "status": (
            "READY_FOR_SEPARATELY_APPROVED_PRIVATE_READER_049"
            if all(checks.values()) else "HELD_PRIVATE_READER_049_GATES"
        ),
        **checks,
        # Names and boolean role attributes only: never credentials, DSNs,
        # buyer records, contact data, or full database catalogue.
        "migrator_incoming_member_details": (
            f.get("migrator_incoming_member_details")
            if isinstance(f.get("migrator_incoming_member_details"), list)
            else []
        ),
        "non_superuser_logins_with_migrator_membership": (
            f.get("non_superuser_login_paths")
            if isinstance(f.get("non_superuser_login_paths"), list)
            else []
        ),
        "migration_049_applied": False,
        "reader_login_assigned": False,
        "buyer_status_endpoint_activated": False,
        "payment_execution": False,
        "release_gate": "FOUNDER_APPROVAL_049_REQUIRED",
    }


def inspect() -> dict:
    import psycopg
    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb "
        "user=postgres connect_timeout=5"
    ) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        identity = tuple(cur.fetchone())
        cur.execute("""
          SELECT c.relrowsecurity,c.relforcerowsecurity,owner.rolname,
                 (SELECT count(*) FROM pg_catalog.pg_policy p
                  WHERE p.polrelid=c.oid),
                 (SELECT count(*) FROM pg_catalog.aclexplode(
                   COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))
                 ) acl WHERE acl.grantee<>c.relowner)
          FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
          WHERE c.oid=pg_catalog.to_regclass(
            'public.direct_bsc_buyer_capabilities')
        """)
        capability = cur.fetchone()
        cur.execute("""
          SELECT pg_catalog.to_regrole(
                   'empire_direct_checkout_status_reader') IS NULL,
                 pg_catalog.to_regprocedure(
                   'public.read_direct_bsc_buyer_status(text)') IS NULL
        """)
        role_absent, function_absent = cur.fetchone()
        cur.execute("""
          SELECT member.rolname,member.rolcanlogin,member.rolsuper,
                 m.inherit_option,m.set_option,m.admin_option
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          WHERE granted.rolname='empiredb_migrator'
          ORDER BY member.rolname
        """)
        incoming_details = [
            {
                "role": row[0],
                "can_login": row[1],
                "superuser": row[2],
                "inherit_option": row[3],
                "set_option": row[4],
                "admin_option": row[5],
            }
            for row in cur.fetchall()
        ]
        incoming = len(incoming_details)
        cur.execute("""
          SELECT r.rolname
          FROM pg_catalog.pg_roles r
          JOIN pg_catalog.pg_roles target
            ON target.rolname='empiredb_migrator'
          WHERE r.rolcanlogin AND NOT r.rolsuper
            AND pg_catalog.pg_has_role(r.oid,target.oid,'MEMBER')
          ORDER BY r.rolname
        """)
        login_paths = [row[0] for row in cur.fetchall()]
        cur.execute("""
          SELECT pg_catalog.to_regclass('public.fulfilment_orders') IS NOT NULL,
                 pg_catalog.to_regclass('public.bsc_payment_requests') IS NOT NULL,
                 pg_catalog.to_regclass('public.bsc_payment_evidence') IS NOT NULL
        """)
        tables = tuple(cur.fetchone())
        cur.execute("""
          SELECT pg_catalog.has_table_privilege(
                   'empiredb_migrator','public.fulfilment_orders','SELECT'),
                 pg_catalog.has_table_privilege(
                   'empiredb_migrator','public.bsc_payment_requests','SELECT'),
                 pg_catalog.has_table_privilege(
                   'empiredb_migrator','public.bsc_payment_evidence','SELECT')
        """)
        selects = tuple(cur.fetchone())
        conn.rollback()
    return classify({
        "identity": identity,
        "capability": tuple(capability) if capability else None,
        "reader_role_absent": role_absent,
        "reader_function_absent": function_absent,
        "migrator_incoming_memberships": incoming,
        "migrator_incoming_member_details": incoming_details,
        "non_superuser_login_paths": login_paths,
        "tables": tables,
        "selects": selects,
    })


def main(argv: list[str]) -> int:
    if argv != ["--preflight"]:
        print(json.dumps({"status": "HELD_EXACT_READONLY_PREFLIGHT_FLAG_REQUIRED"}))
        return 3
    import pwd
    if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({"status": "HELD_POSTGRES_OS_ROLE_REQUIRED"}))
        return 3
    try:
        report = inspect()
    except Exception:
        print(json.dumps({
            "status": "HELD_CANONICAL_CATALOG_UNAVAILABLE",
            "mode": "READ_ONLY", "migration_049_applied": False,
        }))
        return 4
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"].startswith("READY_") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
