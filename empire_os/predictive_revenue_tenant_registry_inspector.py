"""Strict tenant-bound, read-only EmpireDB predictive-forecast registry inventory.

Unlike the legacy global forecast list, this reader requires trusted
session_user tenancy, a non-bypass role and FORCE RLS before a scoped
registry SELECT. No raw forecasts, source evidence or tenant IDs are exported.
It does not certify immutability, forecast performance or customer release.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_registry_transport import READER_ROLE

IDENTITY_SQL="SELECT current_database(),current_setting('transaction_read_only')"
TENANT_SQL="SELECT public.empire_current_tenant_id()"
ROLE_SQL="""SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit
FROM pg_catalog.pg_roles WHERE rolname = %s"""
TABLE_SQL="""SELECT relrowsecurity,relforcerowsecurity
FROM pg_catalog.pg_class
WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')"""
SCOPED_SQL="""SELECT id,forecast_key,dimension_key,metric,
       predicted_value,generated_at
FROM public.predictive_forecasts
WHERE dimension_key = %s AND metric = %s
  AND generated_at <= %s
ORDER BY generated_at DESC,id DESC LIMIT %s"""
MAX_READ=100
METRIC="recognized_revenue_cents"


class PrivateForecastRegistryUnavailable(RuntimeError):
    """Sanitized only: no login, row, tenant, query or credential details."""


def _uuid(value:Any)->str:
    try:
        normalized=str(UUID(str(value)))
    except (TypeError,ValueError,AttributeError):
        raise ValueError("canonical UUID required") from None
    if type(value) is not str or normalized!=value:
        raise ValueError("canonical UUID required")
    return normalized


def _when(value:Any)->datetime:
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp not timezone aware")
    return value.astimezone(timezone.utc)


def _exact_cents(value:Any)->int:
    if type(value) not in (int,Decimal):
        raise ValueError("exact registry cents required")
    if type(value) is Decimal and not value.is_finite():
        raise ValueError("invalid registry decimal")
    if not 0<=value<=9_000_000_000_000_000 or int(value)!=value:
        raise ValueError("invalid registry cents")
    return int(value)


def inspect_tenant_bound_predictive_registry(
    *,dsn:str,tenant_id:str,as_of:datetime,
    limit:int=MAX_READ,
    connect_factory:Callable[...,Any]|None=None,
)->dict[str,Any]:
    """Scoped inventory, NOT the global PostgresPredictiveRegistryReader."""
    try:
        tenant=_uuid(tenant_id)
        now=_when(as_of)
        if type(limit) is not int or not 1<=limit<=MAX_READ:
            raise ValueError("bounded registry size required")
        if not isinstance(dsn,str) or not dsn.strip():
            raise ValueError("dedicated registry credential missing")
    except ValueError:
        raise PrivateForecastRegistryUnavailable("REGISTRY_INPUT_OR_TENANT_SCOPE_INVALID") from None
    if connect_factory is None:
        try:
            import psycopg
            connect_factory=psycopg.connect
        except ImportError:
            raise PrivateForecastRegistryUnavailable("REGISTRY_DRIVER_UNAVAILABLE") from None
    try:
        with connect_factory(dsn,connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE "+READER_ROLE)
                cur.execute(IDENTITY_SQL)
                identity=cur.fetchone()
                if (type(identity) not in (tuple,list) or
                    tuple(identity)!=("empiredb","on")):
                    raise ValueError("not restricted database session")
                cur.execute(TENANT_SQL)
                binding=cur.fetchone()
                if (type(binding) not in (tuple,list) or
                    len(binding)!=1 or str(binding[0])!=tenant):
                    raise ValueError("cross-tenant database session")
                cur.execute(ROLE_SQL,(READER_ROLE,))
                role=cur.fetchone()
                if (type(role) not in (tuple,list) or
                    tuple(role)!=(False,False,False,False)):
                    raise ValueError("registry role privileges drift")
                cur.execute(TABLE_SQL)
                table=cur.fetchone()
                if (type(table) not in (tuple,list) or
                    tuple(table)!=(True,True)):
                    raise ValueError("forecast registry FORCE RLS not verified")
                dimension="tenant:"+tenant
                # A caller-supplied as_of is a historical cutoff, not merely
                # an after-the-fact timestamp assertion. Filter at the DB
                # source to exclude later registrations from original cohorts.
                cur.execute(SCOPED_SQL,(dimension,METRIC,now,limit+1))
                rows=cur.fetchall()
                if type(rows) is not list or len(rows)>limit+1:
                    raise ValueError("bounded registry result required")
        identifiers=set()
        keys=set()
        latest=None
        for row in rows:
            if type(row) not in (tuple,list) or len(row)!=6:
                raise ValueError("registry row shape invalid")
            entry_id,key,scope,metric,value,registered=row
            canonical=str(UUID(str(entry_id)))
            if (not isinstance(key,str) or not 1<=len(key)<=180 or
                canonical in identifiers or key in keys or
                scope!=dimension or metric!=METRIC):
                raise ValueError("duplicate or unscoped registry record")
            identifiers.add(canonical)
            keys.add(key)
            _exact_cents(value)
            issued=_when(registered)
            if issued>now:
                raise ValueError("future registry registration")
            if latest is None or issued>latest:
                latest=issued
    except Exception:
        raise PrivateForecastRegistryUnavailable(
            "TENANT_BOUND_REGISTRY_READ_OR_POLICY_UNAVAILABLE") from None
    bounded=len(rows)>=limit
    return {
        "schema_version":"empire.predictive_revenue.tenant_registry_inspection.v1",
        "status":(
            "REGISTRY_READ_BOUND_REACHED_HOLD" if bounded else
            "REGISTRY_EMPTY_COVERAGE_UNKNOWN_HOLD" if not rows else
            "TENANT_BOUND_REGISTRY_ROWS_OBSERVED_UNVERIFIED"
        ),
        "existing_empiredb_source":"public.predictive_forecasts",
        "metric":METRIC,
        "observed_row_count":min(len(rows),limit),
        "bound_reached":bounded,
        "last_registered_at_utc":latest.isoformat() if latest else None,
        "trusted_session_user_tenant_matched":True,
        "reader_nologin_noinherit_nobypassrls_verified":True,
        "forecast_registry_force_rls_verified":True,
        "source_rows_are_complete_census":False,
        "original_forecast_immutable_registration_verified":False,
        "original_observations_independently_attested":False,
        "original_forecast_values_exported":False,
        "tenant_identifiers_exported":False,
        "customer_model_acceptance_verified":False,
        "financial_actuals_verified":False,
        "customer_delivery_enabled":False,
        "database_written":False,
        "mode":"OBSERVE",
        "execution_authority":"none",
    }
