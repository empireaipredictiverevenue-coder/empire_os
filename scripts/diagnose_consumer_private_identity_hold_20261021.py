#!/usr/bin/env python3
"""Read-only segmented diagnostic for the consumer identity hold.

Never prints passwords, HMACs, DSNs, SQL errors, role verifiers or PII.
Exposes only an allowlisted *stage code* for the first failing check.
Must run as root from a root-owned, checksum-pinned local path.
Never creates a role, secret, subscriber record, service or email.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import psycopg

ROOT_SOURCE=Path("/usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py")
ROOT_SOURCE_SHA256="7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42"
STAGES=frozenset((
    "IDENTITY_SOURCE", "VAULT", "SCRAM_CONNECT", "READ_ONLY_TX",
    "LOGIN_IDENTITY", "ROLE_ATTRIBUTES", "MEMBERSHIP", "SET_LOCAL_ROLE",
    "WRITER_IDENTITY", "RLS_SCHEMA", "POLICY_SET", "TABLE_ACL",
    "RLS_ZERO_ROW_ACCESS", "SUCCESS",
))


def _load_original():
    # No script code is loaded from a user-writable directory under root.
    st=ROOT_SOURCE.stat()
    if st.st_uid != 0 or ROOT_SOURCE.is_symlink() or (st.st_mode & 0o022):
        raise RuntimeError("UNTRUSTED_ORIGINAL_READONLY_SOURCE")
    if hashlib.sha256(ROOT_SOURCE.read_bytes()).hexdigest()!=ROOT_SOURCE_SHA256:
        raise RuntimeError("ORIGINAL_READONLY_SOURCE_DIGEST_HOLD")
    spec=importlib.util.spec_from_file_location("consumer_approved_readonly",ROOT_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("ORIGINAL_REVIEW_SOURCE_UNAVAILABLE")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnosed_readonly(*, original=None, connect=psycopg.connect) -> dict:
    stage="IDENTITY_SOURCE"
    try:
        if os.geteuid()!=0:
            raise RuntimeError("ROOT_IDENTITY_REQUIRED")
        module=original or _load_original()
        stage="VAULT"
        password, keys=module.read_custody()
        # The original helper validates vault root owner, permissions and
        # all 256-bit keys. Never print, store or forward any of them.
        del keys
        stage="SCRAM_CONNECT"
        with connect(
            dbname=module.DB,host="127.0.0.1",port=5432,
            user=module.LOGIN,password=password,connect_timeout=5,
            application_name="empire_consumer_redacted_readonly_diagnostic",
        ) as conn:
            del password
            stage="READ_ONLY_TX"
            conn.execute("SET TRANSACTION READ ONLY")
            stage="LOGIN_IDENTITY"
            row=conn.execute(
                "SELECT session_user,current_user,current_database(),"
                "current_setting('transaction_read_only')"
            ).fetchone()
            if row!=(module.LOGIN,module.LOGIN,module.DB,"on"):
                raise RuntimeError("LOGIN_IDENTITY_HOLD")
            stage="ROLE_ATTRIBUTES"
            attrs=conn.execute(
                "SELECT l.rolcanlogin,NOT l.rolinherit,NOT l.rolsuper,"
                "NOT l.rolbypassrls,NOT l.rolcreatedb,NOT l.rolcreaterole,"
                "NOT l.rolreplication,l.rolconnlimit=5,"
                "NOT w.rolcanlogin,NOT w.rolinherit,"
                "NOT w.rolsuper,NOT w.rolbypassrls "
                "FROM pg_catalog.pg_roles l CROSS JOIN pg_catalog.pg_roles w "
                "WHERE l.rolname=%s AND w.rolname=%s",
                (module.LOGIN,module.WRITER),
            ).fetchone()
            if attrs!=(True,)*12:
                raise RuntimeError("ROLE_ATTRIBUTES_HOLD")
            stage="MEMBERSHIP"
            count=conn.execute(
                "SELECT count(*),bool_and(r.rolname=%s AND m.set_option "
                "AND NOT m.inherit_option AND NOT m.admin_option) "
                "FROM pg_catalog.pg_auth_members m "
                "JOIN pg_catalog.pg_roles u ON u.oid=m.member "
                "JOIN pg_catalog.pg_roles r ON r.oid=m.roleid "
                "WHERE u.rolname=%s",
                (module.WRITER,module.LOGIN),
            ).fetchone()
            if count!=(1,True):
                raise RuntimeError("MEMBERSHIP_HOLD")
            stage="SET_LOCAL_ROLE"
            conn.execute("SET LOCAL ROLE "+module.WRITER)
            stage="WRITER_IDENTITY"
            who=conn.execute(
                "SELECT session_user,current_user,current_database(),"
                "current_setting('transaction_read_only')"
            ).fetchone()
            if who!=(module.LOGIN,module.WRITER,module.DB,"on"):
                raise RuntimeError("WRITER_IDENTITY_HOLD")
            stage="RLS_SCHEMA"
            schema=conn.execute(
                "SELECT count(*) FROM pg_catalog.pg_class c "
                "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=ANY(%s) "
                "AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity "
                "AND pg_get_userbyid(c.relowner)='empiredb_migrator'",
                (list(module.TABLES),),
            ).fetchone()
            if schema!=(5,):
                raise RuntimeError("RLS_SCHEMA_HOLD")
            stage="POLICY_SET"
            policies=conn.execute(
                "SELECT policyname FROM pg_catalog.pg_policies "
                "WHERE schemaname='public' AND tablename=ANY(%s)",
                (list(module.TABLES),),
            ).fetchall()
            if len(policies)!=5 or {r[0] for r in policies}!=set(module.POLICIES):
                raise RuntimeError("POLICY_SET_HOLD")
            for table in module.TABLES:
                name="public."+table
                stage="TABLE_ACL"
                acl=conn.execute(
                    "SELECT has_table_privilege(%s,%s,'SELECT'),"
                    "NOT has_table_privilege('empiredb_app',%s,'SELECT'),"
                    "NOT has_table_privilege('empiredb_readonly',%s,'SELECT'),"
                    "NOT has_table_privilege('public',%s,'SELECT')",
                    (module.WRITER,name,name,name,name),
                ).fetchone()
                if acl!=(True,)*4:
                    raise RuntimeError("TABLE_ACL_HOLD")
                stage="RLS_ZERO_ROW_ACCESS"
                conn.execute("SELECT 1 FROM "+name+" LIMIT 0")
            conn.rollback()
        stage="SUCCESS"
        return {
            "status":"CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_PASS",
            "first_failing_stage":"NONE",
            "production_database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }
    except Exception:
        return {
            "status":"CONSUMER_PRIVATE_IDENTITY_DIAGNOSTIC_HOLD",
            "first_failing_stage":stage if stage in STAGES else "UNKNOWN",
            "production_database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print('{"status":"CONSUMER_DIAGNOSTIC_EXPLICIT_READ_ONLY_REQUIRED"}')
        return 3
    result=diagnosed_readonly()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"].endswith("_PASS") else 3


if __name__=="__main__":
    raise SystemExit(main())
