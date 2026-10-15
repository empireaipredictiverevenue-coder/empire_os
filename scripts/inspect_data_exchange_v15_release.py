"""Read-only privileged reconciliation of a partially attempted V15 release.

No writes, locks, credential printing, role changes or service starts.
Reports safe booleans and error *types* only. Run from canonical checkout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys

from scripts import deploy_data_exchange_custody_v15 as deploy

SCHEMA="empire.data_exchange.v15.release_reconciliation.v1"


def classify(call):
    try:
        return call(), None
    except Exception as exc:
        return None, type(exc).__name__


def _connection_failure_class(exc: Exception) -> str:
    """Allowlist classification only; never print libpq error details."""
    message = str(exc).lower()
    if "permission denied for database" in message:
        return "LOGIN_DATABASE_CONNECT_DENIED"
    if "no pg_hba.conf entry" in message:
        return "LOGIN_HBA_NO_MATCH"
    if "password authentication failed" in message:
        return "LOGIN_PASSWORD_AUTH_FAILED"
    if "role" in message and "does not exist" in message:
        return "LOGIN_ROLE_ABSENT"
    if "connection refused" in message:
        return "LOCAL_POSTGRES_CONNECTION_REFUSED"
    if "timeout" in message:
        return "LOCAL_POSTGRES_CONNECTION_TIMEOUT"
    return "LOGIN_CONNECTION_REJECTED_OTHER"


def protected_dsn() -> str:
    """Read the root-owned dedicated DSN in memory only, never disclose it."""
    from psycopg.conninfo import conninfo_to_dict
    env=deploy.ENV_FILE
    if not env.is_file() or env.is_symlink():
        raise ValueError("dedicated runtime environment missing")
    info=env.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError("dedicated environment must be root-owned 0600")
    tokens = [shlex.split(line, posix=True) for line
              in env.read_text(encoding="utf-8").splitlines() if line.strip()]
    assignments={}
    for token in tokens:
        if len(token)!=1 or "=" not in token[0]:
            raise ValueError("invalid protected environment")
        key,value=token[0].split("=",1)
        if key in assignments:
            raise ValueError("duplicate protected key")
        assignments[key]=value
    dsn=assignments.get("EMPIRE_DATA_EXCHANGE_CUSTODIAN_DSN","")
    opts=conninfo_to_dict(dsn)
    if (opts.get("user") != deploy.LOGIN
        or opts.get("dbname") != "empiredb"
        or opts.get("host") != "127.0.0.1"
        or opts.get("port") != "5432"
        or not opts.get("password")):
        raise ValueError("dedicated connection identity mismatch")
    return dsn


def _probe_dedicated_connection() -> dict:
    """Root-only inspection; never return connection options or secrets."""
    from psycopg import connect
    result={"dedicated_env_secure":False,
            "dedicated_login_connection_status":"NOT_PROBED"}
    if not deploy.ENV_FILE.is_file() or deploy.ENV_FILE.is_symlink():
        return result
    result["dedicated_env_secure"]=(
        deploy.ENV_FILE.stat().st_uid==0
        and stat.S_IMODE(deploy.ENV_FILE.stat().st_mode)==0o600)
    try:
        dsn=protected_dsn()
        with connect(dsn,connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL ROLE empire_data_exchange_custodian")
                cur.execute("SELECT current_database()")
                if cur.fetchone() != ("empiredb",):
                    raise ValueError("database mismatch")
                cur.execute("SELECT count(*) FROM public.empire_data_exchange_observations")
                count=cur.fetchone()[0]
        result["dedicated_login_connection_status"]="AUTHENTICATED_READ_ONLY"
        result["dedicated_login_row_count"]=int(count)
    except Exception as exc:
        result["dedicated_login_connection_status"]=_connection_failure_class(exc)
        result["dedicated_login_exception_type"]=type(exc).__name__
    return result


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
    ident, err=classify(lambda: deploy.postgresql(deploy.DB_IDENTITY_SQL))
    report["canonical_db_identity_verified"] = (
        ident == deploy.EXPECTED_DB_IDENTITY)
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
    if report.get("dedicated_role_count") == 2:
        privileges, perr=classify(lambda: deploy.postgresql(
            "SELECT (has_database_privilege('empire_data_exchange_custody_login',"
            "'empiredb','CONNECT'))::text||'|'||"
            "(has_schema_privilege('empire_data_exchange_custodian',"
            "'public','USAGE'))::text||'|'||"
            "(has_table_privilege('empire_data_exchange_custodian',"
            "'public.empire_data_exchange_observations','SELECT,INSERT'))::text"
        ))
        if perr:
            report["custody_privilege_check_error_type"]=perr
        elif privileges in ("true|true|true","false|true|true",
                            "true|false|true","true|true|false",
                            "false|false|false"):
            connect,usage,table=privileges.split("|")
            report["custody_login_database_connect"]=connect=="true"
            report["custody_role_schema_usage"]=usage=="true"
            report["custody_role_table_select_insert"]=table=="true"
        else:
            report["custody_privilege_status"]="UNRECOGNISED_HOLD"
    if report["runtime_env_exists"]:
        probe,probe_error=classify(_probe_dedicated_connection)
        if probe_error:
            report["dedicated_auth_probe_error_type"]=probe_error
        else:
            report.update(probe)
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
