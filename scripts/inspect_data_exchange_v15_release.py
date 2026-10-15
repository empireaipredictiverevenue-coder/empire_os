"""Read-only privileged reconciliation of a partially attempted V15 release.

No writes, locks, credential printing, role changes or service starts.
Reports safe booleans and error *types* only. Run from canonical checkout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from scripts import deploy_data_exchange_custody_v15 as deploy

SCHEMA="empire.data_exchange.v15.release_reconciliation.v1"


def classify(call):
    try:
        return call(), None
    except Exception as exc:
        return None, type(exc).__name__


def inspect() -> dict:
    report={
        "schema_version":SCHEMA,
        "mode":"READ_ONLY",
        "database_writes":False,
        "service_started":False,
        "migration_attempted":False,
        "passwords_or_dsns_disclosed":False,
        "production_state":"UNDETERMINED",
    }
    if os.geteuid() != 0:
        report["reason_code"]="ROOT_READONLY_INSPECTION_REQUIRED"
        return report
    release, err=classify(deploy.checked_schema)
    report["release_sql_exact_match"]=release is not None
    if err:
        report["release_sql_check_error_type"]=err
    # No risk from reading existence using authorised root.
    report["runtime_env_exists"]=deploy.ENV_FILE.exists()
    report["service_unit_exists"]=deploy.UNIT_FILE.exists()
    report["service_unit_symlink"]=deploy.UNIT_FILE.is_symlink()
    root=deploy.BACKUP_ROOT
    report["protected_backup_root_exists"]=root.is_dir()
    if root.is_dir():
        try:
            backups=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]
            report["backup_attempt_count"]=len(backups)
            report["any_completed_backup_sha_manifest"]=any(
                (p/"backup-sha256.json").is_file() for p in backups
            )
            report["any_release_receipt"]=any(
                (p/"v15-production-receipt.json").is_file() for p in backups
            )
        except OSError as e:
            report["backup_inspection_error_type"]=type(e).__name__
    ident, err=classify(lambda: deploy.postgresql(
        "SELECT current_database()||'|'||current_setting('data_directory')"
        "||'|'||pg_is_in_recovery()"))
    report["canonical_db_identity_verified"] = (
        ident == "empiredb|/var/lib/postgresql/18/main|f")
    if err:
        report["canonical_db_probe_error_type"]=err
    app,err=classify(deploy.application_same_database)
    report["app_dsn_same_pg_instance"]=app is True
    if err:
        report["app_identity_error_type"]=err
    state,err=classify(lambda: deploy.postgresql(
        "SELECT (to_regclass('public.empire_data_exchange_observations') IS NOT NULL)::int"
        "||'|'||(SELECT count(*) FROM pg_roles WHERE rolname IN "
        "('empire_data_exchange_custodian','empire_data_exchange_custody_login'))"))
    if err:
        report["schema_role_probe_error_type"]=err
    else:
        report["custody_table_exists"]=state.split("|")[0]=="1"
        report["dedicated_role_count"]=int(state.split("|")[1])
    # Use the service manager only for passive observation.
    service,serr=classify(lambda: subprocess.run(
        ["systemctl", "show", "empire-data-exchange-custody-capture.service",
         "-p", "LoadState", "-p", "ActiveState", "-p", "Result",
         "--no-pager"], capture_output=True, text=True, timeout=5, check=True,
    ).stdout)
    if serr:
        report["service_inspection_error_type"]=serr
    elif service:
        report["systemd_load_state"]=next((
            line.partition("=")[2] for line in service.splitlines()
            if line.startswith("LoadState=")), "unknown")
        report["systemd_active_state"]=next((
            line.partition("=")[2] for line in service.splitlines()
            if line.startswith("ActiveState=")), "unknown")
        report["systemd_result"]=next((
            line.partition("=")[2] for line in service.splitlines()
            if line.startswith("Result=")), "unknown")
    exists=report.get("custody_table_exists")
    roles=report.get("dedicated_role_count")
    if exists is False and roles==0 and not report["runtime_env_exists"] and not report["service_unit_exists"]:
        report["production_state"]="NO_V15_SCHEMA_OR_SERVICE_OBSERVED"
        report["safe_to_reconcile"]="NEEDS_PREDEPLOY_CAUSE_DIAGNOSIS"
    elif exists is True or (isinstance(roles,int) and roles>0) or report["runtime_env_exists"] or report["service_unit_exists"]:
        report["production_state"]="PARTIAL_OR_COMPLETE_INSTALL_NEEDS_READBACK"
        report["safe_to_reconcile"]="DO_NOT_RETRY_APPLY"
        # Count only, no source payloads or individual contact information.
        if exists:
            count,cerr=classify(lambda: deploy.postgresql(
                "SELECT count(*) FROM public.empire_data_exchange_observations"))
            if not cerr and count and count.isdigit():
                report["canonical_observation_row_count"]=int(count)
            elif cerr:
                report["row_count_error_type"]=cerr
    return report


def main(argv=None):
    from argparse import ArgumentParser
    p=ArgumentParser()
    p.add_argument("--read-only",action="store_true")
    a=p.parse_args(argv)
    if not a.read_only:
        print(json.dumps({"schema_version":SCHEMA,"reason_code":"EXPLICIT_READ_ONLY_FLAG_REQUIRED","mode":"READ_ONLY"},sort_keys=True))
        return 2
    try:
        result=inspect()
    except Exception as exc:
        result={"schema_version":SCHEMA,"mode":"READ_ONLY",
                "status":"HOLD","error_type":type(exc).__name__,
                "database_writes":False}
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("production_state")!="UNDETERMINED" else 2


if __name__=="__main__":
    raise SystemExit(main())
