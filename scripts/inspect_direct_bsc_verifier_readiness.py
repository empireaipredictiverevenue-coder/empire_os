#!/usr/bin/env python3
"""Read-only PostgreSQL catalog guard for the DIRECT BSC payment verifier.

Does not grant roles, create accounts, approve or record payments, change
checkout switches, inspect customer tables, or access operator passwords.
Run as postgres using the existing sudo-controlled operator session.
"""
from __future__ import annotations

import json
import os
import sys

from empire_os.bsc_payment_operator_readiness import (
    DB, APP, LOGIN_FLAGS, PERMISSION_ROLE_FLAGS,
)

GROUP = "empire_bsc_verifier"
LOGIN = "empire_bsc_verifier_login"
VERIFY = "public.record_bsc_payment_evidence(uuid,jsonb)"
REVIEW = "public.get_bsc_payment_request_review(uuid)"


def first_matching_scram(rows: list[dict]) -> bool:
    """Reject a generic peer/trust rule shadowing the dedicated login."""
    if not rows or any(row.get("error") is not None for row in rows):
        return False
    for row in sorted(rows, key=lambda r: r.get("rule_number", 999999)):
        if row.get("type") != "local":
            continue
        dbs, users = row.get("database"), row.get("user_name")
        if not isinstance(dbs, list) or not isinstance(users, list):
            return False
        db_matches = DB in dbs or "all" in dbs or "sameuser" in dbs
        user_matches = LOGIN in users or "all" in users or "sameuser" in users
        user_matches |= any(isinstance(u, str) and
                            (u.startswith("+") or u.startswith("@")) for u in users)
        if db_matches and user_matches:
            return (dbs == [DB] and users == [LOGIN] and
                    row.get("auth_method") == "scram-sha-256")
    return False


def classify(data: dict) -> dict:
    """Never infer operator readiness from a missing/partial catalog response."""
    roles = data["roles"]
    members = data["memberships"]
    privileges = data["privileges"]
    db_priv = data["database_privileges"]
    role_ok = roles.get(GROUP) == PERMISSION_ROLE_FLAGS
    app_safe = roles.get(APP) == (True, True, False, False, False, False, False)
    functions_ok = (privileges.get(("group", REVIEW)) is True and
                    privileges.get(("group", VERIFY)) is True)
    app_separate = (privileges.get(("app", VERIFY)) is False and
                    privileges.get(("app", "public.approve_bsc_payment_request(uuid,text,text)")) is False)
    login_exists = LOGIN in roles
    login_safe = roles.get(LOGIN) == LOGIN_FLAGS
    memberships_safe = members == [(GROUP, LOGIN, False, True, False)]
    acl_safe = db_priv == (True, False, False)
    hba_safe = first_matching_scram(data["hba"])
    if not data["canonical"] or not role_ok or not app_safe or not functions_ok or not app_separate:
        status = "BLOCKED_DIRECT_VERIFIER_BASE_AUTHORITY"
    elif not login_exists and not members:
        status = "DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED"
    elif not login_safe or not memberships_safe or not acl_safe or not hba_safe:
        status = "BLOCKED_DIRECT_VERIFIER_LOGIN_OR_ACL"
    else:
        status = "DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED"
    return {
        "schema_version": "empire.direct-bsc-verifier-catalog.v1",
        "mode": "READ_ONLY",
        "status": status,
        "canonical_empiredb": bool(data["canonical"]),
        "permission_role_safe": role_ok,
        "app_financial_separation_verified": app_safe and app_separate,
        "exact_direct_payment_rpc_grants": functions_ok,
        "login_present": login_exists,
        "login_security_attributes_safe": login_safe,
        "exact_noninherited_role_membership": memberships_safe,
        "database_connect_only": acl_safe,
        "effective_local_scram": hba_safe,
        "human_operator_assigned": False,
        "password_authentication_independently_verified": False,
        "checkout_activated": False,
        "payment_or_database_mutation": False,
    }


def inspect() -> dict:
    import psycopg
    with psycopg.connect(
        "host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5"
    ) as conn, conn.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SET LOCAL statement_timeout='4000ms'")
        cur.execute("SELECT current_database(), current_user, pg_is_in_recovery()")
        database, user, recovery = cur.fetchone()
        cur.execute("""
            SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,
                   rolcreaterole,rolreplication,rolbypassrls
            FROM pg_catalog.pg_roles WHERE rolname IN (%s,%s,%s)
        """, (GROUP, LOGIN, APP))
        roles = {r[0]: tuple(r[1:]) for r in cur.fetchall()}
        cur.execute("""
            SELECT g.rolname,m.rolname,a.inherit_option,a.set_option,a.admin_option
            FROM pg_catalog.pg_auth_members a
            JOIN pg_catalog.pg_roles g ON g.oid=a.roleid
            JOIN pg_catalog.pg_roles m ON m.oid=a.member
            WHERE g.rolname=%s OR m.rolname=%s
            ORDER BY g.rolname,m.rolname
        """, (GROUP, LOGIN))
        members = [tuple(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT rule_number,type,database,user_name,auth_method,error
            FROM pg_catalog.pg_hba_file_rules
        """)
        keys = ("rule_number", "type", "database", "user_name", "auth_method", "error")
        hba = [dict(zip(keys, r)) for r in cur.fetchall()]
        privileges = {}
        for signature in (REVIEW, VERIFY):
            cur.execute("SELECT to_regprocedure(%s) IS NOT NULL, has_function_privilege(%s,%s,'EXECUTE')",
                        (signature, GROUP, signature))
            exists, right = cur.fetchone()
            privileges[("group", signature)] = bool(exists and right)
        for signature in (VERIFY, "public.approve_bsc_payment_request(uuid,text,text)"):
            cur.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                        (APP, signature))
            privileges[("app", signature)] = bool(cur.fetchone()[0])
        db_priv = None
        if LOGIN in roles:
            cur.execute("""
                SELECT has_database_privilege(%s,%s,'CONNECT'),
                       has_database_privilege(%s,%s,'CREATE'),
                       has_database_privilege(%s,%s,'TEMP')
            """, (LOGIN, DB, LOGIN, DB, LOGIN, DB))
            db_priv = tuple(cur.fetchone())
        conn.rollback()
    return classify({
        "canonical": database == DB and user == "postgres" and recovery is False,
        "roles": roles, "memberships": members,
        "privileges": privileges, "database_privileges": db_priv, "hba": hba,
    })


def main(argv: list[str]) -> int:
    if argv not in ([], ["--preflight"]) or os.geteuid() == 0:
        # Run as the postgres OS user, not arbitrary root or app privileges.
        print(json.dumps({"status": "HELD_POSTGRES_READONLY_INVOCATION_REQUIRED"}))
        return 3
    try:
        import pwd
        if os.geteuid() != pwd.getpwnam("postgres").pw_uid:
            raise RuntimeError("postgres operator identity required")
        report = inspect()
    except Exception:
        print(json.dumps({"status": "HELD_DIRECT_VERIFIER_CATALOG_UNAVAILABLE",
                          "mode": "READ_ONLY", "checkout_activated": False}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
