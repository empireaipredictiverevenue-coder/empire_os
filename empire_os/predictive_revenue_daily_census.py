"""Wave 35: bounded EmpireDB day-census reader for recognized revenue.

This is a prepared-only, tenant-scoped *source census candidate*. It must not
be conflated with finalized financial reporting, full backfill finality, or
live tenant authorization. The restricted SQL function is NOT installed by
this module. No source rows, identities or commercial payloads are exposed.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable, Sequence

from empire_os.predictive_revenue_canonical_reader import (
    CanonicalRevenueEvidenceUnavailable, READ_ROLE, _utc,
)

CENSUS_SQL = """SELECT day_utc,scope_tenant_id,global_event_count,
    valid_tenant_event_count,tenant_amount_cents,
    global_invalid_count,tenant_invalid_count,snapshot_at
    FROM public.read_predictive_revenue_day_v1(%s::date,%s::text)"""
MAX_CENTS = 9223372036854775807


def _positive_int(value: Any, *, permit_zero: bool=True) -> int:
    if type(value) not in (int,Decimal):
        raise CanonicalRevenueEvidenceUnavailable("REVENUE_CENSUS_NONINTEGER")
    if isinstance(value, Decimal) and not value.is_finite():
        raise CanonicalRevenueEvidenceUnavailable("REVENUE_CENSUS_NONINTEGER")
    if (value<0 or int(value)!=value or value>MAX_CENTS or
        (not permit_zero and value==0)):
        raise CanonicalRevenueEvidenceUnavailable("REVENUE_CENSUS_NONINTEGER")
    return int(value)


def verify_daily_census_row(
    row:Sequence[Any], *, day_utc:date, tenant_id:str, as_of:datetime,
) -> dict[str,Any]:
    now=_utc(as_of)
    if type(day_utc) is not date:
        raise ValueError("explicit UTC date required")
    if (not isinstance(tenant_id,str) or not tenant_id.strip()
        or len(tenant_id)>256):
        raise ValueError("explicit bounded tenant required")
    if day_utc >= now.date():
        raise ValueError("daily census requires a completed UTC calendar date")
    if type(row) not in (tuple,list) or len(row)!=8:
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_SOURCE_UNPROVEN")
    (reported_day, reported_tenant, raw_count, tenant_count,
     amount, invalid_global, invalid_tenant, snapshot_at) = row
    if reported_day!=day_utc or reported_tenant!=tenant_id:
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_SCOPE_MISMATCH")
    queried_at=_utc(snapshot_at)
    if queried_at>now or queried_at.date()<day_utc:
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_SNAPSHOT_TIME_INVALID")
    count=_positive_int(raw_count)
    scoped=_positive_int(tenant_count)
    total=_positive_int(amount)
    broken=_positive_int(invalid_global)
    scoped_broken=_positive_int(invalid_tenant)
    # REV077 contract is tenant-scoped: never expose global event counts to
    # an ordinary reader. Invalid/unmapped global records fail in SQL before
    # a row is returned. Refuse old global-counting functions on readback.
    if (scoped!=count or broken!=0 or scoped_broken!=0
        or (scoped==0)!=(total==0)):
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_UNSCOPED_OR_INCOMPLETE")
    # An internally consistent source day is still NOT settled cash or an
    # independently admitted customer outcome for model calibration.
    candidate=(scoped>0)
    return {
        "schema_version":"empire.predictive_revenue.daily_census_candidate.v1",
        "status":("DAY_SOURCE_CENSUS_CANDIDATE" if candidate else
                  "DAY_CENSUS_INCOMPLETE_HOLD"),
        "mode":"OBSERVE",
        "observed_utc_date":day_utc.isoformat(),
        "read_snapshot_at":queried_at.isoformat(),
        "global_event_count":None,
        "global_counts_disclosed_to_tenant":False,
        "tenant_event_count":scoped,
        "tenant_candidate_amount_cents":total if candidate else None,
        "unknown_or_invalid_global_event_count":None,
        "unknown_or_invalid_tenant_event_count":None,
        "missing_or_hidden_rows_independently_excluded":False,
        "ledger_backfill_finality_attested":False,
        "tenant_authorization_proven":False,
        "source_scoped_internal_consistency_candidate":candidate,
        "source_census_complete_as_of_snapshot":False,
        "source_scoped_not_financially_final":True,
        "daily_revenue_census_verified":False,
        "original_forecast_proven":False,
        "eligible_for_revenue_forecast_calibration":False,
        "execution_authority":"none",
        "revenue_mutation":False,
    }


def read_daily_revenue_census(
    *, day_utc:date, tenant_id:str, as_of:datetime,
    dsn:str, connect_factory:Callable[...,Any]|None=None,
    require_session_tenant_binding:bool=False,
)->dict[str,Any]:
    if type(day_utc) is not date or day_utc>=_utc(as_of).date():
        raise ValueError("completed UTC day required")
    if (not isinstance(tenant_id,str) or not tenant_id.strip()
        or len(tenant_id)>256):
        raise ValueError("explicit bounded tenant required")
    if type(require_session_tenant_binding) is not bool:
        raise ValueError("explicit Boolean tenant-session verification mode required")
    if not isinstance(dsn,str) or not dsn.strip():
        raise CanonicalRevenueEvidenceUnavailable("DEDICATED_CENSUS_CREDENTIAL_MISSING")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError:
            raise CanonicalRevenueEvidenceUnavailable("CENSUS_DB_DRIVER_MISSING") from None
        connect_factory=psycopg.connect
    try:
        with connect_factory(dsn,connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '4000ms'")
                cursor.execute("SET LOCAL ROLE "+READ_ROLE)
                if require_session_tenant_binding:
                    # Existing trusted resolver binds PostgreSQL session_user.
                    # A tenant query parameter or caller-set GUC is NEVER proof.
                    cursor.execute("SELECT public.empire_current_tenant_id()")
                    binding=cursor.fetchone()
                    if (type(binding) not in (tuple,list) or len(binding)!=1
                        or not binding[0] or str(binding[0])!=tenant_id):
                        raise CanonicalRevenueEvidenceUnavailable(
                            "CENSUS_SESSION_TENANT_NOT_AUTHENTICATED")
                cursor.execute(CENSUS_SQL,(day_utc,tenant_id))
                rows=cursor.fetchall()
    except Exception:
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_READ_FAILED") from None
    if type(rows) is not list or len(rows)!=1:
        raise CanonicalRevenueEvidenceUnavailable("DAY_CENSUS_SOURCE_UNPROVEN")
    # A database snapshot is captured after the caller starts this query.
    # Use the observed read-completion time for the post-query timestamp
    # check, not the pre-query as_of (which would reject fresh reads).
    # The direct row validator still rejects snapshots after its as_of.
    read_completed_at=datetime.now(timezone.utc)
    verification_time=max(_utc(as_of),read_completed_at)
    result=verify_daily_census_row(
        rows[0],day_utc=day_utc,tenant_id=tenant_id,as_of=verification_time)
    if require_session_tenant_binding:
        result["database_session_tenant_identity_matched"]=True
        result["customer_tenant_access_authorized_for_delivery"]=False
    return result
