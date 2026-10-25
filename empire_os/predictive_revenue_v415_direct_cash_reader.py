"""EmpireOS V4.15: bounded original-EmpireDB direct BSC transfer candidates.

Read-only, caller must supply dedicated owner provisioned credentials, native
CRM verifier, and exact order IDs. Missing 067 or unapproved login remains
HELD. This does NOT attest refunds, finality or collected fiat cash.
"""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_revenue_v413_canonical_coverage import (
    _original_twin_contract,
)
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v415.direct_bsc_cash_candidate_read.v1"
READER_LOGIN = "empire_predictive_cash_candidate_login"
CAPABILITY_ROLE = "empire_predictive_cash_candidate_reader"
SQL = (
    "SELECT selected_order_id::text,evidence_status,"
    "selected_direct_usdt_candidate_usd_cents,"
    "payment_and_tenant_lineage_matches,"
    "independent_refund_finality_verified,"
    "cash_collected_by_finance_verified,commercial_action_authorized "
    "FROM public.read_predictive_direct_bsc_cash_candidate_v1("
    "%s::uuid,%s::uuid[])"
)
POSITIVE = "DIRECT_USDT_BSC_TRANSFER_CANDIDATE_HELD"
NEGATIVE = "NO_UNAMBIGUOUS_DIRECT_BSC_EVIDENCE_HELD"


def _order_id(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = UUID(value)
        return str(parsed) == value and parsed.version in (4, 7)
    except (ValueError, TypeError, AttributeError):
        return False


def review_v415_cash_candidates_held(
    *,
    research_twin: dict[str, Any],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    exact_order_ids: tuple[str, ...],
    dedicated_cash_dsn: str,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    if not _original_twin_contract(research_twin):
        raise ValueError("V415_ORIGINAL_NONPROMOTABLE_TWIN_REQUIRED")
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V415_CANONICAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ValueError("V415_VALID_SIGNED_BEARER_REQUIRED")
    if (
        type(exact_order_ids) is not tuple
        or not 1 <= len(exact_order_ids) <= 8
        or any(not _order_id(i) for i in exact_order_ids)
        or len(set(exact_order_ids)) != len(exact_order_ids)
    ):
        raise ValueError("V415_BOUNDED_UNIQUE_CANONICAL_ORDER_IDS_REQUIRED")
    if (
        type(dedicated_cash_dsn) is not str or not dedicated_cash_dsn.strip()
        or len(dedicated_cash_dsn) > 4096
    ):
        raise ValueError("V415_DEDICATED_CASH_READER_CREDENTIAL_REQUIRED")
    try:
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V415_ACTIVE_CRM_TENANT_MEMBERSHIP_REQUIRED") from None
    if tenant != research_twin["canonical_tenant_id"]:
        raise ValueError("V415_CRM_TWIN_TENANT_MISMATCH")

    original_connector = connect_factory is None

    def held(status: str, *, matching: int = 0, unknown: int | None = None):
        return {
            "schema_version": SCHEMA,
            "mode": "OBSERVE",
            "status": status,
            "original_postgresql_connector_used": original_connector,
            "database_endpoint_independently_attested": False,
            "canonical_tenant_id": tenant,
            "requested_exact_order_count": len(exact_order_ids),
            "direct_transfer_candidate_count": matching,
            "unknown_or_unverified_order_count": (
                len(exact_order_ids) if unknown is None else unknown
            ),
            "source_currency": "USDT_BSC_DIRECT_ONLY",
            "assumed_buyer_price_unit": "USD_CENTS_NOT_FIAT_RECONCILED",
            "research_twin_currency": research_twin["currency_code"],
            "claim_not_collected_cash": True,
            "candidate_selection_not_complete_cohort": True,
            "escrow_payments_not_audited": True,
            "refunds_and_chargebacks_not_audited": True,
            "offchain_bank_settlement_not_audited": True,
            "actual_cash_collected_minor_units": None,
            "actual_revenue_recognized_by_this_read": False,
            "revenue_forecast_calibration_eligible": False,
            "commercial_delivery_authorized": False,
            "paid_traffic_authorized": False,
            "funds_movement_authorized": False,
            "execution_authority": "none",
        }

    if connect_factory is None:
        try:
            import psycopg
            connect_factory = psycopg.connect
        except ImportError:
            return held("V415_DEDICATED_READER_UNAVAILABLE_HELD")
    try:
        with connect_factory(dedicated_cash_dsn, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute("SET LOCAL ROLE " + CAPABILITY_ROLE)
                cur.execute("SELECT session_user, current_user")
                if cur.fetchone() != (READER_LOGIN, CAPABILITY_ROLE):
                    return held("V415_DEDICATED_READER_IDENTITY_INVALID_HELD")
                cur.execute(SQL, (tenant, list(exact_order_ids)))
                rows = cur.fetchall()
        if type(rows) is not list or len(rows) != len(exact_order_ids):
            return held("V415_INCOMPLETE_OR_DUPLICATE_RESULT_HELD")
        approved: dict[str, bool] = {}
        for row in rows:
            if type(row) not in (tuple, list) or len(row) != 7:
                return held("V415_MALFORMED_OR_UNAUTHENTICATED_RESULT_HELD")
            ident,status,amount,match,refund,cash,authority = row
            if not _order_id(ident) or ident not in exact_order_ids or ident in approved:
                return held("V415_UNSCOPED_OR_DUPLICATE_RESULT_HELD")
            if (
                refund is not False or cash is not False or authority is not False
                or type(match) is not bool
                or status not in (POSITIVE,NEGATIVE)
                or (status == POSITIVE) != match
                or (
                    (type(amount) is int and 1 <= amount <= 100000000000)
                    if match else amount is None
                ) is not True
            ):
                return held("V415_AMBIGUOUS_FINANCIAL_PROOF_HELD")
            approved[ident] = match
        if set(approved) != set(exact_order_ids):
            return held("V415_RESULT_ORDER_SET_MISMATCH_HELD")
        if not original_connector:
            return held("V415_TEST_INJECTED_CONNECTOR_NOT_SOURCE_PROOF_HELD")
        positives = sum(approved.values())
        return held(
            "V415_SCOPED_DIRECT_TRANSFER_CANDIDATES_ONLY_HELD",
            matching=positives,unknown=len(exact_order_ids)-positives,
        )
    except Exception:
        return held("V415_DEDICATED_READER_UNAVAILABLE_HELD")
