"""Canonical Analytics -> CRM -> Finance owner-evidence join; read-only.

This module never queries or edits EmpireDB. Exact original-owner evidence
readers must provide authenticated, privacy-reviewed aggregate contracts.
Mapping assertions do not themselves authenticate identity or payment finality.
No PII, order IDs, buyer contacts, raw sessions, client tokens or dollar
claims from unverified adapter inputs are returned to acquisition research.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from empire_os.analytics.acquisition_source_v2_candidate import ALL_EVIDENCE

SCHEMA = "empire.analytics.original_crm_finance_lineage_review.v1"
EXACT_KIND = {
    "analytics": (
        "empire.analytics.original_collection_owner_cohort.v1",
        "ORIGINAL_ANALYTICS_TENANT_AGGREGATE_READER",
        "observed_consented_sessions", "observed_cta_sessions",
    ),
    "crm": (
        "empire.crm.original_accepted_order_cohort.v1",
        "ORIGINAL_CRM_TENANT_ACCEPTED_ORDER_READER",
        "accepted_order_count", "source_linked_orders",
    ),
    "finance": (
        "empire.finance.original_settlement_cohort.v1",
        "ORIGINAL_FINANCE_SETTLEMENT_READER",
        "settled_order_count", "actual_cash_received_minor_units",
    ),
}
COUNT_LIMIT = 1_000_000
AMOUNT_LIMIT = 10**12


def _canonical_uuid(value: Any) -> str:
    if type(value) is not str:
        raise ValueError("ORIGINAL_COHORT_TENANT_ID_UNVERIFIED")
    try:
        candidate = UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("ORIGINAL_COHORT_TENANT_ID_UNVERIFIED") from None
    if str(candidate) != value or candidate.version not in (4, 7):
        raise ValueError("ORIGINAL_COHORT_TENANT_ID_UNVERIFIED")
    return value


def _clock(value: Any) -> datetime:
    if type(value) is not str or len(value) > 35:
        raise ValueError("ORIGINAL_COHORT_TIME_INVALID")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except ValueError:
        raise ValueError("ORIGINAL_COHORT_TIME_INVALID") from None


def _count(value: Any, *, max_value: int = COUNT_LIMIT) -> int:
    if type(value) is not int or not 0 <= value <= max_value:
        raise ValueError("ORIGINAL_COHORT_NUMERIC_VALUE_INVALID")
    return value


def _safe_ref(value: Any) -> bool:
    return (type(value) is str and 12 <= len(value) <= 120
            and all(c.isascii() and (c.isalnum() or c in "_:-.")
                    for c in value))


def _validate(kind: str, record: Any) -> dict:
    schema, source, count_a, count_b = EXACT_KIND[kind]
    fields = {
        "schema_version", "mode", "canonical_tenant_id", "property_key",
        "source_cohort_ref", "acquisition_channel", "window_start_utc",
        "window_end_utc", "original_reader_source", "owner_evidence_ref",
        "authenticated_original_owner_assertion", count_a, count_b,
        "execution_authority",
    }
    if kind == "analytics":
        fields |= {"lawful_analytics_consent_verified",
                   "trusted_source_classification_verified"}
    if kind == "crm":
        fields |= {"independent_source_order_join_verified"}
    if kind == "finance":
        fields |= {"settlement_finality_verified", "refunds_reconciled",
                   "costs_reconciled", "currency_code",
                   "verified_source_cost_minor_units"}
    if (not isinstance(record, Mapping) or set(record) != fields
            or record.get("schema_version") != schema
            or record.get("mode") != "READ_ONLY"
            or record.get("original_reader_source") != source
            or record.get("execution_authority") != "NONE"
            or record.get("property_key") != "empire-ai.co.uk"
            or not _safe_ref(record.get("source_cohort_ref"))
            or not _safe_ref(record.get("owner_evidence_ref"))
            or type(record.get("acquisition_channel")) is not str
            or record["acquisition_channel"] not in ALL_EVIDENCE
            or type(record.get("authenticated_original_owner_assertion")) is not bool):
        raise ValueError("UNTRUSTED_OR_PII_BEARING_ORIGINAL_COHORT")
    _canonical_uuid(record["canonical_tenant_id"])
    start, end = (_clock(record["window_start_utc"]),
                  _clock(record["window_end_utc"]))
    if not timedelta(0) < end - start <= timedelta(days=31):
        raise ValueError("ORIGINAL_COHORT_WINDOW_OUT_OF_BOUNDS")
    a = _count(record[count_a])
    b = _count(record[count_b], max_value=(
        AMOUNT_LIMIT if kind == "finance" else COUNT_LIMIT
    ))
    if kind != "finance" and b > a:
        raise ValueError("ORIGINAL_COHORT_STAGE_COUNT_CONFLICT")
    if kind == "analytics":
        for flag in ("lawful_analytics_consent_verified",
                     "trusted_source_classification_verified"):
            if type(record[flag]) is not bool:
                raise ValueError("ANALYTICS_ORIGINAL_OWNER_AUTHORITY_MALFORMED")
    if kind == "crm" and type(record["independent_source_order_join_verified"]) is not bool:
        raise ValueError("CRM_SOURCE_ORDER_JOIN_MALFORMED")
    if kind == "finance":
        if (type(record["settlement_finality_verified"]) is not bool
                or type(record["refunds_reconciled"]) is not bool
                or type(record["costs_reconciled"]) is not bool
                or type(record["currency_code"]) is not str
                or record["currency_code"] not in ("GBP", "USD")):
            raise ValueError("FINANCE_OWNER_RECONCILIATION_INVALID")
        _count(record["actual_cash_received_minor_units"], max_value=AMOUNT_LIMIT)
        _count(record["verified_source_cost_minor_units"], max_value=AMOUNT_LIMIT)
    return dict(record)


def review_owner_source_to_cash(
    *, analytics: Mapping[str, Any] | None = None,
    crm: Mapping[str, Any] | None = None,
    finance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Enforce contract coherence. NEVER authenticate the supplied owner claims."""
    owners = {"analytics": analytics, "crm": crm, "finance": finance}
    verified = {name: _validate(name, record)
                for name, record in owners.items() if record is not None}
    reference = next(iter(verified.values()), None)
    cohort = None
    if reference is not None:
        cohort = {
            field: reference[field] for field in (
                "canonical_tenant_id", "property_key", "source_cohort_ref",
                "acquisition_channel", "window_start_utc", "window_end_utc",
            )
        }
        for row in verified.values():
            if any(row[field] != reference[field] for field in cohort):
                raise ValueError("CROSS_OWNER_TENANT_SOURCE_OR_WINDOW_MISMATCH")
    if "analytics" in verified and "crm" in verified:
        if (verified["crm"]["source_linked_orders"]
                > verified["crm"]["accepted_order_count"]):
            raise ValueError("SOURCE_LINKED_ORDERS_EXCEED_ACCEPTED")
        # Order counts can exceed visitor sessions (repeat orders); no 1:1
        # attribution is manufactured in the absence of authenticated joins.
    if "crm" in verified and "finance" in verified:
        if verified["finance"]["settled_order_count"] > verified["crm"]["accepted_order_count"]:
            raise ValueError("SETTLED_ORDERS_EXCEED_ACCEPTED_ORDERS")
    gates = {
        "original_analytics_read": (
            "analytics" in verified
            and verified["analytics"]["authenticated_original_owner_assertion"] is True
            and verified["analytics"]["lawful_analytics_consent_verified"] is True
            and verified["analytics"]["trusted_source_classification_verified"] is True
        ),
        "original_crm_accepted_order_read": (
            "crm" in verified
            and verified["crm"]["authenticated_original_owner_assertion"] is True
            and verified["crm"]["independent_source_order_join_verified"] is True
        ),
        "original_finance_cash_and_cost_read": (
            "finance" in verified
            and verified["finance"]["authenticated_original_owner_assertion"] is True
            and all(verified["finance"][flag] is True for flag in (
                "settlement_finality_verified", "refunds_reconciled",
                "costs_reconciled",
            ))
        ),
    }
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": ("ALL_ORIGINAL_OWNER_ASSERTIONS_PRESENT_NOT_INDEPENDENTLY_AUTHENTICATED"
                   if all(gates.values())
                   else "HOLD_ORIGINAL_OWNER_EVIDENCE_INCOMPLETE"),
        "source_cohort_ref": cohort["source_cohort_ref"] if cohort else None,
        "acquisition_channel": cohort["acquisition_channel"] if cohort else None,
        "owner_assertion_gates": gates,
        "missing_original_owner_proofs": sorted(k for k, value in gates.items()
                                                if value is not True),
        "owner_inputs_do_not_authenticate_themselves": True,
        "source_to_crm_conversion_independently_proven_by_this_review": False,
        "source_to_finance_cash_independently_proven_by_this_review": False,
        "verified_revenue_minor_units": None,
        "verified_cash_margin_minor_units": None,
        "eligible_for_predictive_revenue_training": False,
        "crm_writes": False, "finance_writes": False,
        "database_queries_executed": False,
        "ingress_or_collector_activated": False,
        "paid_media_authorized": False,
        "execution_authority": "NONE",
    }
