"""Per-product prospective conversion baseline, prepared before future outcome.

Reuse existing verified-feedback consumer and original Quant preflight.
This is NOT a registry receipt, authenticated source read, customer conversion
probability, settled economic value, or authority for an autonomous action.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from empire_os.predictive_intelligence import build_product_estimate
from empire_os.predictive_calibration import prepare_prospective_conversion_prediction

SCHEMA = "empire.predictive_revenue.product_prospective_baseline.v1"
MAX_OUTCOMES = 500
MIN_TERMINAL = 20
MAX_HORIZON_DAYS = 90


class ProspectiveProductHold(ValueError):
    """Refuse contradictory cross-tenant or cross-product source evidence."""


def _required(value: Any, field: str) -> str:
    if (type(value) is not str or not value.strip()
            or value != value.strip() or len(value) > 128):
        raise ProspectiveProductHold(f"{field} required")
    return value


def _owner_bound_catalogue_id(catalog: Mapping[str, Any], code: str) -> str:
    if (not isinstance(catalog, Mapping)
            or type(catalog.get("products")) is not list
            or len(catalog["products"]) > 500):
        raise ProspectiveProductHold("original verified catalog version required")
    matches: list[str] = []
    seen = set()
    for row in catalog["products"]:
        if not isinstance(row, Mapping):
            raise ProspectiveProductHold("original catalog row invalid")
        pid, sku = row.get("product_id"), row.get("product_code")
        if (type(pid) is not str or not pid or type(sku) is not str or not sku):
            continue
        if pid in seen:
            raise ProspectiveProductHold("ambiguous original product identity")
        seen.add(pid)
        if (sku == code and row.get("catalog_state") == "VERIFIED"
                and row.get("version_state") == "VERIFIED"):
            matches.append(pid)
    if len(matches) != 1:
        raise ProspectiveProductHold("unique version-verified original SKU required")
    return matches[0]


def prepare_product_prospective_baseline(
    *, tenant_id: str, product_code: str, opportunity_key: str,
    historical_outcomes: Sequence[Mapping[str, Any]],
    catalog: Mapping[str, Any], as_of: datetime,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """Produce an unregistered shadow forecast, never a calibrated customer claim.

    Historical feedback carries the existing full verified-feedback contract,
    but its ref strings can be forged. Original source owner must attest facts
    separately before any real-world forecast/learning is enabled.
    """
    tenant = _required(tenant_id, "tenant_id")
    code = _required(product_code, "product_code")
    opportunity = _required(opportunity_key, "opportunity_key")
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProspectiveProductHold("aware forecast issuance date required")
    moment = as_of.astimezone(timezone.utc)
    if type(horizon_days) is not int or not 1 <= horizon_days <= MAX_HORIZON_DAYS:
        raise ProspectiveProductHold("fixed bounded horizon required")
    pid = _owner_bound_catalogue_id(catalog, code)
    if (type(historical_outcomes) not in (list, tuple)
            or len(historical_outcomes) > MAX_OUTCOMES):
        raise ProspectiveProductHold("bounded terminal outcome cohort required")
    if any(not isinstance(row, Mapping)
           or row.get("tenant_id") != tenant
           or row.get("product_id") != pid
           for row in historical_outcomes):
        raise ProspectiveProductHold("original outcome tenant/SKU lineage mismatch")
    seen_orders: set[str] = set()
    for row in historical_outcomes:
        order = row.get("fulfilment_order_id")
        if type(order) is not str or not order or order in seen_orders:
            raise ProspectiveProductHold("duplicate or missing original order")
        seen_orders.add(order)
        date = row.get("available_at")
        if type(date) is not str:
            raise ProspectiveProductHold("original outcome availability required")
        try:
            ready_at = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError:
            raise ProspectiveProductHold("invalid original outcome availability") from None
        if ready_at.utcoffset() is None or ready_at.astimezone(timezone.utc) >= moment:
            raise ProspectiveProductHold("hindsight or unscoped source outcome")
    try:
        estimate = build_product_estimate(
            code, historical_outcomes, tenant_id=tenant,
            as_of=moment, min_terminal_samples=MIN_TERMINAL,
            min_timing_samples=8,
        )
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ProspectiveProductHold("original verified feedback rejected") from None
    n = estimate.get("terminal_outcome_count")
    probability = estimate.get("probability_success")
    if (estimate.get("probability_available") is not True or
            type(n) is not int or n < MIN_TERMINAL or
            type(probability) not in (float, int)):
        return {
            "schema_version": SCHEMA, "mode": "OBSERVE",
            "status": "INSUFFICIENT_ORIGINAL_TERMINAL_OUTCOMES",
            "product_code": code, "terminal_sample_count": n,
            "product_cohort_probability": None,
            "cohort_wilson_interval_95": None,
            "original_forecast_registered": False,
            "source_issuer_authenticated": False,
            "customer_probability_claim": False,
            "learning_eligible": False, "execution_authority": "none",
        }
    original_refs = sorted(row["outcome_ref"] for row in historical_outcomes)
    digest = sha256("\n".join(original_refs).encode("utf-8")).hexdigest()
    # Hash is integrity only and does not authenticate original source custody.
    preflight = prepare_prospective_conversion_prediction(
        tenant_id=tenant, opportunity_key=opportunity,
        predicted_probability=probability,
        predicted_at=moment.isoformat(),
        horizon_until=(moment + timedelta(days=horizon_days)).isoformat(),
        evidence_refs=[
            "cohort:validated-feedback-contract-only",
            "cohort:digest-untrusted-" + digest,
        ],
        model_name="empire-product-cohort-beta-baseline",
        model_version="shadow-v1",
        assessed_at=moment,
    )
    if (preflight.get("original_prediction_registered") is not False
            or preflight.get("canonical_registry_readback_verified") is not False
            or preflight.get("may_use_in_verified_calibration") is not False):
        raise ProspectiveProductHold("prospective candidate unexpectedly promoted")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "COHORT_PROSPECTIVE_CANDIDATE_UNREGISTERED",
        "product_code": code,
        "terminal_sample_count": n,
        "won_count": estimate.get("success_count"),
        "lost_count": estimate.get("failure_count"),
        "product_cohort_probability": probability,
        "cohort_wilson_interval_95": estimate.get("wilson_interval_95"),
        "prediction_confidence_interval_for_individual_customer": None,
        "probability_is_product_cohort_not_personalized": True,
        "time_to_revenue_days_eligible": estimate.get("time_to_revenue_available"),
        "time_to_revenue_days": estimate.get("time_to_revenue_days"),
        "original_forecast_candidate_digest_untrusted":
            preflight["candidate_prediction_ref"],
        "original_forecast_registered": False,
        "original_forecast_registry_readback_authenticated": False,
        "source_issuer_authenticated": False,
        "tenant_authority_authenticated": False,
        "customer_probability_claim": False,
        "model_training_authorized": False,
        "learning_eligible": False,
        "commercial_value_claim": False,
        "actual_revenue_verified_by_this_review": False,
        "payment_action": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }
