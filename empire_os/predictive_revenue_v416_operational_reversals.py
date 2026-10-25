"""V4.16: original CRM + held operational reversal signals (NOT refund proof).

Uses existing V4.15 exact one-tenant cash-candidate capability, and PREPARED
migration 068. Never reads financial raw tables, recognises revenue, mutates
production, or produces a net cash amount.
"""
from __future__ import annotations

from typing import Any, Callable

from empire_os.predictive_revenue_v413_canonical_coverage import _original_twin_contract
from empire_os.predictive_revenue_v415_direct_cash_reader import (
    CAPABILITY_ROLE, READER_LOGIN, _order_id,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v416.operational_reversal_audit_held.v1"
SQL = (
    "SELECT selected_order_id::text,operational_signal_status,"
    "refunded_delivery_signal_count,failed_or_rejected_delivery_signal_count,"
    "monetary_reversal_independently_verified,full_refund_census_verified,"
    "net_cash_earned_verified,automatic_execution_authorized "
    "FROM public.read_predictive_revenue_reversal_signals_v1(%s::uuid,%s::uuid[])"
)
STATES = frozenset((
    "REFUND_LIKE_DELIVERY_SIGNAL_HELD",
    "FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD",
    "NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD",
    "ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD",
))


def review_v416_reversal_signals_held(
    *,
    research_twin: dict[str, Any],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    exact_order_ids: tuple[str, ...],
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V416_ORIGINAL_SIMULATION_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V416_ORIGINAL_SIGNED_CRM_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ValueError("V416_SIGNED_BEARER_REQUIRED")
    if (type(exact_order_ids) is not tuple or not 1 <= len(exact_order_ids) <= 8
        or len(set(exact_order_ids)) != len(exact_order_ids)
        or any(not _order_id(i) for i in exact_order_ids)):
        raise ValueError("V416_UNIQUE_BOUNDED_ORDER_IDS_REQUIRED")
    if (type(dedicated_cash_dsn) is not str or not 1 <= len(dedicated_cash_dsn.strip()) <= 4096):
        raise ValueError("V416_OWNER_MANAGED_READER_DSN_REQUIRED")
    try:
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V416_ACTIVE_SIGNED_CRM_MEMBER_REQUIRED") from None
    if tenant != research_twin["canonical_tenant_id"]:
        raise ValueError("V416_TENANT_MISMATCH")

    original_connector = connect_factory is None
    def held(status: str, *, refund_signals: int = 0, failure_signals: int = 0,
             invisible: int | None = None) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": status,
            "canonical_tenant_id": tenant,
            "source_evidence_digest": research_twin["source_evidence_digest"],
            "requested_exact_orders": len(exact_order_ids),
            "original_postgresql_connector_used": original_connector,
            "database_endpoint_independently_attested": False,
            "orders_with_refund_like_delivery_signal": refund_signals,
            "orders_with_failure_or_rejection_delivery_signal": failure_signals,
            "orders_with_unknown_visibility": (
                len(exact_order_ids) if invisible is None else invisible
            ),
            "operational_delivery_outcome_is_not_payment_refund": True,
            "absence_of_refund_signal_proves_refund_absence": False,
            "full_reversal_event_census_verified": False,
            "full_opportunity_cohort_verified": False,
            "source_rights_verified": False,
            "bank_or_onchain_refund_verified": False,
            "refund_and_chargeback_finality_verified": False,
            "net_cash_earned_minor_units": None,
            "forecast_calibration_authorized": False,
            "economic_memory_write_authorized": False,
            "buyer_outreach_authorized": False,
            "paid_traffic_authorized": False,
            "funds_movement_authorized": False,
            "execution_authority": "none",
        }

    if connect_factory is None:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError:
            return held("V416_READER_NOT_AVAILABLE_HELD")
    try:
        with connect_factory(dedicated_cash_dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE " + CAPABILITY_ROLE)
                cur.execute("SELECT session_user, current_user")
                if cur.fetchone() != (READER_LOGIN, CAPABILITY_ROLE):
                    return held("V416_READER_IDENTITY_INVALID_HELD")
                cur.execute(SQL, (tenant, list(exact_order_ids)))
                rows = cur.fetchall()
        if type(rows) is not list or len(rows) != len(exact_order_ids):
            return held("V416_INCOMPLETE_RESULT_SET_HELD")
        matched: dict[str, str] = {}
        for row in rows:
            if type(row) not in (tuple, list) or len(row) != 8:
                return held("V416_MALFORMED_SIGNAL_RESULT_HELD")
            ident,status,refunded,failed,reversed_finance,census,net_cash,authority = row
            if (not _order_id(ident) or ident not in exact_order_ids
                or ident in matched or status not in STATES
                or type(refunded) is not int or not 0 <= refunded <= 100000
                or type(failed) is not int or not 0 <= failed <= 100000
                or reversed_finance is not False or census is not False
                or net_cash is not False or authority is not False):
                return held("V416_UNAUTHENTICATED_OR_OVERPRIVILEGED_RESULT_HELD")
            if not (
                (status == "REFUND_LIKE_DELIVERY_SIGNAL_HELD" and refunded > 0)
                or (status == "FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD"
                    and refunded == 0 and failed > 0)
                or (status in ("NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD",
                               "ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD")
                    and refunded == 0 and failed == 0)
            ):
                return held("V416_INCONSISTENT_DELIVERY_SIGNAL_HELD")
            matched[ident] = status
        if set(matched) != set(exact_order_ids):
            return held("V416_ORDER_SET_MISMATCH_HELD")
        if not original_connector:
            return held("V416_TEST_CONNECTOR_NOT_INDEPENDENT_EVIDENCE_HELD")
        return held(
            "V416_BOUNDED_OPERATIONAL_REVERSAL_OBSERVATIONS_HELD",
            refund_signals=sum(x == "REFUND_LIKE_DELIVERY_SIGNAL_HELD"
                               for x in matched.values()),
            failure_signals=sum(x == "FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD"
                               for x in matched.values()),
            invisible=sum(x == "ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD"
                          for x in matched.values()),
        )
    except Exception:
        return held("V416_READER_NOT_AVAILABLE_HELD")
