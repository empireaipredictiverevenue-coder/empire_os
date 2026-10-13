"""EmpireDB 049 v2 — isolated NOLOGIN owner migration preflight, READ ONLY.

Separately approved migration required even when this inspector returns READY.
Only PostgreSQL role/policy/catalog metadata; no order, buyer, wallet or token rows.
"""
from __future__ import annotations

import json
import os
import pwd
import sys

EXPECTED_INCOMING = {
    "role": "empiredb_migrator_login",
    "can_login": True, "inherits_membership": True,
    "superuser": False, "bypass_rls": False,
    "inherit_option": True, "set_option": True, "admin_option": False,
}
# Live parent RLS catalog independently supplied on 13 October 2026.
# Table, owner, enabled, forced, total policies, restrictive, SELECT policies.
EXPECTED_PARENTS = [
    ("bsc_payment_evidence", "empiredb_migrator", True, False, 9, 0),
    ("bsc_payment_requests", "empiredb_migrator", True, False, 10, 0),
    ("fulfilment_orders", "empiredb_migrator", True, False, 23, 0),
]


def classify(f: dict) -> dict:
    checks = {
        "canonical_empiredb":
            f.get("identity") == ("empiredb", "postgres", False),
        "sealed_capability_table":
            f.get("capability") == (True, True, "empiredb_migrator", 0, 0),
        "isolated_owner_absent": f.get("owner_role_absent") is True,
        "dedicated_reader_absent": f.get("reader_role_absent") is True,
        "private_reader_function_absent": f.get("reader_function_absent") is True,
        "expected_existing_migrator_login_preserved":
            f.get("migrator_incoming_member_details") == [EXPECTED_INCOMING],
        "parent_rls_matches_audited_baseline":
            f.get("parents") == EXPECTED_PARENTS,
        "parent_select_policy_present":
            f.get("parent_select_policy_counts",[]) == [5, 6, 11],
        "migrator_source_reads": f.get("source_selects") == (True, True, True),
    }
    return {
        "schema_version": "empire.direct-bsc-buyer-private-reader-049-preflight.v2",
        "mode": "READ_ONLY",
        "status": ("READY_FOR_SEPARATELY_APPROVED_PRIVATE_READER_049"
                   if all(checks.values()) else
                   "HELD_PRIVATE_READER_049_GATES"),
        **checks,
        "existing_migrator_incoming_member_details":
            f.get("migrator_incoming_member_details", []),
        "parent_rls_snapshot": f.get("parents", []),
        "parent_select_policy_counts": f.get("parent_select_policy_counts",[]),
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
    ) as connection, connection.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        identity = tuple(cur.fetchone())
        cur.execute("""
          SELECT c.relrowsecurity,c.relforcerowsecurity,o.rolname,
            (SELECT count(*) FROM pg_catalog.pg_policy p
              WHERE p.polrelid=c.oid),
            (SELECT count(*) FROM pg_catalog.aclexplode(
              COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) acl
              WHERE acl.grantee<>c.relowner)
          FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
          WHERE c.oid=pg_catalog.to_regclass(
            'public.direct_bsc_buyer_capabilities')
        """)
        cap=cur.fetchone()
        cur.execute("""
          SELECT pg_catalog.to_regrole(
                   'empire_direct_checkout_status_owner') IS NULL,
                 pg_catalog.to_regrole(
                   'empire_direct_checkout_status_reader') IS NULL,
                 pg_catalog.to_regprocedure(
                   'public.read_direct_bsc_buyer_status(text)') IS NULL
        """)
        owner_absent,reader_absent,function_absent=cur.fetchone()
        cur.execute("""
          SELECT member.rolname,member.rolcanlogin,member.rolinherit,
                 member.rolsuper,member.rolbypassrls,
                 m.inherit_option,m.set_option,m.admin_option
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles target ON target.oid=m.roleid
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          WHERE target.rolname='empiredb_migrator'
          ORDER BY member.rolname
        """)
        membership=[
            dict(zip(EXPECTED_INCOMING.keys(),row))
            for row in cur.fetchall()
        ]
        cur.execute("""
          SELECT c.relname,o.rolname,c.relrowsecurity,c.relforcerowsecurity,
            (SELECT count(*) FROM pg_catalog.pg_policy p
              WHERE p.polrelid=c.oid),
            (SELECT count(*) FROM pg_catalog.pg_policy p
              WHERE p.polrelid=c.oid AND NOT p.polpermissive),
            (SELECT count(*) FROM pg_catalog.pg_policy p
              WHERE p.polrelid=c.oid AND p.polcmd='r' AND p.polpermissive)
          FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
          WHERE c.relnamespace='public'::regnamespace
            AND c.relname IN ('fulfilment_orders','bsc_payment_requests',
                              'bsc_payment_evidence')
          ORDER BY c.relname
        """)
        rows=cur.fetchall()
        parents=[tuple(r[:6]) for r in rows]
        counts=[r[6] for r in rows]
        cur.execute("""
          SELECT pg_catalog.has_table_privilege(
            'empiredb_migrator','public.fulfilment_orders','SELECT'),
            pg_catalog.has_table_privilege(
            'empiredb_migrator','public.bsc_payment_requests','SELECT'),
            pg_catalog.has_table_privilege(
            'empiredb_migrator','public.bsc_payment_evidence','SELECT')
        """)
        source_selects=tuple(cur.fetchone())
        connection.rollback()
    return classify({
        "identity":identity, "capability":tuple(cap) if cap else None,
        "owner_role_absent":owner_absent,
        "reader_role_absent":reader_absent,
        "reader_function_absent":function_absent,
        "migrator_incoming_member_details":membership,
        "parents":parents, "parent_select_policy_counts":counts,
        "source_selects":source_selects,
    })


def main(argv: list[str]) -> int:
    if argv != ["--preflight"]:
        print(json.dumps({"status":"HELD_EXACT_READONLY_PREFLIGHT_FLAG_REQUIRED"}))
        return 3
    if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({"status":"HELD_POSTGRES_OS_ROLE_REQUIRED"}))
        return 3
    try:
        report=inspect()
    except Exception:
        print(json.dumps({"status":"HELD_CANONICAL_CATALOG_UNAVAILABLE",
                          "mode":"READ_ONLY","migration_049_applied":False}))
        return 4
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"].startswith("READY_") else 2


if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))
