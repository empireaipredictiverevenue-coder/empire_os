"""Reconcile ONE previously-installed V15 EmpireDB custody release (no remigration).

Root-only, founder-approved OBSERVE scope. Requires two existing roles,
immutable guarded table, protected backup, original exact unit and protected
credentials. Can add ONLY login CONNECT for the dedicated custody identity.
Never modifies HBA/password, bypasses RLS, retries unknown capture, or
sends any outreach/payment/customer data.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess

from empire_os.data_exchange_custody_transport import EmpireDBConstructionCustody
from empire_os.data_exchange_observation_custody import verify_custody_window
from scripts import deploy_data_exchange_custody_v15 as dep
from scripts import inspect_data_exchange_v15_release as inspect

SCHEMA="empire.data_exchange.v15.partial_release_recovery.v1"
LOCK=Path("/run/lock/empire-data-exchange-v15.lock")


class RecoveryHold(RuntimeError):
    pass


def hold(message: str):
    raise RecoveryHold(message)


def validate_backup() -> Path:
    root=dep.BACKUP_ROOT
    if not root.is_dir() or root.is_symlink():
        hold("PROTECTED_RELEASE_BACKUP_MISSING")
    locations=[p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]
    if len(locations)!=1:
        hold("BACKUP_ATTEMPT_COUNT_NEEDS_REVIEW")
    backup=locations[0]
    manifest=backup/"backup-sha256.json"
    archive=backup/"empiredb-before-v15.dump"
    globals_file=backup/"postgres-globals-before-v15.sql"
    if not all(p.is_file() and not p.is_symlink() for p in (manifest,archive,globals_file)):
        hold("RELEASE_BACKUP_INCOMPLETE")
    expected=json.loads(manifest.read_text(encoding="utf-8"))
    if (expected.get("source_sql_sha256") != dep.SQL_HASH
        or expected.get("db_dump") != dep.checksum(archive)
        or expected.get("role_globals") != dep.checksum(globals_file)):
        hold("PROTECTED_BACKUP_HASH_MISMATCH")
    return backup


def precheck() -> dict:
    report=inspect.inspect()
    if (
        report.get("production_state")!="PARTIAL_OR_COMPLETE_INSTALL_NEEDS_READBACK"
        or report.get("canonical_db_identity_verified") is not True
        or report.get("app_dsn_same_pg_instance") is not True
        or report.get("release_sql_exact_match") is not True
        or report.get("custody_table_exists") is not True
        or report.get("dedicated_role_count") != 2
        or report.get("canonical_observation_row_count") != 0
        or report.get("runtime_env_exists") is not True
        or report.get("service_unit_exists") is not True
        or report.get("service_unit_symlink") is True
        or report.get("systemd_load_state")!="loaded"
        or report.get("systemd_active_state")!="inactive"
        or report.get("any_release_receipt") is True
        or report.get("custody_role_schema_usage") is not True
        or report.get("custody_role_table_select_insert") is not True
        or type(report.get("custody_login_database_connect")) is not bool
    ):
        hold("PREEXISTING_SCHEMA_OR_RUNTIME_STATE_NEEDS_MANUAL_RECONCILIATION")
    unit=dep.UNIT_FILE
    contents=unit.read_text(encoding="utf-8")
    info=unit.stat()
    if (
        info.st_uid!=0 or unit.is_symlink()
        or "User=ubuntu\n" not in contents
        or "Type=oneshot\n" not in contents
        or f"EnvironmentFile={dep.ENV_FILE}" not in contents
        or "ExecStart=/srv/empire_os/.venv/bin/python -m "
            "scripts.operate_data_exchange_observation_custody "
            "--append --approved-custody-only" not in contents
        or "ProtectSystem=strict\n" not in contents
        or any(extra in contents for extra in ("ExecStartPre=", "ExecStartPost=",
                                               "ExecStop=", "OnFailure=", ".timer"))
    ):
        hold("INSTALLED_ONESHOT_UNIT_MISMATCH")
    if not report.get("dedicated_env_secure"):
        hold("PROTECTED_CREDENTIAL_FILE_NOT_ROOT_0600")
    if dep.checked_schema() is None:
        hold("REVIEWED_SCHEMA_NOT_PRESENT")
    # Match the reviewed table security controls independently.
    controls=dep.postgresql(
        "SELECT (relrowsecurity AND relforcerowsecurity)::text||'|'||"
        "(SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal "
        "AND tgrelid='public.empire_data_exchange_observations'::regclass) "
        "FROM pg_class WHERE oid='public.empire_data_exchange_observations'::regclass"
    )
    if controls!="true|3":
        hold("CUSTODY_RLS_OR_IMMUTABILITY_DRIFT")
    memberships=dep.postgresql(
        "SELECT (SELECT count(*) FROM pg_auth_members m "
        "JOIN pg_roles member ON member.oid=m.member "
        "WHERE member.rolname='empire_data_exchange_custody_login')::text "
        "||'|'||(SELECT count(*) FROM pg_auth_members m "
        "JOIN pg_roles member ON member.oid=m.member "
        "JOIN pg_roles granted ON granted.oid=m.roleid "
        "WHERE member.rolname='empire_data_exchange_custody_login' "
        "AND granted.rolname='empire_data_exchange_custodian' "
        "AND NOT m.admin_option AND NOT m.inherit_option "
        "AND m.set_option)::text"
    )
    if memberships!="1|1":
        hold("DEDICATED_CUSTODY_ROLE_MEMBERSHIP_DRIFT")
    backup=validate_backup()
    report["backup_directory_validated"]=True
    report["backup_reference"]=backup
    return report


def grant_login_connect_once():
    """ONLY a narrowly named CONNECT grant after the full precheck."""
    sql="""
