#!/usr/bin/env python3
"""One operator-controlled, additive EmpireDB REV076-078 release.

Root-only and SHA-pinned. No new backup, no data backfill, no service restart,
no customer records, no login creation, no tenant-binding change. All three
original HELD DDL files execute as ONE PostgreSQL transaction, with rollback
on any error. The founder/DBA release authority is represented by the
--apply-founder-approved flag, never by an automated scheduler.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

from scripts.provision_revenue_event_evidence_login_20261018 import pg

ROOT = Path("/srv/empire_os")
LOCK = Path("/run/lock/empire-predictive-native-release.lock")
MIGRATIONS = (
    ("migrations/empiredb/076_predictive_forecast_registry_native_held.sql",
     "eb433426469ee2cec6b0bd74879a41dcb7bbc3bd6f7c3fa78a31f247281b12b9"),
    ("migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql",
     "5b232be73e8430af14facf4ae2fe2ff4570bae3f0d3bf5f9899706d96fed0d0b"),
    ("migrations/empiredb/078_predictive_future_forecast_registration_held.sql",
     "280d11a5ddc14aaa8b9c1fbe128eb769824e24974e2b60a85d69c8e9dc82fa5e"),
)
CATALOG_SQL = """BEGIN READ ONLY;
SET LOCAL statement_timeout='4000ms';
SELECT pg_catalog.jsonb_build_object(
 'canonical',current_database()='empiredb' AND NOT pg_catalog.pg_is_in_recovery(),
 'version18',current_setting('server_version_num')::integer >= 180000,
 'migrator_exists',EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper),
 'tenant_resolver_original',EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
   WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
   AND p.prosecdef AND p.provolatile='s'
   AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                  WHERE rolname='empiredb_migrator')),
 'original_rev051_event_reader',pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_event_v1(uuid,text)') IS NOT NULL,
 'original_rev051_no_login_role',EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_revenue_evidence_reader'
     AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
     AND NOT rolinherit),
 'registry_absent',pg_catalog.to_regclass('public.predictive_forecasts') IS NULL,
 'registry_role_absent',NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_registry_reader'),
 'registrar_role_absent',NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_forecast_registrar'),
 'census_absent',pg_catalog.to_regprocedure(
   'public.read_predictive_revenue_day_v1(date,text)') IS NULL,
 'registrar_absent',pg_catalog.to_regprocedure(
   'public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)') IS NULL,
 'archive_mode_on',current_setting('archive_mode')='on',
 'archiver_healthy',(SELECT archived_count>0 AND last_archived_time IS NOT NULL
  AND (last_failed_time IS NULL OR last_archived_time>last_failed_time)
  FROM pg_catalog.pg_stat_archiver)
)::text;
ROLLBACK;"""
REQUIRED = (
 "canonical", "version18", "migrator_exists", "tenant_resolver_original",
 "original_rev051_event_reader", "original_rev051_no_login_role",
 "registry_absent", "registry_role_absent", "registrar_role_absent",
 "census_absent", "registrar_absent", "archive_mode_on", "archiver_healthy",
)
POSTCHECK_SQL = """RESET ROLE;
DO $verify$
BEGIN
 IF pg_catalog.to_regclass('public.predictive_forecasts') IS NULL
 OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class
    WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')
      AND relrowsecurity AND relforcerowsecurity
      AND relowner=(SELECT oid FROM pg_catalog.pg_roles
                    WHERE rolname='empiredb_migrator')) THEN
   RAISE EXCEPTION 'NATIVE_RELEASE_REGISTRY_RLS_OR_OWNER_HOLD';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_registry_reader'
      AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolinherit)
 OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_predictive_forecast_registrar'
      AND NOT rolcanlogin AND NOT rolbypassrls AND NOT rolinherit) THEN
   RAISE EXCEPTION 'NATIVE_RELEASE_RESTRICTED_ROLE_HOLD';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
   WHERE p.oid=pg_catalog.to_regprocedure(
     'public.read_predictive_revenue_day_v1(date,text)')
     AND p.prosecdef
     AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                     WHERE rolname='empiredb_migrator'))
 OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
   WHERE p.oid=pg_catalog.to_regprocedure(
     'public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)')
     AND p.prosecdef
     AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                     WHERE rolname='empiredb_migrator')) THEN
   RAISE EXCEPTION 'NATIVE_RELEASE_PRIVATE_READER_OR_REGISTRAR_HOLD';
 END IF;
 IF (SELECT count(*) FROM public.predictive_forecasts) <> 0 THEN
   RAISE EXCEPTION 'NATIVE_RELEASE_UNEXPECTED_REGISTRY_ROWS';
 END IF;
