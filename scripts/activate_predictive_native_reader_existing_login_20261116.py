#!/usr/bin/env python3
"""Single guarded role grant + authenticated first-party source read.

Existing REV052 founder tenant login only. Original native REV076/077 roles.
No new login, credential, tenant mapping, server restart, backup or model write.
This changes *only* one non-inherited DB role membership and refreshes the
original source preflight report after a real SCRAM-authenticated DB session.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import stat
import sys

from empire_os.predictive_revenue_source_preflight import review_authenticated_sources
from scripts.provision_revenue_event_evidence_login_20261018 import (
    LOGIN, ROLE, TENANT, VAULT, PASSFILE, pg,
)
from scripts.audit_predictive_revenue_forecasts import _save_report

ROOT = Path("/srv/empire_os")
REGISTRY_ROLE = "empire_predictive_registry_reader"
OUTPUT = ROOT / "runtime/predictive_revenue_control/authenticated_source_preflight_latest.json"
CATALOG = f"""BEGIN READ ONLY;
SET LOCAL statement_timeout='4000ms';
SELECT pg_catalog.jsonb_build_object(
 'canonical',current_database()='empiredb' AND NOT pg_catalog.pg_is_in_recovery(),
 'postgres18',current_setting('server_version_num')::int>=180000,
 'registry_force_rls',COALESCE((SELECT relrowsecurity AND relforcerowsecurity
  FROM pg_catalog.pg_class
  WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')),FALSE),
 'registrar_exists',pg_catalog.to_regprocedure(
  'public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)') IS NOT NULL,
 'census_exists',pg_catalog.to_regprocedure(
  'public.read_predictive_revenue_day_v1(date,text)') IS NOT NULL,
 'registry_role_safe',EXISTS(SELECT 1 FROM pg_catalog.pg_roles
  WHERE rolname='{REGISTRY_ROLE}' AND NOT rolcanlogin AND NOT rolinherit
    AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
    AND NOT rolcreaterole AND NOT rolreplication),
 'login_safe',EXISTS(SELECT 1 FROM pg_catalog.pg_roles
  WHERE rolname='{LOGIN}' AND rolcanlogin AND NOT rolinherit
   AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb
   AND NOT rolcreaterole AND NOT rolreplication),
 'original_census_role_member',EXISTS(SELECT 1
  FROM pg_catalog.pg_auth_members m
  WHERE m.member=pg_catalog.to_regrole('{LOGIN}')
   AND m.roleid=pg_catalog.to_regrole('{ROLE}')
   AND m.set_option AND NOT m.inherit_option AND NOT m.admin_option),
 'original_active_tenant_only',(
  SELECT count(*)=1 AND bool_and(
   tenant_id='{TENANT}'::uuid AND active
   AND nullif(btrim(evidence_ref),'') IS NOT NULL)
  FROM public.empire_tenant_role_bindings
  WHERE role_name='{LOGIN}'),
 'registry_reader_no_table_write',NOT (
   pg_catalog.has_table_privilege('{REGISTRY_ROLE}','public.predictive_forecasts','INSERT')
   OR pg_catalog.has_table_privilege('{REGISTRY_ROLE}','public.predictive_forecasts','UPDATE')
   OR pg_catalog.has_table_privilege('{REGISTRY_ROLE}','public.predictive_forecasts','DELETE')),
 'no_business_registrar_membership',NOT pg_catalog.pg_has_role(
   '{LOGIN}','empire_predictive_forecast_registrar','MEMBER'),
 'existing_membership',EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
   WHERE m.member=pg_catalog.to_regrole('{LOGIN}')
   AND m.roleid=pg_catalog.to_regrole('{REGISTRY_ROLE}')
   AND m.set_option AND NOT m.inherit_option AND NOT m.admin_option),
 'unexpected_membership',EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m
   WHERE m.member=pg_catalog.to_regrole('{LOGIN}')
   AND m.roleid=pg_catalog.to_regrole('{REGISTRY_ROLE}')
   AND (NOT m.set_option OR m.inherit_option OR m.admin_option)),
 'existing_registry_role_members',(
    SELECT count(*) FROM pg_catalog.pg_auth_members m
    WHERE m.roleid=pg_catalog.to_regrole('{REGISTRY_ROLE}'))
)::text;
ROLLBACK;"""
ADMISSION = (
    "canonical","postgres18","registry_force_rls","registrar_exists",
    "census_exists","registry_role_safe","login_safe",
    "original_census_role_member","original_active_tenant_only",
    "registry_reader_no_table_write","no_business_registrar_membership",
)
GRANT_SQL = f"""BEGIN;
SET LOCAL statement_timeout='8000ms';
SET LOCAL lock_timeout='2000ms';
DO $guard$
BEGIN
 IF current_database()<>'empiredb' OR pg_catalog.pg_is_in_recovery()
 OR NOT EXISTS(SELECT 1 FROM public.empire_tenant_role_bindings
    WHERE role_name='{LOGIN}' AND tenant_id='{TENANT}'::uuid
      AND active AND nullif(btrim(evidence_ref),'') IS NOT NULL)
 OR (SELECT count(*) FROM public.empire_tenant_role_bindings
      WHERE role_name='{LOGIN}')<>1
 OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
     WHERE member=pg_catalog.to_regrole('{LOGIN}')
       AND roleid=pg_catalog.to_regrole('{REGISTRY_ROLE}'))
 OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members
     WHERE roleid=pg_catalog.to_regrole('{REGISTRY_ROLE}'))
 OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class
     WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')
       AND relrowsecurity AND relforcerowsecurity)
 THEN
  RAISE EXCEPTION 'NATIVE_REGISTRY_ONE_TENANT_READER_PREREQUISITE_DRIFT';
 END IF;
