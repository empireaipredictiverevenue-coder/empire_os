"""Read-only canonical EmpireDB 050 private issuer admission preflight.

Never installs roles, alters policies, reads customer rows, or issues tokens.
"""
from __future__ import annotations
import json
import os
import pwd
import sys

OWNER="empire_direct_checkout_status_owner"
READER="empire_direct_checkout_status_reader"
FUNCTION="public.read_direct_bsc_buyer_status(text)"
ISSUER_FUN="public.issue_direct_bsc_buyer_status(text,uuid,uuid,timestamptz,timestamptz)"


def classify(snapshot: dict) -> dict:
    flags={
        "canonical_empiredb":snapshot.get("identity")==("empiredb","postgres",False),
        "capability_force_rls_one_policy":
            snapshot.get("capability")==(True,True,"empiredb_migrator",1),
        "reader_and_owner_isolated":
            snapshot.get("reader_roles")==[(OWNER,False,False,False),
                                         (READER,False,False,False)],
        "reader_role_memberships_zero":snapshot.get("reader_role_member_count")==0,
        "private_status_function_sealed":
            snapshot.get("status_function")==(OWNER,True,True,False),
        "request_rls_policy_count":
            snapshot.get("payment_request_rls")==(True,False,11),
        "047_guard_trigger_present":snapshot.get("guard_trigger") is True,
        "issuer_roles_absent":snapshot.get("issuer_roles_absent")==(True,True),
        "issuer_function_absent":snapshot.get("issuer_function_absent") is True,
        "existing_migrator_login_preserved":
            snapshot.get("migrator_login")==(True,True,True,True),
    }
    return {
        "schema_version":"empire.direct-bsc-private-issuer-050-preflight.v1",
        "mode":"READ_ONLY",
        "status":("READY_FOR_SEPARATELY_APPROVED_PRIVATE_ISSUER_050"
                  if all(flags.values()) else "HELD_PRIVATE_ISSUER_050_GATES"),
        **flags,
        "migration_050_applied":False,
        "buyer_status_endpoint_activated":False,
        "issuer_login_assigned":False,
        "reader_login_assigned":False,
        "payment_execution":False,
        "release_gate":"FOUNDER_APPROVAL_050_REQUIRED",
    }


def inspect():
    import psycopg
    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb "
        "user=postgres connect_timeout=5"
    ) as conn,conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='3500ms'")
        cur.execute("SELECT current_database(),current_user,pg_is_in_recovery()")
        identity=tuple(cur.fetchone())
        cur.execute("""
          SELECT c.relrowsecurity,c.relforcerowsecurity,o.rolname,
            (SELECT count(*) FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid)
          FROM pg_catalog.pg_class c JOIN pg_catalog.pg_roles o ON o.oid=c.relowner
          WHERE c.oid='public.direct_bsc_buyer_capabilities'::regclass
        """)
        capability=tuple(cur.fetchone())
        cur.execute("""
          SELECT rolname,rolcanlogin,rolinherit,rolbypassrls
          FROM pg_catalog.pg_roles
          WHERE rolname IN (%s,%s) ORDER BY rolname
        """,(OWNER,READER))
        roles=[tuple(r) for r in cur.fetchall()]
        cur.execute("""
          SELECT count(*) FROM pg_catalog.pg_auth_members m
          WHERE m.member IN (%s::regrole,%s::regrole)
             OR m.roleid IN (%s::regrole,%s::regrole)
        """,(OWNER,READER,OWNER,READER))
        member_count=cur.fetchone()[0]
        cur.execute("""
          SELECT o.rolname,f.prosecdef,
            pg_catalog.has_function_privilege(%s,%s,'EXECUTE'),
            pg_catalog.has_function_privilege('empiredb_app',%s,'EXECUTE')
          FROM pg_catalog.pg_proc f
          JOIN pg_catalog.pg_roles o ON o.oid=f.proowner
          WHERE f.oid=pg_catalog.to_regprocedure(%s)
        """,(READER,FUNCTION,FUNCTION,FUNCTION))
        function_row=cur.fetchone()
        func=tuple(function_row) if function_row else None
        cur.execute("""
          SELECT c.relrowsecurity,c.relforcerowsecurity,
            (SELECT count(*) FROM pg_catalog.pg_policy p WHERE p.polrelid=c.oid)
          FROM pg_catalog.pg_class c
          WHERE c.oid='public.bsc_payment_requests'::regclass
        """)
        request=tuple(cur.fetchone())
        cur.execute("""
          SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger t
            WHERE t.tgrelid='public.direct_bsc_buyer_capabilities'::regclass
              AND t.tgname='direct_bsc_buyer_capability_guard'
              AND t.tgenabled='O' AND NOT t.tgisinternal),
            pg_catalog.to_regrole(
              'empire_direct_checkout_status_issuer_owner') IS NULL,
            pg_catalog.to_regrole(
              'empire_direct_checkout_status_issuer') IS NULL,
            pg_catalog.to_regprocedure(%s) IS NULL
        """,(ISSUER_FUN,))
        trigger,abs_owner,abs_issuer,abs_fun=cur.fetchone()
        cur.execute("""
          SELECT member.rolcanlogin,member.rolinherit,
            m.inherit_option,m.set_option
          FROM pg_catalog.pg_auth_members m
          JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid
          JOIN pg_catalog.pg_roles member ON member.oid=m.member
          WHERE parent.rolname='empiredb_migrator'
          AND member.rolname='empiredb_migrator_login'
        """)
        login=cur.fetchone()
        conn.rollback()
    return classify({
        "identity":identity,"capability":capability,
        "reader_roles":roles,
        "reader_role_member_count":member_count,
        "status_function":func,
        "payment_request_rls":request,
        "guard_trigger":trigger,
        "issuer_roles_absent":(abs_owner,abs_issuer),
        "issuer_function_absent":abs_fun,
        "migrator_login":tuple(login) if login else None,
    })


def main(argv: list[str])->int:
    if argv!=["--preflight"]:
        print(json.dumps({"status":"HELD_READONLY_PREFLIGHT_FLAG_REQUIRED"}))
        return 3
    if os.geteuid()!=pwd.getpwnam("postgres").pw_uid:
        print(json.dumps({"status":"HELD_POSTGRES_OS_USER_REQUIRED"}))
        return 3
    try:
        state=inspect()
    except Exception:
        print(json.dumps({"status":"HELD_CANONICAL_CATALOG_UNAVAILABLE",
                          "mode":"READ_ONLY","migration_050_applied":False}))
        return 4
    print(json.dumps(state,sort_keys=True))
    return 0 if state["status"].startswith("READY_") else 2


if __name__=="__main__":
    raise SystemExit(main(sys.argv[1:]))
