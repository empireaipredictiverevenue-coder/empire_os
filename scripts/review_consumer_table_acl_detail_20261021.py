#!/usr/bin/env python3
"""Exact consumer table ACL isolate: root-only and READ-ONLY.

Do not write, change, or expose credentials, subscriber rows, role memberships,
HBA, defaults, or service state. Output only allowlisted catalog booleans
for the five specific consumer tables, plus the first failing permission.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import psycopg

ROOT_SOURCE=Path("/usr/local/lib/empire-os/private-consumer/review_consumer_private_identity_session_20261021.py")
ROOT_SOURCE_SHA256="7799c81a37a0806a370a710a20ea32f59304ce7fb30e5c0d69feb031056aac42"
LABELS=("writer_select","crm_app_select_denied",
        "crm_readonly_select_denied","public_select_denied")


def _trusted_source():
    st=ROOT_SOURCE.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid!=0
        or stat.S_IMODE(st.st_mode)!=0o500 or st.st_nlink!=1):
        raise RuntimeError("SOURCE_CUSTODY_HOLD")
    if hashlib.sha256(ROOT_SOURCE.read_bytes()).hexdigest()!=ROOT_SOURCE_SHA256:
        raise RuntimeError("SOURCE_CHECKSUM_HOLD")
    spec=importlib.util.spec_from_file_location("consumer_acl_original",ROOT_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("SOURCE_LOAD_HOLD")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _report_for_table(row, table: str) -> dict:
    # This returns catalog privilege booleans for named static roles only.
    # It is never allowed to report subscriber data, keys or SQL errors.
    if not isinstance(row,(tuple,list)) or len(row)!=4 or any(type(x) is not bool for x in row):
        return {"table":table,"status":"ACL_RESULT_INVALID"}
    failures=[name for name,passed in zip(LABELS,row) if passed is not True]
    return {
        "table":table,
        "status":"PASS" if not failures else "HOLD",
        "writer_select":row[0],
        "crm_app_select_denied":row[1],
        "crm_readonly_select_denied":row[2],
        "public_select_denied":row[3],
        "failed_checks":failures,
    }


def diagnostic(*, original=None, connect=psycopg.connect) -> dict:
    stage="SOURCE"
    current_table=None
    try:
        if os.geteuid()!=0:
            raise RuntimeError("ROOT_REQUIRED")
        original=original or _trusted_source()
        stage="VAULT"
        password,_=original.read_custody()
        stage="LOGIN"
        with connect(
            dbname=original.DB,host="127.0.0.1",port=5432,
            user=original.LOGIN,password=password,connect_timeout=5,
            application_name="empire_consumer_acl_readonly_diagnostic"
        ) as conn:
            del password
            stage="READ_ONLY_TX"
            conn.execute("SET TRANSACTION READ ONLY")
            identity=conn.execute(
                "SELECT session_user,current_user,current_database(),"
                "current_setting('transaction_read_only')"
            ).fetchone()
            if identity!=(original.LOGIN,original.LOGIN,original.DB,"on"):
                raise RuntimeError("WRONG_LOGIN")
            stage="SET_LOCAL_ROLE"
            conn.execute("SET LOCAL ROLE "+original.WRITER)
            identity=conn.execute(
                "SELECT session_user,current_user,current_database(),"
                "current_setting('transaction_read_only')"
            ).fetchone()
            if identity!=(original.LOGIN,original.WRITER,original.DB,"on"):
                raise RuntimeError("WRONG_WRITER")
            reports=[]
            for table in original.TABLES:
                if table not in (
                    "empire_consumer_subscriptions",
                    "empire_consumer_consent_events",
                    "empire_consumer_email_suppressions",
                    "empire_consumer_one_time_tokens",
                    "empire_consumer_delivery_receipts"
                ):
                    raise RuntimeError("UNEXPECTED_TABLE_NAME")
                current_table=table
                stage="TABLE_ACL"
                name="public."+table
                row=conn.execute(
                    "SELECT has_table_privilege(%s,%s,'SELECT'),"
                    "NOT has_table_privilege('empiredb_app',%s,'SELECT'),"
                    "NOT has_table_privilege('empiredb_readonly',%s,'SELECT'),"
                    "NOT has_table_privilege('public',%s,'SELECT')",
                    (original.WRITER,name,name,name,name),
                ).fetchone()
                entry=_report_for_table(row,table)
                reports.append(entry)
            conn.rollback()
        failed=next((entry for entry in reports if entry["status"]!="PASS"),None)
        return {
            "status":"CONSUMER_ACL_READONLY_PASS" if failed is None else "CONSUMER_ACL_READONLY_HOLD",
            "first_failed_table":failed["table"] if failed is not None else "NONE",
            "first_failed_checks":failed.get("failed_checks",[]) if failed else [],
            "table_checks":reports,
            "production_database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }
    except Exception as err:
        state={
            "status":"CONSUMER_ACL_READONLY_HOLD",
            "first_failed_stage":stage,
            "first_failed_table":current_table or "NONE",
            "production_database_modified":False,
            "subscriber_rows_fetched":False,
            "email_sent":False,
        }
        # A standard SQLSTATE is a public error *category*; no SQL text,
        # original exception detail, role/password or personal data is shown.
        sqlstate=getattr(err,"sqlstate",None)
        if sqlstate in ("42704","42501","42P01","42883","42601"):
            state["sqlstate"]=sqlstate
        return state


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args(argv)
    if not args.read_only:
        print('{"status":"CONSUMER_ACL_READONLY_ONLY"}')
        return 3
    response=diagnostic()
    print(json.dumps(response,sort_keys=True))
    return 0 if response["status"]=="CONSUMER_ACL_READONLY_PASS" else 3


if __name__=="__main__":
    raise SystemExit(main())
