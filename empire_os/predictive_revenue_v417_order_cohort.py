"""Empire Predictive Revenue V4.17: buyer-owned order cohort review.

Only existing EmpireDB roles, original signed Smart CRM and HELD 069.
Current-state order counts, not the full GTM opportunity population.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import CAPABILITY_ROLE, READER_LOGIN
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v417.tenant_order_cohort_held.v1"
SQL = (
    "SELECT selected_order_count,current_state_settled_or_outcome_captured,"
    "current_state_rejected,current_state_cancelled,current_state_other_or_open,"
    "selected_orders_without_opportunity_id,distinct_order_linked_opportunity_ids,"
    "multiple_orders_per_opportunity,complete_buyer_owned_order_window_scanned,"
    "complete_gtm_opportunity_denominator_verified,"
    "historical_status_as_of_window_end_verified,"
    "settled_cash_independently_verified,eligible_for_revenue_model_calibration "
    "FROM public.read_predictive_revenue_tenant_order_cohort_v1("
    "%s::uuid,%s::timestamptz,%s::timestamptz)"
)


def review_v417_tenant_order_cohort_held(
    *,
    research_twin: dict[str, Any],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    window_start: datetime,
    window_end: datetime,
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V417_ORIGINAL_SIMULATION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V417_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ValueError("V417_SIGNED_BEARER_REQUIRED")
    if (type(window_start) is not datetime or type(window_end) is not datetime
        or window_start.tzinfo is None or window_end.tzinfo is None
        or window_start.utcoffset() is None or window_end.utcoffset() is None):
        raise ValueError("V417_AWARE_WINDOW_REQUIRED")
    start = window_start.astimezone(timezone.utc)
    end = window_end.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if not (timedelta(0) < end-start <= timedelta(days=31)
            and end <= now and start>=now-timedelta(days=365*5+2)):
        raise ValueError("V417_BOUNDED_HISTORICAL_WINDOW_REQUIRED")
    if type(dedicated_cash_dsn) is not str or not 1 <= len(dedicated_cash_dsn.strip()) <= 4096:
        raise ValueError("V417_OWNER_MANAGED_DSN_REQUIRED")
    try:
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V417_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant != research_twin["canonical_tenant_id"]:
        raise ValueError("V417_TENANT_IDENTITY_MISMATCH")

    original_connector = connect_factory is None

    def held(status: str, counts: tuple[int, ...] | None = None) -> dict[str, Any]:
        if counts is None:
            counts = (None,) * 7
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": status,
            "canonical_tenant_id": tenant,
            "start_inclusive_utc": start.isoformat(),
            "end_exclusive_utc": end.isoformat(),
            "original_postgresql_connector_used": original_connector,
            "database_endpoint_independently_attested": False,
            "buyer_owned_order_count": counts[0],
            "orders_currently_settled_or_outcome_captured": counts[1],
            "orders_currently_rejected": counts[2],
            "orders_currently_cancelled": counts[3],
            "orders_currently_other_or_open": counts[4],
            "orders_without_opportunity_link": counts[5],
            "distinct_linked_opportunities_in_orders": counts[6],
            "more_than_one_order_can_reference_same_opportunity": (
                (counts[0]-counts[5]) > counts[6] if counts[0] is not None else None
            ),
            "order_cohort_window_complete_under_buyer_ownership": counts[0] is not None,
            "gtm_opportunity_denominator_complete": False,
            "unowned_and_unbound_opportunities_excluded": True,
            "historical_status_as_of_window_end_verified": False,
            "settled_cash_independently_verified": False,
            "refunds_reconciled_to_finance": False,
            "customer_conversion_rate_verified": False,
            "eligible_for_revenue_forecast_calibration": False,
            "actual_revenue_minor_units": None,
            "actual_cash_collected_minor_units": None,
            "economic_memory_write_authorized": False,
            "buyer_outreach_authorized": False,
            "paid_traffic_authorized": False,
            "funds_movement_authorized": False,
            "execution_authority": "none",
        }

    if original_connector:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError:
            return held("V417_RESTRICTED_READER_UNAVAILABLE_HELD")

    try:
        with connect_factory(dedicated_cash_dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE " + CAPABILITY_ROLE)
                cur.execute("SELECT session_user,current_user")
                if cur.fetchone() != (READER_LOGIN, CAPABILITY_ROLE):
                    return held("V417_RESTRICTED_LOGIN_IDENTITY_INVALID_HELD")
                cur.execute(SQL, (tenant,start,end))
                rows = cur.fetchall()
        if type(rows) is not list or len(rows) != 1:
            return held("V417_INCOMPLETE_OR_MALFORMED_COHORT_HELD")
        if type(rows[0]) not in (tuple,list) or len(rows[0]) != 13:
            return held("V417_INCOMPLETE_OR_MALFORMED_COHORT_HELD")
        row = rows[0]
        counts = row[:7]
        duplicates,complete,gtm,historical,cash,calibrated = row[7:]
        if (any(type(x) is not int or not 0 <= x <= 5000 for x in counts)
            or counts[1]+counts[2]+counts[3]+counts[4] != counts[0]
            or counts[5] > counts[0] or counts[6] > counts[0]-counts[5]
            or type(duplicates) is not bool
            or duplicates != ((counts[0]-counts[5]) > counts[6])
            or complete is not True or gtm is not False
            or historical is not False or cash is not False
            or calibrated is not False):
            return held("V417_INCONSISTENT_OR_PROMOTED_COHORT_HELD")
        if not original_connector:
            return held("V417_TEST_CONNECTOR_NOT_CANONICAL_EVIDENCE_HELD")
        return held("V417_BOUNDED_TENANT_ORDER_COHORT_ONLY_HELD",
                    counts=tuple(counts))
    except Exception:
        return held("V417_RESTRICTED_READER_UNAVAILABLE_HELD")
