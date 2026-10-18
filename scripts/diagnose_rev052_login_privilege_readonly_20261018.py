#!/usr/bin/env python3
"""Evidence-only PostgreSQL 42501 isolation for existing REV052 login.

Never changes privileges, creates a login, resets a password or reads real
commercial-event rows. Checks connection, identity and privilege metadata
using read-only transactions/savepoints. No secrets, SQL, or raw DB errors
are emitted. Use sudo python -B -m scripts.diagnose_rev052_login_privilege_readonly_20261018 --read-only
"""
from __future__ import annotations
import argparse
import json
import os
from typing import Any, Callable

from scripts.provision_revenue_event_evidence_login_20261018 import (
    LOGIN, ROLE, TENANT, role_name_text,
)
from scripts.review_rev052_committed_login_readonly_20261018 import (
    private_password,
)

SCHEMA = "empire.rev052.login_privilege_denial_probe.v1"
ZERO_EVENT = "00000000-0000-4000-8000-000000000000"
# Whitelisted, read-only, single-value metadata queries.
PROBES = (
    ("identity", "SELECT session_user::text,current_user::text"),
    ("schema_public_usage", "SELECT pg_catalog.has_schema_privilege(session_user,'public','USAGE')"),
    ("raw_commercial_select", "SELECT pg_catalog.has_table_privilege(session_user,'public.commercial_events','SELECT')"),
    ("raw_orders_select", "SELECT pg_catalog.has_table_privilege(session_user,'public.fulfilment_orders','SELECT')"),
    ("raw_buyers_select", "SELECT pg_catalog.has_table_privilege(session_user,'public.buyers','SELECT')"),
)


def _code(exc: Exception) -> str:
    code = getattr(exc, "sqlstate", None)
    return code if isinstance(code, str) and len(code)==5 and code.isalnum() else "UNAVAILABLE"


def _bool_query(cur: Any, label: str, sql: str) -> dict[str, Any]:
    """One metadata query. Savepoints contain any 42501 transaction abort."""
    result: dict[str, Any]={"status":"HOLD"}
    try:
        cur.execute("SAVEPOINT rev052_probe")
        row = cur.execute(sql).fetchone()
        cur.execute("RELEASE SAVEPOINT rev052_probe")
        if row is None:
            result["reason"]="NO_METADATA_ROW"
            return result
        if label=="identity":
            result["status"]="PASS" if (
                len(row)==2 and
                role_name_text(row[0])==LOGIN and
                role_name_text(row[1])==LOGIN
            ) else "HOLD"
        elif len(row)==1 and type(row[0]) is bool:
            result["status"]="PASS"
            result["value"]=row[0]
        else:
            result["reason"]="UNEXPECTED_METADATA_SHAPE"
        return result
    except Exception as exc:
        result["reason"]="POSTGRES_PRIVILEGE_OR_QUERY_ERROR"
        result["sqlstate"]=_code(exc)
        # Leave transaction clean for the next metadata check, even if
        # the last SELECT was denied.
        try:
            cur.execute("ROLLBACK TO SAVEPOINT rev052_probe")
            cur.execute("RELEASE SAVEPOINT rev052_probe")
        except Exception:
            result["reason"]="ROLLBACK_TO_SAVEPOINT_FAILED"
            result["status"]="HOLD"
            raise RuntimeError("PROBE_TRANSACTION_UNRECOVERABLE") from None
        return result


def _session(password: str, *, connector: Callable[...,Any]|None=None) -> dict[str,Any]:
    if connector is None:
        import psycopg
        connector=psycopg.connect
    report: dict[str,Any]={
        "authenticated":False,
        "session_readonly":False,
        "role_set":False,
        "restricted_function_executable":False,
        "sentinel_only_no_real_event":True,
        "metadata":{},
        "stage":"CONNECT"
    }
    try:
        with connector(
            host="/var/run/postgresql", port=5432, dbname="empiredb",
            user=LOGIN, password=password, connect_timeout=5
        ) as conn:
            report["authenticated"]=True
            with conn.cursor() as cur:
                report["stage"]="SESSION_READ_ONLY"
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                report["session_readonly"]=True
                for label,sql in PROBES:
                    report["stage"]="PROBE_"+label.upper()
                    report["metadata"][label]=_bool_query(cur,label,sql)
                # Do not fail early on non-executable diagnostic ACL
                # expressions: admin catalogue already independently checked
                # all three source-table direct-read denials.
                report["stage"]="SET_CAPABILITY_ROLE"
                try:
                    cur.execute("SET LOCAL ROLE "+ROLE)
                    row=cur.execute(
                        "SELECT session_user::text,current_user::text"
                    ).fetchone()
                    report["role_set"]=(
                        row is not None and len(row)==2 and
                        role_name_text(row[0])==LOGIN and
                        role_name_text(row[1])==ROLE
                    )
                except Exception as exc:
                    report["sqlstate"]=_code(exc)
                    return report
                if not report["role_set"]:
                    report["stage"]="SET_CAPABILITY_ROLE_UNVERIFIED"
                    return report
                report["stage"]="SENTINEL_FUNCTION"
                try:
                    row=cur.execute(
                        "SELECT count(*) FROM public.read_predictive_revenue_event_v1("
                        "%s::uuid,%s::text)", (ZERO_EVENT,TENANT),
                    ).fetchone()
                    report["restricted_function_executable"]=row==(0,)
                    if not report["restricted_function_executable"]:
                        report["stage"]="SENTINEL_NOT_ZERO"
                        return report
                except Exception as exc:
                    report["sqlstate"]=_code(exc)
                    return report
                report["stage"]="DONE"
    except Exception as exc:
        report["sqlstate"]=_code(exc)
    return report


def diagnose(*, password_reader: Callable[[],str]=private_password,
             connector:Callable[...,Any]|None=None)->dict[str,Any]:
    out:dict[str,Any]={
        "schema_version":SCHEMA, "status":"HOLD_READER_42501_UNRESOLVED",
        "mode":"OBSERVE", "read_only":True, "database_writes":False,
        "permission_changes":False, "new_login_created":False,
        "credentials_disclosed":False, "real_event_rows_read":0,
        "customer_release_authorised":False
    }
    try:
        password=password_reader()
    except Exception:
        out["failure_stage"]="PRIVATE_CREDENTIAL_CUSTODY"
        return out
    result=_session(password,connector=connector)
    out["authenticated"]=result["authenticated"]
    out["session_readonly"]=result["session_readonly"]
    out["metadata"]=result["metadata"]
    out["role_set"]=result["role_set"]
    out["restricted_function_executable"]=result["restricted_function_executable"]
    out["stage"]=result["stage"]
    if "sqlstate" in result:
        out["sqlstate"]=result["sqlstate"]
    if (result["authenticated"] and result["session_readonly"] and
        result["role_set"] and result["restricted_function_executable"]):
        out["status"]="REV052_RESTRICTED_SESSION_FUNCTION_WORKS"
    return out


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status":"HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    if os.geteuid()!=0:
        print(json.dumps({"status":"HOLD_ROOT_LOCAL_READONLY_REQUIRED"}))
        return 2
    report=diagnose()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="REV052_RESTRICTED_SESSION_FUNCTION_WORKS" else 2


if __name__=="__main__":
    raise SystemExit(main())