BEGIN;
SET LOCAL statement_timeout='5s';
DO $guard$
BEGIN
 IF current_database()<>'empiredb' OR pg_is_in_recovery() THEN
    RAISE EXCEPTION 'not canonical writable database';
 END IF;
 IF NOT EXISTS(
   SELECT 1 FROM pg_roles WHERE rolname='empire_data_exchange_custody_login'
     AND rolcanlogin AND NOT rolinherit AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) OR NOT EXISTS (
   SELECT 1 FROM pg_roles WHERE rolname='empire_data_exchange_custodian'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
     AND NOT rolbypassrls
 ) THEN
   RAISE EXCEPTION 'dedicated identity contract changed';
 END IF;
 IF pg_catalog.has_database_privilege('empire_data_exchange_custody_login',
                                      'empiredb','CONNECT') THEN
   RAISE EXCEPTION 'login CONNECT already granted; reconcile, do not retry';
 END IF;
 IF (SELECT count(*) FROM public.empire_data_exchange_observations)<>0 THEN
   RAISE EXCEPTION 'custody already contains an observation';
 END IF;
END;
$guard$;
GRANT CONNECT ON DATABASE empiredb TO empire_data_exchange_custody_login;
DO $check$
BEGIN
 IF NOT pg_catalog.has_database_privilege(
       'empire_data_exchange_custody_login','empiredb','CONNECT') THEN
   RAISE EXCEPTION 'login CONNECT did not commit';
 END IF;
