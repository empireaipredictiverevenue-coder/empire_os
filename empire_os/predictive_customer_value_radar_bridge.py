"""Source-revision-bound bridge from Community Intent to Predictive Revenue value pilots.

Pure read-only joins on the existing Opportunity Radar. A community complaint
is not a buyer, a Radar research rank is not a probability, and a product
hypothesis must not be trained on outcomes observed after forecast issuance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.predictive_customer_value_demand import (
    review_existing_community_needs, build_cross_market_customer_value_research_blueprint,
    _time,
)
from empire_os.pain_solution_engine import SOLUTION_MAP

SCHEMA = "empire.predictive.customer_value_radar_bridge.v1"
RADAR_SCHEMA = "empire.predictive_cloud.opportunity_radar.v1"
MAX_AGE = timedelta(hours=6)
MAX_SOURCE_LAG = timedelta(minutes=30)
MAX_BYTES = 3_000_000
MEASURE = {
    "lead_generation": ("verified_acquisition_cost_per_accepted_customer", "qualified_paid_customer_acquisitions"),
    "sales_conversion": ("verified_sales_conversion_from_inbound", "net_margin_per_accepted_sale"),
    "search_visibility": ("verified_qualified_search_traffic", "paid_customer_acquisitions_from_search"),
    "automation_ops": ("monthly_task_minutes", "net_cost_per_completed_task"),
    "data_intelligence": ("decision_quality_against_holdout", "cost_per_verified_decision"),
    "revenue_growth": ("incremental_paid_net_revenue", "contribution_margin_after_cost"),
    "storm_demand": ("time_to_accepted_service", "net_profit_after_real_delivery"),
}


def _base(status: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "status": status,
        "hold_code": reason,
        "source_identity_aligned": False, "source_revision_attested": False,
        "research_pain_count": None, "community_radar_candidate_count": None,
        "market_research_candidate_count": None,
        "other_radar_research_candidate_count": None, "research_cards": [],
        "consumer_product_research_blueprint_count": 0,
        "verified_product_purchase_count": None,
        "verified_app_subscriptions": None,
        "verified_service_bookings": None,
        "buyer_identity_authenticated": False,
        "buyer_terms_authenticated": False, "market_demand_verified": False,
        "customer_time_saved_measured": False,
        "customer_cash_saved_measured": False,
        "prospective_original_quant_registered": False,
        "verified_outcome_calibration_performed": False,
        "new_research_executed": False,
        "crm_accessed": False, "outbound_sent": False, "database_writes": False,
        "execution_authority": "none",
    }


def review_customer_value_radar_bridge(
    community: Mapping[str, Any], radar: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    """Correlate research hypotheses ONLY to their exact frozen source revision."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    now = as_of.astimezone(timezone.utc)
    if not isinstance(community, Mapping) or not isinstance(radar, Mapping):
        return _base("SOURCE_EVIDENCE_HOLD", "SOURCES_REQUIRED")
    try:
        bridge = review_existing_community_needs(community, as_of=now)
        if (radar.get("schema_version") != RADAR_SCHEMA or radar.get("mode") != "OBSERVE"
                or radar.get("execution_authority") != "none"
                or radar.get("outreach_authority") != "none"
                or radar.get("commercial_authority") != "none"
                or radar.get("payment_authority") != "none"
                or radar.get("revenue_recognition_authority") != "none"
                or radar.get("automatic_external_execution_allowed") is not False):
            return _base("SOURCE_EVIDENCE_HOLD", "UNTRUSTED_RADAR_AUTHORITY")
        community_at = _time(community.get("observed_at"))
        radar_at = _time(radar.get("generated_at"))
        if not timedelta(0) <= now-radar_at <= MAX_AGE:
            return _base("SOURCE_EVIDENCE_HOLD", "STALE_OR_FUTURE_RADAR")
        if not timedelta(0) <= radar_at-community_at <= MAX_SOURCE_LAG:
            return _base("SOURCE_EVIDENCE_HOLD", "COMMUNITY_RADAR_SOURCE_EPOCH_MISMATCH")
        statuses = radar.get("source_status")
        details = statuses.get("community_intent") if isinstance(statuses, Mapping) else None
        if (not isinstance(details, Mapping)
                or details.get("available") is not True
                or details.get("generated_at") != community.get("observed_at")):
            return _base("SOURCE_EVIDENCE_HOLD", "ORIGINAL_COMMUNITY_REVISION_NOT_BOUND")
        candidates = radar.get("candidates")
        if (not isinstance(candidates, list) or len(candidates) > 250
                or type(radar.get("candidate_count")) is not int
                or len(candidates) != radar["candidate_count"]
                or type(details.get("candidate_count")) is not int):
            return _base("SOURCE_EVIDENCE_HOLD", "RADAR_CANDIDATE_COUNT_UNTRUSTED")

        rows: dict[str, Mapping[str, Any]] = {}
        seen_keys: set[str] = set()
        research_only = 0
        other_research_only = 0
        for raw in candidates:
            if not isinstance(raw, Mapping):
                return _base("SOURCE_EVIDENCE_HOLD", "RADAR_ROW_NOT_OBJECT")
            key = raw.get("opportunity_key")
            if not isinstance(key, str) or not 4 <= len(key) <= 160 or key in seen_keys:
                return _base("SOURCE_EVIDENCE_HOLD", "DUPLICATE_OR_INVALID_RADAR_OPPORTUNITY")
            seen_keys.add(key)
            if (raw.get("execution_authority") != "none"
                    or raw.get("revenue_inferred") is not False
                    or raw.get("buyer_intent_inferred") is not False
                    or raw.get("opportunity_factory_ready") is not False):
                return _base("SOURCE_EVIDENCE_HOLD", "UNSUPPORTED_RADAR_BUYER_OR_FORECAST_CLAIM")
            cls = raw.get("opportunity_class")
            if cls == "community_pain":
                if raw.get("source") != "community_intent":
                    return _base("SOURCE_EVIDENCE_HOLD", "COMMUNITY_SOURCE_OWNER_MISMATCH")
                rows[key] = raw
            elif cls == "market_research":
                research_only += 1
            else:
                other_research_only += 1
        original_pains = {}
        for row in community.get("pain_solution_briefs", []):
            if not isinstance(row, Mapping):
                return _base("SOURCE_EVIDENCE_HOLD", "INVALID_COMMUNITY_PROBLEM_ROW")
            pain = row.get("pain_point")
            if pain not in SOLUTION_MAP or pain in original_pains:
                return _base("SOURCE_EVIDENCE_HOLD", "INVALID_OR_DUPLICATE_PAIN")
            original_pains[pain] = row
        expected = {f"community_pain:{name}" for name, row in original_pains.items()
                    if row.get("opportunity_event") == "opportunity_candidate_created"}
        if set(rows) != expected or details["candidate_count"] != len(expected):
            return _base("SOURCE_EVIDENCE_HOLD", "RADAR_COMMUNITY_PROMOTION_DRIFT")

        cards = []
        for key in sorted(rows):
            radar_row = rows[key]
            pain = key.removeprefix("community_pain:")
            original = original_pains[pain]
            if (radar_row.get("offer_key") != original.get("offer_key")
                    or radar_row.get("products") != original.get("products")
                    or radar_row.get("evidence_strength") != original.get("evidence_strength")
                    or radar_row.get("observed_mentions") != original.get("observed_mentions")
                    or radar_row.get("high_intent_mentions") != original.get("high_intent_mentions")):
                return _base("SOURCE_EVIDENCE_HOLD", "RADAR_OFFER_OR_PUBLIC_PAIN_REVISION_DRIFT")
            metrics = MEASURE.get(pain)
            if not metrics:
                return _base("SOURCE_EVIDENCE_HOLD", "UNSUPPORTED_PROBLEM_MEASUREMENT_CONTRACT")
            # Revision fingerprint is a deterministic *detection aid*, not a
            # signed source receipt or a cryptographic proof of authenticity.
            revision = sha256(json.dumps(
                [community_at.isoformat(), radar_at.isoformat(), key,
                 radar_row["offer_key"], radar_row["products"],
                 radar_row["observed_mentions"], radar_row["high_intent_mentions"]],
                separators=(",",":"),sort_keys=False,
            ).encode()).hexdigest()
            cards.append({
                "opportunity_key": key,
                "source_revision_fingerprint": revision,
                "original_community_epoch": community_at.isoformat(),
                "radar_snapshot_epoch": radar_at.isoformat(),
                "problem_key": pain,
                "candidate_offer_key": original["offer_key"],
                "candidate_products": list(original["products"]),
                "reported_public_mentions": original["observed_mentions"],
                "reported_high_intent_tags": original["high_intent_mentions"],
                "proposed_primary_value_metric": metrics[0],
                "proposed_commercial_validation_metric": metrics[1],
                "proposed_comparison": "prospective_baseline_or_randomized_holdout",
                "verified_buyer_count": None,
                "verified_purchase_count": None,
                "original_value_baseline_measured": False,
                "original_value_after_measurement": False,
                "original_model_probability_issued": False,
                "customer_outcomes_verified": False,
                "quant_ready": False,
                "next_owner": "predictive_value_experiment_design",
                "next_action": "REGISTER_PROSPECTIVE_VALUE_BASELINE_AND_SOURCED_OUTCOME_PLAN",
                "research_only_not_a_buyer_or_sale": True,
            })

        blueprint = build_cross_market_customer_value_research_blueprint()
        return {
            **_base("CUSTOMER_VALUE_TO_RADAR_RESEARCH_BRIDGED", "NONE"),
            "hold_code": None,
            "source_identity_aligned": True,
            "source_revision_attested": False,
            "source_community_epoch": community_at.isoformat(),
            "source_radar_epoch": radar_at.isoformat(),
            "source_lag_seconds": int((radar_at-community_at).total_seconds()),
            "research_pain_count": bridge["research_theme_count"],
            "community_radar_candidate_count": len(cards),
            "market_research_candidate_count": research_only,
            "other_radar_research_candidate_count": other_research_only,
            "research_cards": cards,
            "consumer_product_research_blueprint_count": blueprint["research_question_count"],
            "market_research_rows_have_customer_value_attribution": False,
            "community_pain_is_paid_demand": False,
            "market_pain_source_may_be_reused_for_training": False,
            "next_owner": "existing_predictive_value_and_scientific_quant_owner",
            "next_action": "COLLECT_PROSPECTIVE_CUSTOMER_VALUE_AND_VERIFIED_BUYER_OUTCOMES",
        }
    except (ValueError, TypeError, KeyError, AttributeError):
        return _base("SOURCE_EVIDENCE_HOLD", "SOURCE_CONTRACT_VALIDATION_FAILED")


def review_customer_value_radar_bridge_runtime(
    repo_root: str | Path, *, as_of: datetime,
) -> dict[str, Any]:
    """Read ONLY existing public aggregate snapshots; no private posts/CRM/DB."""
    root = Path(repo_root).resolve()
    snapshots: dict[str, Mapping[str, Any]] = {}
    for name, rel in (
        ("community", "runtime/community_intent/latest.json"),
        ("radar", "runtime/opportunity_radar/latest.json"),
    ):
        p = root / rel
        try:
            if ((root / "runtime").is_symlink()
                    or p.parent.is_symlink() or p.is_symlink()
                    or not p.is_file() or not 0 < p.stat().st_size <= MAX_BYTES):
                return _base("SOURCE_EVIDENCE_HOLD", "UNAVAILABLE_"+name.upper()+"_SOURCE")
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeError):
            return _base("SOURCE_EVIDENCE_HOLD", "UNREADABLE_"+name.upper()+"_SOURCE")
        snapshots[name] = data
    return review_customer_value_radar_bridge(
        snapshots["community"], snapshots["radar"], as_of=as_of,
    )