END $verify$;
"""
READBACK_SQL = """BEGIN READ ONLY;
SET LOCAL statement_timeout='4000ms';
SELECT (
  current_database()='empiredb' AND NOT pg_catalog.pg_is_in_recovery()
  AND EXISTS(SELECT 1 FROM pg_catalog.pg_class
   WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')
     AND relrowsecurity AND relforcerowsecurity)
  AND (SELECT count(*)=0 FROM public.predictive_forecasts)
  AND pg_catalog.to_regprocedure('public.read_predictive_revenue_day_v1(date,text)') IS NOT NULL
  AND pg_catalog.to_regprocedure('public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)') IS NOT NULL
  AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_registry_reader'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolbypassrls)
  AND EXISTS(SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_forecast_registrar'
     AND NOT rolcanlogin AND NOT rolinherit AND NOT rolbypassrls)
  AND NOT pg_catalog.has_table_privilege('empire_predictive_forecast_registrar',
    'public.predictive_forecasts','SELECT')
  AND NOT pg_catalog.has_table_privilege('empire_predictive_forecast_registrar',
    'public.predictive_forecasts','INSERT')
  AND NOT pg_catalog.has_table_privilege('empire_predictive_forecast_registrar',
    'public.predictive_forecasts','UPDATE')
  AND NOT pg_catalog.has_table_privilege('empire_predictive_forecast_registrar',
    'public.predictive_forecasts','DELETE')
  AND pg_catalog.has_function_privilege('empire_predictive_forecast_registrar',
    'public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)', 'EXECUTE')
  AND pg_catalog.to_regprocedure('public.read_predictive_revenue_event_v1(uuid,text)') IS NOT NULL
);
ROLLBACK;"""

class ReleaseHold(RuntimeError):
    pass


def load_pinned_migrations(*, root: Path = ROOT) -> tuple[str, ...]:
    parts = []
    for relative, digest in MIGRATIONS:
        path = root / relative
        try:
            meta = path.lstat()
            if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o022:
                raise ReleaseHold("MIGRATION_SOURCE_NOT_LOCKED")
            source = path.read_bytes()
        except (OSError, ValueError):
            raise ReleaseHold("MIGRATION_SOURCE_UNAVAILABLE") from None
        if hashlib.sha256(source).hexdigest() != digest:
            raise ReleaseHold("MIGRATION_SOURCE_DIGEST_DRIFT")
        content = source.decode("utf-8")
        lines = content.splitlines()
        if lines.count("BEGIN;") != 1 or lines.count("COMMIT;") != 1:
            raise ReleaseHold("MIGRATION_TRANSACTION_BOUNDARY_INVALID")
        # Eliminate only exact standalone transaction delimiters.
        # RESET ROLE is necessary between REV076 (leaves SET LOCAL ROLE
        # migrator) and REV077's privileged DBA preflight.
        body = "\n".join(
            line for line in lines if line not in ("BEGIN;", "COMMIT;")
        )
        parts.append(body + "\nRESET ROLE;\n")
    return tuple(parts)


def build_atomic_sql(parts: tuple[str, ...]) -> str:
    if len(parts) != len(MIGRATIONS):
        raise ReleaseHold("EXACT_THREE_MIGRATIONS_REQUIRED")
    return (
        "BEGIN;\nSET LOCAL statement_timeout='15000ms';\n"
        "SET LOCAL lock_timeout='3000ms';\n"
        + "\n".join(parts)
        + "\n" + POSTCHECK_SQL
        + "\nSELECT pg_catalog.jsonb_build_object("
          "'status','NATIVE_PREDICTIVE_RELEASE_COMMITTED_SCHEMA_ONLY',"
          "'rev076_registry',true,'rev077_census',true,"
          "'rev078_registration',true,'registry_rows',0,"
          "'new_login_created',false,'customer_rows_copied',false,"
          "'financial_actuals_verified',false,"
          "'customer_calibration_verified',false)::text;\nCOMMIT;\n"
    )


def check_catalogue(raw: str) -> dict[str, bool]:
    try:
        result = json.loads(raw)
    except (TypeError, ValueError):
        raise ReleaseHold("ORIGINAL_CATALOGUE_UNAVAILABLE") from None
    if type(result) is not dict or set(result)!=set(REQUIRED):
        raise ReleaseHold("ORIGINAL_CATALOGUE_SCHEMA_MISMATCH")
    if any(type(result.get(k)) is not bool for k in REQUIRED):
        raise ReleaseHold("ORIGINAL_CATALOGUE_PROOF_INVALID")
    if not all(result.values()):
        failed=','.join(sorted(k for k,v in result.items() if not v))
        raise ReleaseHold("ORIGINAL_LIVE_CATALOGUE_OR_WAL_GATE_UNMET:"+failed)
    return result


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight",action="store_true")
    mode.add_argument("--apply-founder-approved",action="store_true")
    mode.add_argument("--verify",action="store_true")
    args=parser.parse_args(argv)
    try:
        if os.geteuid()!=0 or ROOT.resolve()!=Path.cwd().resolve():
            raise ReleaseHold("EXPLICIT_ROOT_OPERATOR_IN_ORIGINAL_EMPIREOS_REQUIRED")
        parts=load_pinned_migrations()
        if not Path("/run/systemd/system").is_dir():
            raise ReleaseHold("ORIGINAL_SERVICE_MANAGER_REQUIRED")
        # Lock only as root; refuse symlinks and another user's lock file.
        descriptor=os.open(LOCK,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(descriptor,'r+') as lock:
            lock_stat=os.fstat(lock.fileno())
            if (lock_stat.st_uid!=0 or not stat.S_ISREG(lock_stat.st_mode)
                or lock_stat.st_nlink!=1 or lock_stat.st_mode & 0o077):
                raise ReleaseHold('ORIGINAL_ROOT_OPERATOR_LOCK_UNTRUSTED')
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            # Post-release verification is read-only and never reapplies DDL.
            if args.verify:
                if pg(READBACK_SQL).strip() != 't':
                    raise ReleaseHold('POST_COMMIT_ORIGINAL_READBACK_UNVERIFIED')
                print(json.dumps({
                    'status':'NATIVE_PREDICTIVE_SCHEMA_POSTCOMMIT_VERIFIED',
                    'release':'REV076_REV077_REV078',
                    'database_writes':False,
                    'original_customer_forecast_pairs_verified':False,
                },sort_keys=True))
                return 0
            # Fresh live catalogue read through original local postgres peer.
            check_catalogue(pg(CATALOG_SQL))
            if args.preflight:
                print(json.dumps({
                    "status":"SOURCE_AND_LIVE_CATALOGUE_PREFLIGHT_PASS",
                    "mode":"OBSERVE","database_writes":False,
                    "existing_backup_copies_created":0,
                    "schema_release_would_create_roles":2,
                    "schema_release_would_create_table":1,
                    "schema_release_would_create_functions":2,
                    "production_forecast_accuracy_verified":False,
                },sort_keys=True))
                return 0
            sql=build_atomic_sql(parts)
            # Uses original runuser/psql local peer helper with sanitized errors;
            # connection failure rolls back the open transaction.
            result=pg(sql)
            if "NATIVE_PREDICTIVE_RELEASE_COMMITTED_SCHEMA_ONLY" not in result:
                raise ReleaseHold("NO_COMPLETE_SCHEMA_RELEASE_RECEIPT")
            # A second independent transaction proves durable schema state.
            # Do not report success if a commit/connection ambiguity persists.
            if pg(READBACK_SQL).strip()!='t':
                raise ReleaseHold('POST_COMMIT_ORIGINAL_READBACK_UNVERIFIED')
            print(json.dumps({
                "status":"NATIVE_PREDICTIVE_SCHEMA_SQL_TRANSACTION_SUCCESS",
                "release":"REV076_REV077_REV078",
                "new_login_created":False,
                "tenant_binding_changed":False,
                "customer_rows_copied":False,
                "new_backup_created":False,
                "independent_financial_actuals_verified":False,
                "customer_forecast_accuracy_verified":False,
            },sort_keys=True))
            return 0
    except (OSError, BlockingIOError, ReleaseHold, RuntimeError) as exc:
        code=(str(exc) if isinstance(exc,ReleaseHold) else
              "ORIGINAL_DB_RUNNER_OR_RELEASE_SESSION_UNAVAILABLE")
        print(json.dumps({
            "status":"NATIVE_PREDICTIVE_SCHEMA_RELEASE_HELD",
            "hold":code[:120],
            "database_writes_verified":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