END;
$check$;
COMMIT;
"""
    dep.postgresql(stdin_sql=sql,silent=True)


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply",action="store_true")
    p.add_argument(dep.APPROVAL,action="store_true")
    args=p.parse_args(argv)
    output={"schema_version":SCHEMA,"status":"HOLD",
            "scope":"FIRST_SOURCE_OBSERVATION_ONLY",
            "database_writes":False,
            "customer_delivery_enabled":False,"outbound_enabled":False,
            "payment_execution":False,"hba_changes":False,
            "password_rotation":False}
    phase="ROOT_AND_RELEASE_SCOPE"
    try:
        if not args.apply or not getattr(args,dep.APPROVAL.lstrip("-").replace("-","_")):
            hold("EXPLICIT_EXISTING_FOUNDER_RELEASE_SCOPE_REQUIRED")
        if os.geteuid()!=0:
            hold("AUTHORISED_ROOT_REQUIRED")
        if Path.cwd().resolve()!=dep.ROOT:
            hold("CANONICAL_CHECKOUT_REQUIRED")
        with LOCK.open("a+") as fd:
            try:
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                hold("ANOTHER_CUSTODY_RELEASE_OWNS_LOCK")
            phase="VERIFY_PREVIOUS_INSTALLATION"
            report=precheck()
            # Privilege repair is unnecessary if already connected.
            has_connect=report["custody_login_database_connect"]
            if not has_connect:
                phase="GRANT_DEDICATED_LOGIN_CONNECT_ONLY"
                grant_login_connect_once()
                output["database_writes"]=True
                output["dedicated_connect_grant_committed"]=True
            phase="VERIFY_DEDICATED_AUTH_AND_RLS_READ"
            live=inspect._probe_dedicated_connection()
            if live.get("dedicated_login_connection_status")!="AUTHENTICATED_READ_ONLY":
                output["dedicated_login_status"]=live.get("dedicated_login_connection_status","NOT_VERIFIED")
                hold("DEDICATED_LOGIN_AUTH_ROUTE_NOT_READY_NO_CAPTURE_ATTEMPT")
            if live.get("dedicated_login_row_count")!=0:
                hold("CUSTODY_OBSERVATION_ALREADY_EXISTS_NO_RESTART")
            # This is the first, and only, allowed service start in this
            # reconciliation. No timer install and no automatic retry.
            phase="FIRST_REAL_OFFICIAL_SOURCE_CAPTURE"
            started=subprocess.run(
                ["systemctl","start","empire-data-exchange-custody-capture.service"],
                capture_output=True,text=True,timeout=50)
            if started.returncode!=0:
                hold("ONE_SHOT_CAPTURE_FAILED_NO_AUTOMATIC_RETRY")
            phase="VERIFY_CANONICAL_READBACK"
            rows=EmpireDBConstructionCustody(inspect.protected_dsn()).read_window()
            if len(rows)!=1 or rows[0]["sequence"]!=0:
                hold("FIRST_CAPTURE_READBACK_UNVERIFIED_NO_RETRY")
            proof=verify_custody_window(rows)
            if (proof["head_chain_sha256"]!=rows[0]["chain_sha256"]
                or len(rows[0]["snapshot_json"].get("records",[]))!=3):
                hold("OBSERVATION_CHAIN_OR_SOURCE_COUNT_MISMATCH")
            output.update(status="PRODUCTION_OBSERVE_CUSTODY_ACTIVE",
                          canonical_rows=1,first_sequence=0,
                          canonical_head_sha256=proof["head_chain_sha256"],
                          external_anchor_verified=False,
                          timer_installed=False,source_field_rights_cleared=False,
                          actual_revenue_verified=False)
            receipt=report["backup_reference"]/"v15-production-recovery-receipt.json"
            with receipt.open("x",encoding="utf-8") as stream:
                stream.write(json.dumps(output,sort_keys=True)+"\n")
            os.chmod(receipt,0o600)
    except RecoveryHold as exc:
        output["reason_code"]=str(exc)
        output["failed_phase"]=phase
    except Exception as exc:
        output["reason_code"]="RELEASE_RECOVERY_UNEXPECTED_ERROR_NO_RETRY"
        output["failed_phase"]=phase
        output["exception_type"]=type(exc).__name__
    print(json.dumps(output,sort_keys=True))
    return 0 if output["status"]=="PRODUCTION_OBSERVE_CUSTODY_ACTIVE" else 2


if __name__=="__main__":
    raise SystemExit(main())
