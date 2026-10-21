#!/usr/bin/env python3
"""One final nonmutating authority check for the actual consumer login.

A restricted consumer login must NOT inspect the effective privileges of
unrelated CRM principals. Separate checks into:
 (1) original postgres peer => DB/ACL authority review, READ ONLY;
 (2) original scoped login => credential and zero-row RLS access, READ ONLY.
No service launch, outgoing message, subscriber-row retrieval or credential
disclosure. Never infer that a 42501 error authorizes REVOKE/GRANT.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess

import psycopg

DB="empiredb"
LOGIN="empire_consumer_optin_login"
WRITER="empire_consumer_optin_writer"
ORIGINAL=Path("/usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py")
ORIGINAL_SHA256="7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42"
TABLES=(
    "empire_consumer_subscriptions","empire_consumer_consent_events",
    "empire_consumer_email_suppressions","empire_consumer_one_time_tokens",
    "empire_consumer_delivery_receipts",
)
POLICIES=(
    "consumer_writer_subscriptions","consumer_writer_consent_events",
    "consumer_writer_suppressions","consumer_writer_tokens",
    "consumer_writer_delivery"
)
PREFIX="/usr/local/lib/empire-os/private-consumer"

# Superuser checks of *other* roles must be isolated from the consumer
# login; pg_catalog.has_table_privilege is used under original DBA identity.
ADMIN_SQL="""
BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT pg_catalog.jsonb_build_object(
 'correct_database',current_database()='empiredb' AND NOT pg_is_in_recovery(),
 'five_forced_rls_owned_tables',(
  SELECT count(*)=5 FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname=ANY(ARRAY[
   'empire_consumer_subscriptions','empire_consumer_consent_events',
   'empire_consumer_email_suppressions','empire_consumer_one_time_tokens',
   'empire_consumer_delivery_receipts'])
   AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity
   AND c.relowner='empiredb_migrator'::pg_catalog.regrole),
 'exact_scoped_policies',(
  SELECT count(*)=5 FROM pg_catalog.pg_policies
  WHERE schemaname='public' AND policyname=ANY(ARRAY[
   'consumer_writer_subscriptions','consumer_writer_consent_events',
   'consumer_writer_suppressions','consumer_writer_tokens',
   'consumer_writer_delivery'])),
 'login_restricted',EXISTS(
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_consumer_optin_login'
   AND rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls
   AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
   AND rolconnlimit=5),
 'writer_restricted',EXISTS(
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_consumer_optin_writer'
   AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper AND NOT rolbypassrls
   AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication),
 'writer_public_schema_usage',
    pg_catalog.has_schema_privilege(
      'empire_consumer_optin_writer','public','USAGE'),
 'exact_one_writer_membership',(
  SELECT count(*)=1 AND COALESCE(bool_and(
   r.rolname='empire_consumer_optin_writer'
    AND m.set_option AND NOT m.inherit_option AND NOT m.admin_option
  ),false) FROM pg_catalog.pg_auth_members m
  JOIN pg_catalog.pg_roles u ON u.oid=m.member
  JOIN pg_catalog.pg_roles r ON r.oid=m.roleid
  WHERE u.rolname='empire_consumer_optin_login'),
 'table_acl',(
  SELECT pg_catalog.jsonb_agg(
    pg_catalog.jsonb_build_object(
      'name', t.name,
      'writer_select',pg_catalog.has_table_privilege(
        'empire_consumer_optin_writer', 'public.'||t.name,'SELECT'),
      'crm_denied',NOT pg_catalog.has_table_privilege(
        'empiredb_app','public.'||t.name,'SELECT'),
      'readonly_denied',NOT pg_catalog.has_table_privilege(
        'empiredb_readonly','public.'||t.name,'SELECT'),
      'public_denied',NOT pg_catalog.has_table_privilege(
        'public','public.'||t.name,'SELECT'))
  ) FROM (VALUES
   ('empire_consumer_subscriptions'),('empire_consumer_consent_events'),
   ('empire_consumer_email_suppressions'),('empire_consumer_one_time_tokens'),
   ('empire_consumer_delivery_receipts')) t(name)
 )
)::text;
ROLLBACK;
"""


def _original_source():
    st=ORIGINAL.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0
        or stat.S_IMODE(st.st_mode)!=0o500 or st.st_nlink!=1):
        raise RuntimeError("ORIGINAL_SOURCE_CUSTODY_HOLD")
    if hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()!=ORIGINAL_SHA256:
        raise RuntimeError("ORIGINAL_SOURCE_DIGEST_HOLD")
    spec=importlib.util.spec_from_file_location("original_consumer_verifier",ORIGINAL)
    if not spec or not spec.loader:
        raise RuntimeError("ORIGINAL_SOURCE_LOAD_HOLD")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _admin_original() -> dict:
    result=subprocess.run(
        ["/usr/sbin/runuser","-u","postgres","--","/usr/bin/psql",
         "-X","-q","-w","-A","-t","-v","ON_ERROR_STOP=1",
         "-h","/var/run/postgresql","-p","5432",
         "-U","postgres","-d",DB],
        input=ADMIN_SQL,text=True,capture_output=True,timeout=20,
        env={"HOME":"/var/lib/postgresql","PATH":"/usr/bin:/bin"},
    )
    if result.returncode:
        raise RuntimeError("ADMIN_CATALOG_QUERY_HOLD")
    return json.loads(result.stdout.strip())


def _validated_admin_acl(state: dict) -> tuple[bool,dict]:
    expected=(
        "correct_database","five_forced_rls_owned_tables",
        "exact_scoped_policies","login_restricted","writer_restricted",
        "writer_public_schema_usage", "exact_one_writer_membership",
    )
    checks={name:state.get(name) is True for name in expected}
    details=state.get("table_acl")
    if not isinstance(details,list) or len(details)!=5:
        return False,{"checks":checks,"tables":"INVALID"}
    static={x:None for x in TABLES}
    entries={}
    for item in details:
        if not isinstance(item,dict) or item.get("name") not in static:
            return False,{"checks":checks,"tables":"INVALID"}
        name=item["name"]
        if name in entries:
            return False,{"checks":checks,"tables":"INVALID"}
        entries[name]={
            name_:item.get(name_) is True for name_ in (
                "writer_select","crm_denied","readonly_denied","public_denied")
        }
    if set(entries)!=set(TABLES):
        return False,{"checks":checks,"tables":"INVALID"}
    return (
        all(checks.values()) and all(all(row.values()) for row in entries.values()),
        {"checks":checks, "tables":entries},
    )


def _original_login_readonly(*, password: str, connect=psycopg.connect) -> dict:
    # Avoid asking a restricted consumer principal to evaluate unrelated role
    # access (which may raise 42501 under production privilege policies).
    # Only original consumer login and original scoped writer are tested.
    with connect(
        dbname=DB,host="127.0.0.1",port=5432,user=LOGIN,password=password,
        connect_timeout=5,application_name="empire_consumer_original_readonly"
    ) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        initial=conn.execute(
            "SELECT session_user,current_user,current_database(),"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if initial!=(LOGIN,LOGIN,DB,"on"):
            raise RuntimeError("LOGIN_OR_DATABASE_MISMATCH")
        conn.execute("SET LOCAL ROLE "+WRITER)
        active=conn.execute(
            "SELECT session_user,current_user,current_database(),"
            "current_setting('transaction_read_only')"
        ).fetchone()
        if active!=(LOGIN,WRITER,DB,"on"):
            raise RuntimeError("SCOPED_WRITER_ROLE_MISMATCH")
        for table in TABLES:
            relation="public."+table
            # Only one's OWN effective SELECT; independent superuser
            # catalog readback establishes the CRM/PUBLIC negatives.
            has_select=conn.execute(
                "SELECT has_table_privilege(current_user,%s,'SELECT')",
                (relation,),
            ).fetchone()
            if has_select!=(True,):
                raise RuntimeError("WRITER_SELECT_HOLD")
            conn.execute("SELECT 1 FROM "+relation+" LIMIT 0")
        conn.rollback()
    return {
        "login_scram_authenticated":True,
        "private_writer_role_assumed":True,
        "five_zero_row_rls_selects":True,
        "no_subscriber_rows_fetched":True,
    }


def check(*, original=None, admin=None, connect=psycopg.connect) -> dict:
    stage="ROOT"
    try:
        if os.geteuid()!=0:
            raise RuntimeError("ROOT_ONLY")
        stage="ORIGINAL_SOURCE"
        orig=original or _original_source()
        stage="ROOT_CUSTODY"
        secret,_=orig.read_custody()
        stage="ADMIN_ACL"
        state=admin() if admin is not None else _admin_original()
        passed,details=_validated_admin_acl(state)
        if not passed:
            return {
                "status":"CONSUMER_ROOT_ACL_HOLD",
                "step":"ADMIN_ACL",
                "catalogue":details,
                "service_activated":False,
                "database_modified":False,
                "subscriber_rows_fetched":False,
                "email_sent":False,
            }
        stage="SCOPED_LOGIN"
        scoped=_original_login_readonly(password=secret,connect=connect)
        del secret
        return {
            "status":"CONSUMER_ROOT_AND_LOGIN_READONLY_VERIFIED",
            "authoritative_admin_acl":True,
            "original_root_key_custody":True,
            "catalogue":details,
            **scoped,
            "service_activated":False,
            "database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }
    except Exception as err:
        # No SQL, secrets, DSN or personal data leave this process.
        safe_sqlstate=getattr(err,"sqlstate",None)
        res={
            "status":"CONSUMER_ROOT_READONLY_HOLD",
            "step":stage,
            "service_activated":False,
            "database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }
        if safe_sqlstate in ("42501","42P01","42704","42883","42601"):
            res["sqlstate"]=safe_sqlstate
        return res


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print('{"status":"CONSUMER_ROOT_READONLY_FLAG_REQUIRED"}')
        return 3
    result=check()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="CONSUMER_ROOT_AND_LOGIN_READONLY_VERIFIED" else 3


if __name__=="__main__":
    raise SystemExit(main())
