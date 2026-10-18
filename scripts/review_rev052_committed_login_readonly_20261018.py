#!/usr/bin/env python3
"""Redacted production REV052 post-commit reconciliation.

Explicitly read-only. Does NOT rerun provisioning, repair a role, change HBA,
rotate password, read any real commercial event, or expose secrets/SQL errors.
Use --read-only on the authorised EmpireOS host as root.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
from typing import Any, Callable

from scripts.provision_revenue_event_evidence_login_20261018 import (
    DB,LOGIN,ROLE,TENANT,VAULT,PASSFILE,pg,role_name_text
)

EXPECTED_ABSENT_UUID = "00000000-0000-4000-8000-000000000000"
SCHEMA = "empire.rev052.committed_login_reconciliation.v1"

# Catalogue metadata and one existing tenant binding only; no commercial rows.
CATALOG_SQL = f"""BEGIN READ ONLY;
SET LOCAL statement_timeout='5000ms';
SELECT pg_catalog.jsonb_build_object(
 'correct_db',current_database()='empiredb' AND NOT pg_is_in_recovery(),
 'login_exists',
   EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}'),
 'login_no_admin_noinherit',
   EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='{LOGIN}'
      AND rolcanlogin AND NOT rolinherit AND NOT rolsuper
      AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication
      AND NOT rolbypassrls),
 'credential_is_scram',
   EXISTS(SELECT 1 FROM pg_catalog.pg_authid
      WHERE rolname='{LOGIN}' AND
        rolpassword LIKE 'SCRAM-SHA-256$%'),
 'capability_is_nologin',
   EXISTS(SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname='{ROLE}' AND NOT rolcanlogin
      AND NOT rolsuper AND NOT rolbypassrls),
 'exact_set_only_grant',
   (SELECT count(*)=1 FROM pg_catalog.pg_auth_members am
      WHERE am.member=pg_catalog.to_regrole('{LOGIN}')
        AND am.roleid=pg_catalog.to_regrole('{ROLE}')
        AND am.set_option AND NOT am.inherit_option
        AND NOT am.admin_option),
 'no_other_granted_memberships',
   NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members am
      WHERE am.member=pg_catalog.to_regrole('{LOGIN}')
        AND am.roleid<>pg_catalog.to_regrole('{ROLE}')),
 'tenant_binding_exactly_one',
   (SELECT count(*)=1 FROM public.empire_tenant_role_bindings b
     WHERE b.role_name='{LOGIN}' AND b.tenant_id='{TENANT}'::uuid
       AND b.active AND nullif(btrim(b.evidence_ref),'') IS NOT NULL),
 'tenant_binding_no_extra_rows',
   (SELECT count(*)=1 FROM public.empire_tenant_role_bindings b
     WHERE b.role_name='{LOGIN}'),
 'function_exists',pg_catalog.to_regprocedure(
  'public.read_predictive_revenue_event_v1(uuid,text)') IS NOT NULL,
 'capability_function_execute',
   pg_catalog.has_function_privilege('{ROLE}',
     'public.read_predictive_revenue_event_v1(uuid,text)','EXECUTE'),
 'login_no_commercial_select',
   NOT pg_catalog.has_table_privilege('{LOGIN}','public.commercial_events','SELECT'),
 'login_no_orders_select',
   NOT pg_catalog.has_table_privilege('{LOGIN}','public.fulfilment_orders','SELECT'),
 'login_no_buyers_select',
   NOT pg_catalog.has_table_privilege('{LOGIN}','public.buyers','SELECT'),
 'hba_specific_scram_rule_configured',
   EXISTS(SELECT 1 FROM pg_catalog.pg_hba_file_rules h
    WHERE h.type='local' AND h.database=ARRAY['empiredb']::text[]
      AND h.user_name=ARRAY['{LOGIN}']::text[]
      AND h.auth_method='scram-sha-256' AND h.error IS NULL),
 'hba_no_parse_errors',
   NOT EXISTS(SELECT 1 FROM pg_catalog.pg_hba_file_rules WHERE error IS NOT NULL)
)::text;
ROLLBACK;"""


def private_password() -> str:
    """Inspect only server-root-owned 0600 custody; never reveal its content."""
    ds=VAULT.lstat()
    fs=PASSFILE.lstat()
    if (not stat.S_ISDIR(ds.st_mode) or ds.st_uid!=0
        or stat.S_IMODE(ds.st_mode)!=0o700
        or not stat.S_ISREG(fs.st_mode) or fs.st_uid!=0
        or stat.S_IMODE(fs.st_mode)!=0o600):
        raise RuntimeError("CREDENTIAL_CUSTODY_UNSAFE")
    flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW
    fd=os.open(PASSFILE,flags)
    try:
        content=os.read(fd,4096)
        if os.read(fd,1):
            raise RuntimeError("CREDENTIAL_FILE_OVERSIZED")
    finally:
        os.close(fd)
    # Strict one-line .pgpass format; no logging of password or connection DSN.
    lines=content.decode("ascii").splitlines()
    prefix=f"/var/run/postgresql:5432:empiredb:{LOGIN}:"
    if len(lines)!=1 or not lines[0].startswith(prefix):
        raise RuntimeError("CREDENTIAL_FILE_FORMAT_INVALID")
    pw=lines[0][len(prefix):]
    if (len(pw)<32 or any(c in pw for c in ("\\",":","\n","\r"," "))):
        raise RuntimeError("CREDENTIAL_FILE_PASSWORD_INVALID")
    return pw


def bounded_auth_probe(password:str, *, connector:Callable[...,Any]|None=None)->dict[str,Any]:
    """Same live-login check, now with explicit redacted stage/SQLSTATE."""
    if connector is None:
        import psycopg
        connector=psycopg.connect
    stage="AUTHENTICATION"
    results:dict[str,Any]={
        "auth_connection_verified":False,
        "session_login_identity_verified":False,
        "login_has_no_direct_source_table_select":False,
        "capability_set_role_verified":False,
        "capability_function_execute_verified":False,
        "sentinel_zero_result_verified":False,
        "real_event_selected":False,
    }
    try:
        with connector(
            host="/var/run/postgresql",port=5432,dbname=DB,user=LOGIN,
            password=password,connect_timeout=5,
        ) as conn:
            results["auth_connection_verified"]=True
            with conn.cursor() as cur:
                stage="READ_ONLY_SESSION"
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='3000ms'")
                stage="LOGIN_PRIVILEGES"
                row=cur.execute(
                    "SELECT session_user::text,current_user::text,"
                    "pg_catalog.has_table_privilege(session_user,"
                    "'public.commercial_events','SELECT'),"
                    "pg_catalog.has_table_privilege(session_user,"
                    "'public.fulfilment_orders','SELECT'),"
                    "pg_catalog.has_table_privilege(session_user,"
                    "'public.buyers','SELECT')"
                ).fetchone()
                if (row is None or len(row)!=5):
                    results["failure_stage"]="LOGIN_PRIVILEGES_SHAPE"
                    return results
                results["session_login_identity_verified"]=(
                    role_name_text(row[0])==LOGIN and
                    role_name_text(row[1])==LOGIN)
                results["login_has_no_direct_source_table_select"]=(
                    row[2:] == (False,False,False)
                )
                if not (results["session_login_identity_verified"]
                        and results["login_has_no_direct_source_table_select"]):
                    results["failure_stage"]="LOGIN_IDENTITY_OR_PRIVILEGE_DRIFT"
                    return results
                stage="SET_CAPABILITY_ROLE"
                cur.execute("SET LOCAL ROLE "+ROLE)
                user=cur.execute(
                    "SELECT session_user::text,current_user::text"
                ).fetchone()
                results["capability_set_role_verified"]=(
                    user is not None and len(user)==2 and
                    role_name_text(user[0])==LOGIN and
                    role_name_text(user[1])==ROLE)
                if not results["capability_set_role_verified"]:
                    results["failure_stage"]="CAPABILITY_ROLE_NOT_SET"
                    return results
                stage="FUNCTION_EXECUTE_PRIVILEGE"
                privilege=cur.execute(
                    "SELECT pg_catalog.has_function_privilege("
                    "current_user,'public.read_predictive_revenue_event_v1(uuid,text)',"
                    "'EXECUTE')"
                ).fetchone()
                results["capability_function_execute_verified"]=(
                    privilege==(True,))
                if not results["capability_function_execute_verified"]:
                    results["failure_stage"]="FUNCTION_EXECUTE_PRIVILEGE_DENIED"
                    return results
                stage="SENTINEL_FUNCTION_READONLY"
                row=cur.execute(
                    "SELECT count(*) FROM public.read_predictive_revenue_event_v1("
                    "%s::uuid,%s::text)",
                    (EXPECTED_ABSENT_UUID,TENANT)
                ).fetchone()
                results["sentinel_zero_result_verified"]=(row==(0,))
                if not results["sentinel_zero_result_verified"]:
                    results["failure_stage"]="SENTINEL_UNEXPECTED_COUNT"
                    return results
                results["failure_stage"]="NONE"
                return results
    except Exception as exc:
        # SQLSTATE only, never raw exception (may include SQL, DSN, credentials).
        state=getattr(exc,"sqlstate",None)
        results["failure_stage"]=stage
        results["sqlstate"]=state if (
            isinstance(state,str) and len(state)==5 and state.isalnum()
        ) else "UNAVAILABLE"
        return results


def review(*,admin_query:Callable[[str],str]=pg,
           password_reader:Callable[[],str]=private_password,
           connector:Callable[...,Any]|None=None) -> dict[str,Any]:
    out:dict[str,Any]={
        "schema_version":SCHEMA,"mode":"OBSERVE","read_only":True,
        "production_writes":False,"password_printed":False,
        "real_financial_events_read":0,"customer_report_release":False,
        "status":"HOLD_REV052_POST_COMMIT_NOT_VERIFIED"
    }
    try:
        text=admin_query(CATALOG_SQL)
        catalog=json.loads(text)
        if not isinstance(catalog,dict):
            raise ValueError("CATALOG_NOT_OBJECT")
    except Exception:
        out["failure_stage"]="ADMIN_CATALOG_READONLY"
        return out
    out["catalog_checks"]={k:(v is True) for k,v in sorted(catalog.items())}
    if not all(out["catalog_checks"].values()):
        out["failure_stage"]="CATALOG_PREREQUISITES"
        return out
    try:
        pw=password_reader()
    except Exception:
        out["failure_stage"]="PRIVATE_CREDENTIAL_CUSTODY"
        return out
    probe=bounded_auth_probe(pw,connector=connector)
    out["auth_checks"]={k:v for k,v in probe.items() if isinstance(v,bool)}
    if probe.get("sqlstate"):
        out["sqlstate"]=probe["sqlstate"]
    out["failure_stage"]=probe.get("failure_stage","UNKNOWN")
    if (probe.get("failure_stage")=="NONE" and
        probe.get("sentinel_zero_result_verified") is True and
        all(v for k,v in out["auth_checks"].items()
            if k!="real_event_selected")):
        out["status"]="REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED"
    return out


def main(argv:list[str]|None=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    if os.geteuid()!=0:
        print(json.dumps({"status":"HOLD_ROOT_READONLY_REQUIRED"}))
        return 2
    report=review()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
