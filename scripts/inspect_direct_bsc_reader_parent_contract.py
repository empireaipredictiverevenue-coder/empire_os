"""Read-only, system-catalog-only readiness evidence for isolated buyer status owner.

Use as postgres OS peer: python -m scripts.inspect_direct_bsc_reader_parent_contract --preflight
This does NOT authorize migration 049. It reads only pg_catalog metadata,
not buyer, order, capability, fingerprint, or payment data.
"""
from __future__ import annotations

import json
import os
import pwd
import sys

TABLE_NAMES = (
    "direct_bsc_buyer_capabilities",
    "fulfilment_orders",
    "bsc_payment_requests",
    "bsc_payment_evidence",
)


def classify(rows, memberships, default_privs) -> dict:
    names = {r["table_name"] for r in rows}
    complete = (
        len(rows) == len(TABLE_NAMES) and
        len(names) == len(TABLE_NAMES) and
        names == set(TABLE_NAMES)
    )
    return {
        "schema_version": "empire.bsc-private-reader-parent-rls-catalog.v1",
        "mode": "READ_ONLY",
        "production_changes": False,
        "status": "CATALOG_OBSERVED_REVIEW_REQUIRED" if complete
                  else "HELD_PARENT_CATALOG_MISSING",
        "parent_table_security": rows,
        "migrator_incoming_memberships": memberships,
        "existing_migrator_default_grants": default_privs,
        "migration_049_applied": False,
        "payment_execution": False,
    }


def inspect():
    import psycopg
    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb "
        "user=postgres connect_timeout=5"
    ) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        if tuple(cur.fetchone()) != ("empiredb", "postgres", False):
            raise RuntimeError("noncanonical database")
        cur.execute("""
          SELECT c.relname,owner.rolname,c.relrowsecurity,c.relforcerowsecurity,
            (SELECT count(*) FROM pg_catalog.pg_policy p
              WHERE p.polrelid=c.oid)
          FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_roles owner ON owner.oid=c.relowner
          WHERE c.relnamespace='public'::regnamespace
            AND c.relname = ANY(%s)
          ORDER BY c.relname
        """, (list(TABLE_NAMES),))
        rows=[]
        for name,owner,rls,force,count in cur.fetchall():
            rows.append({
                "table_name": name, "owner": owner,
                "rls_enabled": rls, "rls_forced": force,
                "rls_policy_count": count,
            })
        cur.execute("""
          SELECT c.relname,p.polname,p.polpermissive,p.polcmd,
            COALESCE((SELECT pg_catalog.array_agg(
              CASE WHEN target.oid=0 THEN 'PUBLIC' ELSE role.rolname END
              ORDER BY target.oid)
              FROM pg_catalog.unnest(p.polroles) AS target(oid)
              LEFT JOIN pg_catalog.pg_roles role
                ON role.oid=target.oid),ARRAY[]::text[]),
            pg_catalog.pg_get_expr(p.polqual,p.polrelid)
          FROM pg_catalog.pg_policy p
          JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
          WHERE c.relnamespace='public'::regnamespace
            AND c.relname = ANY(%s)
          ORDER BY c.relname,p.polname
        """, (list(TABLE_NAMES),))
        policies={}
        for table,name,permissive,command,targets,qual in cur.fetchall():
            policies.setdefault(table,[]).append({
                "name":name,"permissive":permissive,
                "command":command,"target_roles":targets,
                "select_scope_expression":qual,
            })
        for row in rows:
            row["policy_metadata"] = policies.get(row["table_name"],[])
        cur.execute("""
          SELECT member.rolname, member.rolcanlogin,
                 m.inherit_option,m.set_option,m.admin_option
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          JOIN pg_catalog.pg_roles granted ON granted.oid=m.roleid
          WHERE granted.rolname='empiredb_migrator'
          ORDER BY member.rolname
        """)
        members=[
            {"role":n,"can_login":login,"inherit_option":inh,
             "set_option":sett,"admin_option":adm}
            for n,login,inh,sett,adm in cur.fetchall()
        ]
        cur.execute("""
          SELECT COALESCE(ns.nspname,'<global>'),grantee.rolname,
            acl.privilege_type
          FROM pg_catalog.pg_default_acl d
          JOIN pg_catalog.pg_roles owner ON owner.oid=d.defaclrole
          LEFT JOIN pg_catalog.pg_namespace ns ON ns.oid=d.defaclnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(d.defaclacl) acl
          JOIN pg_catalog.pg_roles grantee ON grantee.oid=acl.grantee
          WHERE owner.rolname='empiredb_migrator' AND d.defaclobjtype='r'
          ORDER BY ns.nspname,grantee.rolname,acl.privilege_type
        """)
        default=[
            {"schema":sc,"grantee":gr,"privilege":priv}
            for sc,gr,priv in cur.fetchall()
        ]
        conn.rollback()
    return classify(rows,members,default)


def main(argv):
    if argv!=["--preflight"]:
        print(json.dumps({"status":"HELD_READONLY_FLAG_REQUIRED"}))
        return 3
    if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({"status":"HELD_POSTGRES_OS_USER_REQUIRED"}))
        return 3
    try:
        result=inspect()
    except Exception:
        print(json.dumps({"mode":"READ_ONLY",
                          "status":"HELD_PARENT_CATALOG_UNAVAILABLE",
                          "production_changes":False}))
        return 4
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="CATALOG_OBSERVED_REVIEW_REQUIRED" else 2


if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))
