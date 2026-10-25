"""Predictive Revenue V4.13: bounded canonical evidence coverage audit.

Use original signed Smart CRM tenant membership and existing REV051/052
restricted single-event read. A single recognized revenue event does not prove
collected cash, complete cohort outcomes, source rights, or calibrated forecasts.
Never writes to canonical EmpireDB or activates commercial controls.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Callable
from uuid import UUID

from empire_os.predictive_revenue_canonical_reader import (
    read_recognized_revenue_event,
)
from empire_os.predictive_revenue_v412_scenario_twin import SCHEMA as TWIN_SCHEMA
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v413.canonical_coverage_audit_held.v1"
MAX_EVENTS = 8


def _canonical_uuid(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value and UUID(value).int != 0
    except (TypeError, ValueError):
        return False


def _original_twin_contract(twin: object) -> bool:
    if type(twin) is not dict or twin.get("schema_version") != TWIN_SCHEMA:
        return False
    if (
        twin.get("mode") != "SIMULATION"
        or twin.get("simulation_only") is not True
        or twin.get("execution_authority") != "none"
        or twin.get("licensed_source_admitted") is not False
        or twin.get("forecast_empirically_calibrated") is not False
        or twin.get("approved_commercial_forecast") is not False
        or twin.get("revenue_recognised_cents") is not None
    ):
        return False
    if (
        twin.get("currency_code") not in ("GBP", "USD", "EUR")
        or not _canonical_uuid(twin.get("canonical_tenant_id"))
    ):
        return False
    horizons = twin.get("forecast_horizons")
    if type(horizons) is not dict or set(horizons) != {"30", "60", "90"}:
        return False
    for item in horizons.values():
        if type(item) is not dict:
            return False
        vals = [item.get(f"{p}_gross_cash_cents") for p in ("p10", "p50", "p90")]
        if any(type(v) is not int or v < 0 for v in vals) or vals != sorted(vals):
            return False
    return True


def review_v413_canonical_evidence_coverage_held(
    *,
    research_twin: dict[str, Any],
    candidate_event_ids: tuple[str, ...],
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    dedicated_revenue_dsn: str,
    as_of: datetime,
    event_reader: Callable[..., dict[str, Any]] = read_recognized_revenue_event,
) -> dict[str, Any]:
    """At most eight explicit candidate IDs; no discovery or mass event exports.

    Trust positive event evidence only from the unmodified original restricted
    reader, never a caller-injected mock. Test injection measures diagnostics
    but can never assert production evidence. No currency exists in REV051
    response, so no comparison with V4.12 GBP/USD/EUR cash trajectories.
    """
    if type(crm_verifier) is not SignedCrmTenantVerifier:
        raise ValueError("V413_ORIGINAL_CRM_VERIFIER_REQUIRED")
    if type(signed_crm_bearer) is not str or not 1 <= len(signed_crm_bearer) <= 4096:
        raise ValueError("V413_SIGNED_BEARER_REQUIRED")
    if not _original_twin_contract(research_twin):
        raise ValueError("V413_UNTRUSTED_TWIN_CONTRACT")
    if (
        type(candidate_event_ids) is not tuple
        or len(candidate_event_ids) > MAX_EVENTS
        or any(not _canonical_uuid(i) for i in candidate_event_ids)
        or len(set(candidate_event_ids)) != len(candidate_event_ids)
    ):
        raise ValueError("V413_BOUNDED_UNIQUE_EVENT_IDS_REQUIRED")
    if (
        type(dedicated_revenue_dsn) is not str
        or not dedicated_revenue_dsn.strip()
        or len(dedicated_revenue_dsn) > 4096
    ):
        raise ValueError("V413_DEDICATED_REVENUE_READER_DSN_REQUIRED")
    if (
        type(as_of) is not datetime or as_of.tzinfo is None
        or as_of.utcoffset() is None
    ):
        raise ValueError("V413_AWARE_AS_OF_REQUIRED")
    try:
        tenant = crm_verifier.authenticate(signed_crm_bearer)
    except Exception:
        raise ValueError("V413_ACTIVE_CRM_MEMBERSHIP_REQUIRED") from None
    if tenant != research_twin["canonical_tenant_id"]:
        raise ValueError("V413_CRM_TWIN_TENANT_MISMATCH")
    original_reader = event_reader is read_recognized_revenue_event
    result_refs: list[str] = []
    errors = 0
    for event_id in candidate_event_ids:
        try:
            found = event_reader(
                event_id=event_id, tenant_id=tenant,
                as_of=as_of, dsn=dedicated_revenue_dsn,
            )
            if (
                type(found) is not dict
                or found.get("schema_version") != "empire.predictive_revenue.verified_event_read.v1"
                or found.get("status") != "SINGLE_REVENUE_EVENT_VERIFIED"
                or found.get("canonical_event_ref") != "canonical:commercial_events:" + event_id
                or found.get("order_bound") is not True
                or found.get("tenant_lineage_matched") is not True
                or found.get("product_and_price_matched") is not True
                or found.get("single_event_not_daily_aggregate") is not True
                or found.get("daily_revenue_census_verified") is not False
                or found.get("forecast_source_verified") is not False
                or found.get("revenue_recognition_performed") is not False
                or found.get("execution_authority") != "none"
                or type(found.get("amount_cents")) is not int
                or found.get("amount_cents") <= 0
            ):
                errors += 1
            else:
                result_refs.append(sha256(event_id.encode("ascii")).hexdigest()[:16])
        except Exception:
            # Dedicated credentials and source records cannot leak via errors.
            errors += 1

    total = len(candidate_event_ids)
    verified = len(result_refs) if original_reader else 0
    return {
        "schema_version": SCHEMA,
        "status": (
            "NO_EVENT_CANDIDATES_CENSUS_UNKNOWN_HELD" if total == 0
            else "ONE_OR_MORE_CANONICAL_EVENTS_ONLY_COHORT_UNKNOWN_HELD"
            if verified and errors == 0
            else "EVENT_COVERAGE_UNAVAILABLE_HELD"
        ),
        "mode": "OBSERVE",
        "source_rights_decision": research_twin.get("source_rights_decision"),
        "simulated_currency": research_twin["currency_code"],
        "observed_canonical_event_currency": None,
        "candidate_ids_supplied": total,
        "single_event_reads_verified": verified,
        "sanitized_rejected_or_missing_count": errors,
        "event_ref_fingerprints": tuple(result_refs) if original_reader else (),
        "reader_independently_original": original_reader,
        "forecast_metric": "simulated_gross_collectible_cash",
        "observed_metric": "single_revenue_recognition_event",
        "recognition_vs_cash_metric_mismatch": True,
        "event_currency_verified": False,
        "complete_30_60_90_cohort_census_verified": False,
        "revenue_cohort_coverage_verified": False,
        "revenue_forecast_calibration_eligible": False,
        "unverified_events_are_not_zero_revenue": True,
        "actual_revenue_total_cents": None,
        "cash_collected_total_cents": None,
        "forecast_model_updated": False,
        "economic_memory_write_authorized": False,
        "source_ingestion_authorized": False,
        "buyer_outreach_authorized": False,
        "paid_traffic_authorized": False,
        "execution_authority": "none",
    }
