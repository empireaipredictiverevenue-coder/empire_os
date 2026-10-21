"""Read-only pre-DDL evidence probe for EmpireDB original conversion registry.

Runs with an already authorized ROOT operator only, invokes postgres local
read-only SELECT and pgBackRest INFO. Does not authenticate original forecast
rows, prove a restore drill, or approve/execute any migration.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
from typing import Any, Callable

from empire_os.rev051_pgbackrest_readiness import review_pgbackrest_info

SCHEMA="empire.predictive_revenue.original_conversion_dba_prerequisites.v1"
MAX_BACKUP_AGE_HOURS=24
MAX_OUTPUT=1_000_000

# No protected roles, tenant IDs, archive_command, source records or secret
# settings are returned in output. SQL reads only pg_catalog / pg_stat views.
SQL="""SELECT pg_catalog.jsonb_build_object(
 'canonical_database',current_database()='empiredb',
 'postgres_version_18',current_setting('server_version_num')::int BETWEEN 180000 AND 189999,
 'migrator_role_present',EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ),
 'service_role_present',EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='service_role'
 ),
 'tenant_resolver_owner_shape',EXISTS(
   SELECT 1 FROM pg_catalog.pg_proc p
   WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
     AND p.prosecdef AND p.provolatile='s'
     AND p.proowner='empiredb_migrator'::pg_catalog.regrole
 ),
 'dedicated_conversion_table_absent',
   pg_catalog.to_regclass('public.original_conversion_predictions') IS NULL,
 'dedicated_writer_fn_absent',pg_catalog.to_regprocedure(
   'public.record_original_conversion_prediction_v1(text,text,text,text)'
 ) IS NULL,
 'dedicated_reader_fn_absent',pg_catalog.to_regprocedure(
   'public.read_original_conversion_prediction_v1(text,text)'
 ) IS NULL,
 'dedicated_writer_role_absent',NOT EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_original_conversion_prediction_writer'
 ),
 'dedicated_reader_role_absent',NOT EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_original_conversion_prediction_reader'
 ),
 'archive_mode_enabled',current_setting('archive_mode')='on',
 'archiver_failed_count',(SELECT failed_count FROM pg_catalog.pg_stat_archiver),
 'archiver_last_failed_later_than_last_archived',(
   SELECT last_failed_time IS NOT NULL AND
     (last_archived_time IS NULL OR last_failed_time>last_archived_time)
   FROM pg_catalog.pg_stat_archiver
 )
)"""


class DBAEvidenceHold(ValueError):
    pass


def _exec(args: list[str], *, run: Callable[...,Any]) -> Any:
    try:
        result=run(args,capture_output=True,timeout=20,check=False)
    except (OSError,subprocess.TimeoutExpired):
        raise DBAEvidenceHold("protected original source inaccessible") from None
    stdout=getattr(result,"stdout",None)
    if (getattr(result,"returncode",1)!=0
            or not isinstance(stdout,bytes)
            or not 0<len(stdout)<=MAX_OUTPUT):
        raise DBAEvidenceHold("protected original source did not respond")
    try:
        return json.loads(stdout)
    except (ValueError,UnicodeDecodeError):
        raise DBAEvidenceHold("protected original source malformed") from None


def _archive_row(row: Any) -> dict:
    required={
      "canonical_database", "postgres_version_18", "migrator_role_present",
      "service_role_present", "tenant_resolver_owner_shape",
      "dedicated_conversion_table_absent", "dedicated_writer_fn_absent",
      "dedicated_reader_fn_absent", "dedicated_writer_role_absent",
      "dedicated_reader_role_absent", "archive_mode_enabled",
      "archiver_failed_count", "archiver_last_failed_later_than_last_archived",
    }
    if (type(row) is not dict or set(row)!=required
            or any(type(row[k]) is not bool for k in required
                   if k!="archiver_failed_count")
            or type(row["archiver_failed_count"]) is not int
            or row["archiver_failed_count"]<0):
        raise DBAEvidenceHold("original SQL evidence untrustworthy")
    return row


def diagnostic(*, run: Callable[...,Any] = subprocess.run, is_root: bool | None = None,
               now: datetime | None = None) -> dict:
    if is_root is None:
        is_root=os.geteuid()==0
    if not is_root:
        raise DBAEvidenceHold("privileged original observer required")
    stamp=now or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise DBAEvidenceHold("timezone-aware observer required")
    backups=_exec([
        "runuser","-u","postgres","--","pgbackrest",
        "--config=/etc/pgbackrest/empiredb.conf","--stanza=empiredb",
        "--log-level-file=off","--output=json","info",
    ],run=run)
    metadata=review_pgbackrest_info(backups,now_utc=stamp)
    row=_archive_row(_exec([
        "runuser","-u","postgres","--","psql",
        "-X","-q","-t","-A","-v","ON_ERROR_STOP=1",
        "-d","empiredb","-c",SQL,
    ],run=run))
    roles_ready=all(row[k] for k in (
        "canonical_database","postgres_version_18","migrator_role_present",
        "service_role_present","tenant_resolver_owner_shape",
    ))
    absent=all(row[k] for k in (
        "dedicated_conversion_table_absent","dedicated_writer_fn_absent",
        "dedicated_reader_fn_absent","dedicated_writer_role_absent",
        "dedicated_reader_role_absent",
    ))
    backup_fresh=(metadata.get("status")==
        "PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
        and type(metadata.get("newest_backup_age_hours")) in (int,float)
        and metadata["newest_backup_age_hours"]<=MAX_BACKUP_AGE_HOURS)
    archive_ok=(row["archive_mode_enabled"] and
                not row["archiver_last_failed_later_than_last_archived"])
    prerequisites_observed=roles_ready and absent and backup_fresh and archive_ok
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":(
            "PRE_DDL_BACKUP_AND_AUTHORITY_METADATA_REVIEW_READY"
            if prerequisites_observed
            else "PRE_DDL_BACKUP_OR_AUTHORITY_METADATA_HOLD"
        ),
        "observed_at_utc":stamp.isoformat(),
        "empiredb_migrator_and_tenant_resolver_shape_verified":roles_ready,
        "original_conversion_registry_absence_reconfirmed":absent,
        "pgbackrest_source_metadata_validated":metadata.get("status")==
            "PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED",
        "newest_backup_age_hours":metadata.get("newest_backup_age_hours"),
        "max_backup_age_hours_for_change":MAX_BACKUP_AGE_HOURS,
        "recent_backup_under_change_threshold":backup_fresh,
        "archive_mode_enabled":row["archive_mode_enabled"],
        "archiver_recent_unresolved_failure_detected":row[
            "archiver_last_failed_later_than_last_archived"
        ],
        "archiver_failed_count_diagnostic":row["archiver_failed_count"],
        "metadata_prerequisites_observed":prerequisites_observed,
        "independent_restoration_or_pitr_drill_verified":False,
        "offnode_backup_verified":False,
        "original_operator_dba_security_review_signed":False,
        "release_commit_approved_for_database_ddl":False,
        "registry_ddl_executed":False,
        "credentials_or_role_memberships_changed":False,
        "production_forecasting_enabled":False,
        "database_writes":False,
        "execution_authority":"none",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args(argv)
    try:
        result=diagnostic()
    except (DBAEvidenceHold,TypeError,ValueError,OSError):
        result={
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"ORIGINAL_DBA_PROTECTED_READ_HELD",
            "metadata_prerequisites_observed":False,
            "independent_restoration_or_pitr_drill_verified":False,
            "registry_ddl_executed":False,
            "database_writes":False,
            "execution_authority":"none",
        }
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result.get("metadata_prerequisites_observed") else 2


if __name__=="__main__":
    raise SystemExit(main())
