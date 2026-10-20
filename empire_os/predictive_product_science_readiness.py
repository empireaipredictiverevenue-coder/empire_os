"""Read-only Predictive Revenue product science admission from ORIGINAL snapshots.

Surface scientific readiness per catalogued SKU. Existing owner materializers
are responsible for the underlying source. Filesystem custody is NOT a signed
issuer receipt, a tenant login, a paid order or verified customer outcome.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.predictive_catalog_readiness_bridge import (
    ProductContractHold, _read_bounded_file,
    _stamp, MAX_AGE_SECONDS, MAX_CLOCK_SKEW_SECONDS,
    review_existing_local_catalogue,
)

SOURCE = Path("/srv/empire_os/runtime/predictive_intelligence/latest.json")
SCHEMA = "empire.predictive_revenue.product_science_readiness.v1"
SNAPSHOT_SCHEMA = "empire.predictive_intelligence.v1"
HOLD_CODE = "ORIGINAL_TERMINAL_PRODUCT_EVIDENCE_NOT_VERIFIED"


def _integer(value: Any, key: str) -> int:
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise ProductContractHold(f"{key} invalid")
    return value


def science_source_status(
    catalog_report: Mapping[str, Any], intelligence: Mapping[str, Any], *,
    as_of: datetime,
) -> dict[str, Any]:
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ProductContractHold("trusted science review time required")
    if (not isinstance(catalog_report, Mapping)
            or catalog_report.get("schema_version") !=
                "empire.predictive_revenue.catalog_original_readiness.v1"
            or catalog_report.get("mode") != "OBSERVE"
            or catalog_report.get("source_original_db_receipt_authenticated") is not False
            or catalog_report.get("source_root_custody_verified") is not True
            or catalog_report.get("execution_authority") != "none"
            or type(catalog_report.get("products")) is not list):
        raise ProductContractHold("original catalogue readiness owner not admitted")
    if (not isinstance(intelligence, Mapping)
            or intelligence.get("schema_version") != SNAPSHOT_SCHEMA
            or intelligence.get("mode") != "OBSERVE"
            or intelligence.get("probability_source") !=
                "verified_terminal_commercial_outcomes_only"
            or intelligence.get("prediction_only") is not True
            or intelligence.get("model_weight_mutation") is not False
            or intelligence.get("commercial_authority") != "none"
            or intelligence.get("execution_authority") != "none"
            or intelligence.get("search_scores_used") is not False
            or intelligence.get("llm_probability_used") is not False
            or intelligence.get("unverified_pipeline_state_used_as_outcome") is not False):
        raise ProductContractHold("predictive intelligence source contract not satisfied")
    age = (as_of.astimezone(timezone.utc) -
           _stamp(intelligence.get("generated_at"))).total_seconds()
    if not -MAX_CLOCK_SKEW_SECONDS <= age <= MAX_AGE_SECONDS:
        raise ProductContractHold("predictive intelligence source stale or future")
    outcomes = _integer(intelligence.get("source_outcome_count"), "source_outcome_count")
    matched = _integer(intelligence.get("matched_outcome_count"), "matched_outcome_count")
    unmatched = _integer(intelligence.get("unmatched_outcome_count"), "unmatched_outcome_count")
    if matched + unmatched != outcomes:
        raise ProductContractHold("source outcome accounting inconsistent")
    probability_count = _integer(
        intelligence.get("probability_ready_product_count"), "probability_ready_product_count"
    )
    timing_count = _integer(
        intelligence.get("timing_ready_product_count"), "timing_ready_product_count"
    )
    terminal_min = _integer(
        intelligence.get("minimum_terminal_samples"), "minimum_terminal_samples"
    )
    timing_min = _integer(
        intelligence.get("minimum_timing_samples"), "minimum_timing_samples"
    )
    if terminal_min < 1 or timing_min < 1:
        raise ProductContractHold("minimum sample requirements absent")
    estimates = intelligence.get("product_estimates")
    if (not isinstance(estimates, Mapping) or len(estimates) > 500
            or probability_count > len(estimates) or timing_count > len(estimates)):
        raise ProductContractHold("product estimate totals invalid")
    if sum(
        isinstance(row, Mapping) and row.get("probability_available") is True
        for row in estimates.values()
    ) != probability_count:
        raise ProductContractHold("model probability availability counts contradicted")
    if sum(
        isinstance(row, Mapping) and row.get("time_to_revenue_available") is True
        for row in estimates.values()
    ) != timing_count:
        raise ProductContractHold("model timing availability counts contradicted")
    tenant = intelligence.get("tenant_id")
    if tenant is not None and (type(tenant) is not str or not tenant.strip()):
        raise ProductContractHold("invalid tenant scope on original source")
    if tenant is None and (outcomes or estimates or matched or probability_count or timing_count):
        raise ProductContractHold("unscoped forecast observations cannot enter product science")
    catalog_products = catalog_report["products"]
    codes = set()
    for row in catalog_products:
        if not isinstance(row, Mapping):
            raise ProductContractHold("original catalogue product row invalid")
        code = row.get("product_code")
        if type(code) is not str or code in codes:
            raise ProductContractHold("ambiguous original SKU")
        codes.add(code)
    if not set(estimates).issubset(codes):
        raise ProductContractHold("predictive source product outside original catalog")
    # Snapshot is source-owner material, but no independent source signature,
    # original forecast registry readback or tenant authentication is present.
    # Never surface numerical customer forecasts from snapshot directly.
    if outcomes == 0:
        status = "NO_PRODUCT_TERMINAL_OUTCOMES_OBSERVED"
        reason = "NO_ORIGINAL_VERIFIED_PRODUCT_TERMINAL_COHORT_IN_OWNER_SNAPSHOT"
    else:
        status = "PRODUCT_COHORT_PRESENT_OWNER_AUTHENTICATION_STILL_REQUIRED"
        reason = "ORIGINAL_SOURCE_AND_FORECAST_REGISTRY_OWNER_READBACK_REQUIRED"
    families = Counter(x["product_family"] for x in catalog_products)
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "reason_code": reason,
        "catalogue_product_count": len(catalog_products),
        "catalogue_family_count": len(families),
        "catalogue_terms_flag_count": catalog_report["catalogue_terms_ready_count"],
        "source_reported_terminal_outcome_count": outcomes,
        "source_reported_matched_outcome_count": matched,
        "source_reported_product_cohorts": len(estimates),
        "source_reported_probability_ready_product_count": probability_count,
        "source_reported_timing_ready_product_count": timing_count,
        "minimum_terminal_samples": terminal_min,
        "minimum_timing_samples": timing_min,
        "tenant_bound_original_source_claim_present": tenant is not None,
        "tenant_identity_exposed": False,
        "product_science_workbench": [
            {
                "product_code": x["product_code"],
                "product_family": x["product_family"],
                "original_product_terms_flag": x["existing_catalogue_terms_flag_observed"],
                "original_terms_blockers": x["original_catalogue_readiness_blockers"],
                "science_status": (
                    "SOURCE_OWNER_COHORT_PRESENT_UNVERIFIED" if x["product_code"] in estimates
                    else "NO_SOURCE_OWNER_PRODUCT_COHORT"
                ),
                "prediction": None,
                "confidence_interval": None,
                "historical_baseline_brier": None,
                "forecast_issued_and_registered": False,
                "enterprise_customer_delivery_approved": False,
            }
            for x in catalog_products
        ],
        "original_source_issuer_authenticated": False,
        "original_forecast_registry_readback_authenticated": False,
        "model_holdout_from_authenticated_actuals_proven": False,
        "forecast_eligible_for_customer": False,
        "economic_memory_update_eligible": False,
        "database_writes": False,
        "production_activated": False,
        "execution_authority": "none",
    }


def review_existing_product_science(*, as_of: datetime | None = None) -> dict[str, Any]:
    now = as_of or datetime.now(timezone.utc)
    catalog = review_existing_local_catalogue(as_of=now)
    snapshot, digest, file_time = _read_bounded_file(SOURCE, owner_uid=0)
    if abs((_stamp(snapshot.get("generated_at")) - file_time).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
        raise ProductContractHold("predictive source mtime and generation mismatch")
    review = science_source_status(catalog, snapshot, as_of=now)
    return {
        **review,
        "original_catalogue_snapshot_custody_verified": True,
        "local_predictive_source_file_custody_verified": True,
        "predictive_snapshot_sha256_change_detection_only": digest,
    }