END $guard$;
GRANT {REGISTRY_ROLE} TO {LOGIN}
  WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;
COMMIT;"""
REVOKE_SQL = f"""BEGIN;
SET LOCAL statement_timeout='8000ms';
SET LOCAL lock_timeout='2000ms';
REVOKE {REGISTRY_ROLE} FROM {LOGIN};
COMMIT;"""


class ActivationHold(RuntimeError):
    pass


def protected_credential_path() -> Path:
    """Return root-only original SCRAM passfile path; never read/print secrets."""
    if (VAULT.is_symlink() or PASSFILE.is_symlink()
        or not VAULT.is_dir() or not PASSFILE.is_file()):
        raise ActivationHold("ORIGINAL_VAULT_PATH_UNAVAILABLE")
    a,b=VAULT.stat(),PASSFILE.stat()
    if (a.st_uid!=0 or b.st_uid!=0
        or stat.S_IMODE(a.st_mode)!=0o700
        or stat.S_IMODE(b.st_mode)!=0o600
        or b.st_size>8192 or b.st_size==0):
        raise ActivationHold("ORIGINAL_VAULT_SECURITY_DRIFT")
    return PASSFILE


def read_catalog(*, read_sql=pg) -> dict:
    try:
        record=json.loads(read_sql(CATALOG))
    except (OSError,RuntimeError,ValueError,TypeError):
        raise ActivationHold("ORIGINAL_LIVE_CATALOGUE_UNAVAILABLE") from None
    fields=set(ADMISSION)|{"existing_membership","unexpected_membership",
                           "existing_registry_role_members"}
    if (type(record) is not dict or set(record)!=fields
        or any(type(record[k]) is not (int if k=="existing_registry_role_members"
                                        else bool) for k in fields)):
        raise ActivationHold("ORIGINAL_CATALOGUE_CONTRACT_INVALID")
    failing=sorted(key for key in ADMISSION if not record[key])
    if (failing or record["unexpected_membership"]
        or record["existing_registry_role_members"]>1
        or (record["existing_membership"] and
            record["existing_registry_role_members"]!=1)
        or (not record["existing_membership"] and
            record["existing_registry_role_members"]!=0)):
        raise ActivationHold("ORIGINAL_ROLE_OR_TENANT_DRIFT:"+",".join(failing))
    return record


def authenticated_readback(passfile: Path) -> dict:
    import psycopg
    from psycopg.conninfo import make_conninfo
    dsn=make_conninfo(
        host="/var/run/postgresql",port=5432,dbname="empiredb",
        user=LOGIN,passfile=str(passfile),connect_timeout=5,
    )
    # The original reader probes return bounded counts and booleans only.
    result=review_authenticated_sources(
        tenant_id=TENANT,registry_dsn=dsn,census_dsn=dsn,
        as_of=datetime.now(timezone.utc),
    )
    return validate_authenticated_result(result)


def validate_authenticated_result(result: dict)->dict:
    if (type(result) is not dict
        or result.get("schema_version") !=
            "empire.predictive_revenue.authenticated_source_preflight.v1"
        or result.get("mode") != "OBSERVE"
        or result.get("registry_reader_authenticated_session") is not True
        or result.get("census_reader_authenticated_session") is not True
        or result.get("reader_tenant_scope_input_valid") is not True
        or result.get("original_restricted_registry_reader_reused") is not True
        or result.get("original_restricted_day_census_reader_reused") is not True
        or type(result.get("registry_scoped_rows_observed")) is not int
        or type(result.get("census_tenant_events_observed")) is not int
        or result.get("source_credentials_exposed") is not False
        or result.get("independently_verified_forecast_actual_pairs") != 0
        or result.get("model_calibration_ready") is not False
        or result.get("customer_release_authorized") is not False
        or result.get("database_writes") is not False):
        # Only bounded internal enum statuses, never role IDs, SQL errors,
        # tenant identity, passfile contents or customer/source payloads.
        allowed_registry = {
            "REGISTRY_EMPTY_COVERAGE_UNKNOWN_HOLD",
            "TENANT_BOUND_REGISTRY_ROWS_OBSERVED_UNVERIFIED",
            "REGISTRY_READ_BOUND_REACHED_HOLD",
            "REGISTRY_RESTRICTED_READ_OR_POLICY_FAILED",
            "DEDICATED_REGISTRY_CREDENTIAL_UNAVAILABLE",
        }
        allowed_census = {
            "DAY_CENSUS_INCOMPLETE_HOLD",
            "DAY_SOURCE_CENSUS_CANDIDATE",
            "CENSUS_RESTRICTED_READ_OR_POLICY_FAILED",
            "DEDICATED_CENSUS_CREDENTIAL_UNAVAILABLE",
        }
        registry = result.get("registry_source_status")
        census = result.get("census_source_status")
        stage = ("REGISTRY=" + (registry if registry in allowed_registry else "UNKNOWN")
                 + ",CENSUS=" + (census if census in allowed_census else "UNKNOWN"))
        raise ActivationHold(
            "NATIVE_READER_POSTGRANT_TENANT_AUTHENTICATION_UNVERIFIED:" + stage)
    return result


def apply(*, read_sql=pg, verify=authenticated_readback,
          save=_save_report, passfile_provider=protected_credential_path) -> dict:
    passfile=passfile_provider()
    state=read_catalog(read_sql=read_sql)
    granted=False
    try:
        if not state["existing_membership"]:
            read_sql(GRANT_SQL)
            granted=True
        new_state=read_catalog(read_sql=read_sql)
        if not new_state["existing_membership"]:
            raise ActivationHold("NATIVE_READER_ROLE_GRANT_NOT_VERIFIED")
        result=validate_authenticated_result(verify(passfile))
        save(OUTPUT,result)
    except Exception:
        # Only unwind a role membership actually created by this operation.
        # Never revoke another owner's pre-existing approval.
        if granted:
            try:
                read_sql(REVOKE_SQL)
            except Exception:
                raise ActivationHold("NATIVE_READER_GRANT_ROLLBACK_UNVERIFIED") from None
        raise
    return {
        "status":"NATIVE_FORECAST_READER_TENANT_AUTHENTICATED",
        "existing_original_login_reused":True,
        "original_registry_role_grant_applied":granted,
        "registry_authenticated":result["registry_reader_authenticated_session"],
        "registry_status":result["registry_source_status"],
        "registry_scoped_rows_observed":result["registry_scoped_rows_observed"],
        "census_authenticated":result["census_reader_authenticated_session"],
        "census_status":result["census_source_status"],
        "census_tenant_events_observed":result["census_tenant_events_observed"],
        "genuine_forecast_outcome_pairs_verified":0,
        "model_calibration_ready":False,
        "new_backup_created":False,
        "new_login_created":False,
        "credentials_rotated":False,
        "customer_rows_written":False,
        "outbound_sent":False,
    }


def _safe_error_category(exc: Exception) -> str:
    """Never expose actual DB exception strings, credentials or source rows."""
    sqlstate=getattr(exc,"sqlstate",None)
    if sqlstate=="42501":return "SQL_PERMISSION_DENIED_42501"
    if sqlstate=="42883":return "SQL_FUNCTION_MISSING_42883"
    if sqlstate=="42P01":return "SQL_RELATION_MISSING_42P01"
    if sqlstate=="P0001":return "SOURCE_DAY_INCOMPLETE_OR_TENANT_REJECTED_P0001"
    lowered=str(exc).lower()
    if "no password supplied" in lowered:
        return "PGPASS_NO_MATCHING_PASSWORD"
    if "password authentication failed" in lowered:
        return "SCRAM_PASSWORD_REJECTED"
    if "pg_hba.conf" in lowered or "peer authentication failed" in lowered:
        return "PG_HBA_AUTH_RULE_REJECTED"
    if "connection refused" in lowered or "no such file or directory" in lowered:
        return "PG_SOCKET_NOT_ACCESSIBLE"
    if sqlstate is not None:return "SQLSTATE_OTHER"
    return "CLIENT_DB_CONNECTION_OR_SOURCE_READ_UNAVAILABLE"


def diagnose_readonly(*, path_provider=protected_credential_path,
                      catalog_reader=read_catalog, connect_factory=None)->dict:
    """Root-only, original vault, no grant, source mutation or credentials out."""
    import psycopg
    from psycopg.conninfo import make_conninfo
    stage="ORIGINAL_VAULT_CHECK"
    steps={
        "original_root_vault_valid":False,
        "passfile_target_matches":False,
        "scram_authenticated_login":False,
        "canonical_read_only_transaction":False,
        "original_restricted_census_role_set":False,
        "original_rev077_census_query_executed":False,
    }
    membership=False
    try:
        passfile=path_provider()
        steps["original_root_vault_valid"]=True
        # Do not print line contents, password length or hashes. This
        # structural metadata check uses only the four public connection
        # selectors, not the credential itself.
        stage="ORIGINAL_PGPASS_TARGET"
        with passfile.open("r",encoding="utf-8") as handle:
            lines=handle.read(8193).splitlines()
        target=[line.split(":",4)[:4] for line in lines if line and not line.startswith("#")]
        steps["passfile_target_matches"]=any(
            prefix==["/var/run/postgresql","5432","empiredb",LOGIN]
            for prefix in target
        )
        if not steps["passfile_target_matches"]:
            return {"status":"ORIGINAL_READER_DIAGNOSTIC_HOLD",
                "stage":"ORIGINAL_PGPASS_TARGET","failure":"PGPASS_TARGET_MISMATCH",
                "observations":steps,"database_writes":False}
        stage="ORIGINAL_CATALOGUE_READ"
        membership=catalog_reader()["existing_membership"]
        stage="ORIGINAL_SCRAM_CONNECTION"
        dsn=make_conninfo(host="/var/run/postgresql",port=5432,
            dbname="empiredb",user=LOGIN,passfile=str(passfile),connect_timeout=5)
        connect_factory=connect_factory or psycopg.connect
        with connect_factory(dsn) as connection:
            steps["scram_authenticated_login"]=True
            with connection.cursor() as cursor:
                stage="CANONICAL_READER_TRANSACTION"
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SELECT current_database(),session_user,"
                    "current_setting('transaction_read_only')")
                row=cursor.fetchone()
                if row!=("empiredb",LOGIN,"on"):
                    raise ActivationHold("ORIGINAL_READ_ONLY_SESSION_IDENTITY_DRIFT")
                steps["canonical_read_only_transaction"]=True
                stage="ORIGINAL_REV052_CENSUS_ROLE"
                cursor.execute("SET LOCAL ROLE " + ROLE)
                steps["original_restricted_census_role_set"]=True
                stage="ORIGINAL_REV077_SOURCE_DAY"
                cursor.execute(
                    "SELECT day_utc,scope_tenant_id,global_event_count,"
                    "valid_tenant_event_count,tenant_amount_cents,"
                    "global_invalid_count,tenant_invalid_count,snapshot_at "
                    "FROM public.read_predictive_revenue_day_v1(%s::date,%s::text)",
                    ((datetime.now(timezone.utc).date()-timedelta(days=1)),TENANT))
                row=cursor.fetchone()
                if row is None or len(row)!=8 or row[1]!=TENANT:
                    raise ActivationHold("CENSUS_SCOPED_RESULT_UNVERIFIED")
                steps["original_rev077_census_query_executed"]=True
    except Exception as exc:
        return {"status":"ORIGINAL_READER_DIAGNOSTIC_HOLD",
            "stage":stage,"failure":_safe_error_category(exc),
            "observations":steps,"registry_role_currently_granted":membership,
            "database_writes":False}
    return {"status":"ORIGINAL_READER_DIAGNOSTIC_PASSED",
        "stage":"COMPLETED","failure":None,
        "observations":steps,"registry_role_currently_granted":membership,
        "database_writes":False,
        "independent_financial_actuals_verified":False}


def main(argv: list[str]|None=None)->int:
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight",action="store_true")
    mode.add_argument("--diagnose-readonly",action="store_true")
    mode.add_argument("--apply-founder-approved",action="store_true")
    args=parser.parse_args(argv)
    if os.geteuid()!=0 or Path.cwd().resolve()!=ROOT:
        print(json.dumps({"status":"EXPLICIT_FOUNDER_ROOT_OPERATOR_REQUIRED"}))
        return 2
    try:
        if args.diagnose_readonly:
            observation=diagnose_readonly()
            print(json.dumps(observation,sort_keys=True))
            return 0 if observation["status"]=="ORIGINAL_READER_DIAGNOSTIC_PASSED" else 2
        protected_credential_path()
        state=read_catalog()
        if args.preflight:
            outcome={"status":"ORIGINAL_ONE_TENANT_READER_PREFLIGHT_READY",
                     "registry_role_already_granted":state["existing_membership"],
                     "database_writes":False}
        else:
            outcome=apply()
        print(json.dumps(outcome,sort_keys=True))
        return 0
    except (ActivationHold,OSError,ValueError,RuntimeError) as error:
        code=str(error) if isinstance(error,ActivationHold) else (
            "NATIVE_READER_PROBE_OR_GRANT_UNAVAILABLE")
        print(json.dumps({"status":"NATIVE_READER_RELEASE_HELD",
                          "reason_code":code[:155],
                          "authenticated_customer_forecast_unverified":True},
                         sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
