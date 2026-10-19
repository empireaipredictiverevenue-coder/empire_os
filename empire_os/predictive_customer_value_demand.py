"""Cross-market customer need, purchase-claim, and time/money value research.

Additive Predictive Revenue research adapter. This module cannot authenticate a
transaction, independent customer count, outcome, rights, price or conversion.
It never scans private text or executes a purchase/search/outbound action.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from empire_os.pain_solution_engine import SOLUTION_MAP

SCHEMA = "empire.predictive.customer_value_demand_shadow.v1"
COMMUNITY_SCHEMA = "empire.community_intent.v2"
TYPES = ("product", "app", "service", "data_product")
AUDIENCES = ("consumer", "business")
SOURCE_TYPES = (
    "public_problem", "public_comparison", "public_review",
    "app_review", "public_search", "seller_marketing",
    "catalog_listing", "buyer_purchase_claim",
    "first_party_receipt_claim",
)
PURCHASE_CLAIMS = frozenset(("buyer_purchase_claim", "first_party_receipt_claim"))
RESEARCH_ONLY = frozenset(SOURCE_TYPES) - PURCHASE_CLAIMS
SAFE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_RECORDS = 150
MAX_CLUSTERS = 60

# Market-agnostic *questions*, not observed demand, rankings, buyer profiles,
# or forecasts. Owners may research each within their licensed source budgets.
RESEARCH_JOBS = (
    ("consumer", "reduce_household_bills", ("product", "app", "service"), "monthly_cash_spend"),
    ("consumer", "save_personal_admin_time", ("app", "service"), "monthly_task_minutes"),
    ("consumer", "find_reliable_home_services", ("service", "app"), "appointment_quality_and_cost"),
    ("consumer", "compare_product_value", ("product", "app"), "purchase_cost_and_returns"),
    ("consumer", "avoid_subscription_waste", ("app", "service"), "renewal_cost_and_churn"),
    ("business", "reduce_manual_work", ("app", "service"), "monthly_staff_task_minutes"),
    ("business", "improve_lead_conversion", ("app", "service", "data_product"), "verified_margin_per_acquisition"),
    ("business", "compare_supplier_costs", ("product", "service", "data_product"), "fulfillment_adjusted_cost"),
    ("business", "improve_purchase_decisions", ("app", "data_product"), "decision_accuracy_and_loss"),
    ("business", "reduce_customer_service_wait", ("app", "service"), "resolution_time_and_quality"),
)


def build_cross_market_customer_value_research_blueprint(
    markets: tuple[str, ...] = ("united_kingdom", "united_states"),
) -> dict[str, Any]:
    """Static bounded evidence acquisition questions; no searches performed."""
    if (not isinstance(markets, tuple) or not 1 <= len(markets) <= 4
            or len(set(markets)) != len(markets)
            or any(not _slug(market) for market in markets)):
        raise ValueError("unique bounded market research scope required")
    plans = []
    for market in markets:
        for audience, need, purchase_types, outcome in RESEARCH_JOBS:
            plans.append({
                "market_key": market, "audience": audience,
                "job_to_be_done": need,
                "eligible_purchase_types": list(purchase_types),
                "customer_value_metric_to_test": outcome,
                "problem_observed": False,
                "purchase_observed": False,
                "buyer_count_known": False,
                "savings_measured": False,
                "owner_research_tasks": [
                    "CHECK_PERMISSIONED_PROBLEM_AND_COMPARISON_OBSERVATIONS",
                    "CHECK_INDEPENDENT_PURCHASE_CANCEL_RETURN_RECEIPTS",
                    "TEST_BEFORE_AFTER_VALUE_AND_REAL_DELIVERY_COST",
                ],
            })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "CROSS_MARKET_RESEARCH_BLUEPRINT_ONLY",
        "market_count": len(markets),
        "research_question_count": len(plans),
        "questions": plans,
        "covers_purchase_categories": list(TYPES),
        "real_world_search_executed": False,
        "buyer_data_or_spend_observed": False,
        "research_questions_are_detected_market_needs": False,
        "outbound_sent": False, "database_writes": False,
        "execution_authority": "none",
    }


def _time(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 75:
        raise ValueError("bounded timezone-aware observation timestamp required")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid source observation timestamp") from exc
    if t.utcoffset() is None:
        raise ValueError("source clock must be timezone aware")
    return t.astimezone(timezone.utc)


def _slug(value: Any) -> bool:
    return isinstance(value, str) and SAFE.fullmatch(value) is not None


def _int(value: Any, *, upper: int) -> int:
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError("invalid nonnegative bounded scenario number")
    return value


def _money_scenario(raw: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Reported what-if scenario, *not* a customer measurement or ROI proof."""
    if raw is None:
        return None
    fields = {
        "currency", "minutes_before_month", "minutes_after_month",
        "cash_before_month_minor", "cash_after_month_minor",
        "solution_cost_month_minor", "time_value_per_hour_minor",
    }
    if not isinstance(raw, Mapping) or set(raw) != fields:
        raise ValueError("scenario needs exact monthly comparison fields")
    currency = raw["currency"]
    if currency not in ("USD", "GBP", "EUR"):
        raise ValueError("unsupported or unconverted currency")
    for field in fields - {"currency"}:
        v = raw[field]
        if v is not None:
            _int(v, upper=10_000_000_000 if "minor" in field else 1_000_000)
    before, after = raw["minutes_before_month"], raw["minutes_after_month"]
    b, a, subscription = (raw["cash_before_month_minor"],
                          raw["cash_after_month_minor"],
                          raw["solution_cost_month_minor"])
    minutes_delta = before - after if before is not None and after is not None else None
    cash_delta = b - a - subscription if all(v is not None for v in (b,a,subscription)) else None
    time_val = raw["time_value_per_hour_minor"]
    value_of_time = (
        round(minutes_delta * time_val / 60)
        if minutes_delta is not None and time_val is not None else None
    )
    total = (
        cash_delta + value_of_time
        if cash_delta is not None and value_of_time is not None else None
    )
    return {
        "currency": currency,
        "monthly_minutes_saved_scenario": minutes_delta,
        "monthly_net_cash_delta_minor_scenario": cash_delta,
        "monthly_time_valued_minor_scenario": value_of_time,
        "monthly_combined_illustrative_minor_scenario": total,
        "baseline_and_solution_period": "same_month",
        "solution_cost_counted_once": True,
        "time_valuation_optional_and_not_cash": True,
        "customer_savings_independently_measured": False,
        "customer_roi_verified": False,
        "income_or_profit_realized": False,
        "forecast_probability": None,
    }


def compare_monthly_customer_value_scenario(
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    """Optional what-if calculator; never infer accuracy from a customer claim."""
    return _money_scenario(scenario)  # type: ignore[return-value]


def review_customer_value_observations(
    records: Sequence[Mapping[str, Any]], *, as_of: datetime,
) -> dict[str, Any]:
    """Research-only clusters across consumer/business, products/apps/services.

    Inputs are typed, rights-scoped feature receipts supplied by existing
    approved source owners, NOT raw reviews, URLs, people or transaction data.
    A claimed purchase/receipt NEVER becomes verified demand here.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("prospective aware clock required")
    now = as_of.astimezone(timezone.utc)
    if (not isinstance(records, (list, tuple)) or len(records) > MAX_RECORDS
            or any(not isinstance(row, Mapping) for row in records)):
        raise ValueError("bounded existing observations required")
    seen: set[tuple[tuple[str, str, str, str], str]] = set()
    clusters: dict[tuple[str,str,str,str], Counter[str]] = defaultdict(Counter)
    origin_count = 0
    duplicates = 0
    for row in records:
        required = {
            "audience", "market_key", "item_type", "job_key",
            "source_type", "source_observed_at", "origin_sha256",
            "content_sha256", "reuse_scope",
        }
        if set(row) != required:
            raise ValueError("typed observed event fields required; no raw PII")
        audience, market, kind, job = (
            row["audience"], row["market_key"], row["item_type"], row["job_key"])
        if (audience not in AUDIENCES or kind not in TYPES
                or not _slug(market) or not _slug(job)
                or row["source_type"] not in SOURCE_TYPES
                or row["reuse_scope"] != "INTERNAL_AGGREGATE_RESEARCH_ONLY"
                or not isinstance(row["origin_sha256"], str)
                or not HEX64.fullmatch(row["origin_sha256"])
                or not isinstance(row["content_sha256"], str)
                or not HEX64.fullmatch(row["content_sha256"])):
            raise ValueError("untrusted market, source, reuse licence or digest")
        timestamp = _time(row["source_observed_at"])
        if not timedelta(0) <= now-timestamp <= timedelta(days=90):
            raise ValueError("future or stale purported customer evidence")
        cluster = (audience, market, kind, job)
        key = (cluster, row["origin_sha256"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        origin_count += 1
        clusters[cluster][row["source_type"]] += 1
    if len(clusters) > MAX_CLUSTERS:
        raise ValueError("unbounded segment cluster count")

    priority = {
        "public_problem": 2, "public_comparison": 3, "public_review": 1,
        "app_review": 1, "public_search": 1, "seller_marketing": 0,
        "catalog_listing": 0, "buyer_purchase_claim": 2,
        "first_party_receipt_claim": 2,
    }
    answers = []
    for (audience, market, kind, job), counts in clusters.items():
        total = sum(counts.values())
        purchase_claims = sum(counts.get(kind,0) for kind in PURCHASE_CLAIMS)
        research_points = sum(counts.get(key, 0) * weight for key,weight in priority.items())
        research_key = sha256(
            ("|".join((audience,market,kind,job))).encode()
        ).hexdigest()[:20]
        answers.append({
            "cluster_ref": "need_" + research_key,
            "audience": audience,
            "market_key": market, "item_type": kind,
            "job_to_be_done": job,
            "source_type_counts": {s:counts[s] for s in SOURCE_TYPES if counts[s]},
            "distinct_source_origin_receipts": total,
            "purchase_claim_receipts": purchase_claims,
            "verified_purchase_count": None,
            "verified_sold_units": None,
            "verified_customer_count": None,
            "market_share_estimate": None,
            "paying_demand_or_spend_authenticated": False,
            "independently_verified_customer_benefit": False,
            "research_triage_points": research_points,
            "research_triage_is_purchase_probability": False,
            "next_owner": "customer_value_research",
            "next_action": (
                "VERIFY_FIRST_PARTY_PURCHASES_RETURNS_AND_UNIT_ECONOMICS"
                if purchase_claims else
                "FIND_INDEPENDENT_PROBLEM_AND_PURCHASE_EVIDENCE"
            ),
        })
    answers.sort(key=lambda x:(-x["research_triage_points"], -x["distinct_source_origin_receipts"],x["cluster_ref"]))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "CROSS_MARKET_CUSTOMER_VALUE_RESEARCH_READY",
        "input_event_count": len(records),
        "deduplicated_event_count": duplicates,
        "distinct_observation_receipts": origin_count,
        "cross_segment_source_origins_are_independent_people": False,
        "cluster_count": len(answers),
        "research_clusters": answers,
        "covers_purchase_categories": list(TYPES),
        "covers_customer_types": list(AUDIENCES),
        "market_demand_verified": False,
        "transactions_authenticated": False,
        "commercial_purchase_intent_verified": False,
        "customer_savings_verified": False,
        "customer_roi_verified": False,
        "training_labels_available": False,
        "predictive_model_fitted": False,
        "new_external_research_run": False,
        "private_customer_content_ingested": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_existing_community_needs(
    snapshot: Mapping[str, Any], *, as_of: datetime,
) -> dict[str, Any]:
    """Bridge existing Community Intent *aggregates* to new multi-product research."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted aware clock required")
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("schema_version") != COMMUNITY_SCHEMA
            or snapshot.get("mode") != "OBSERVE"
            or snapshot.get("execution_authority") != "none"):
        raise ValueError("untrusted existing Community Intent contract")
    at = _time(snapshot.get("observed_at"))
    if not timedelta(0) <= as_of.astimezone(timezone.utc)-at <= timedelta(days=7):
        raise ValueError("community aggregate snapshot out of date")
    briefs = snapshot.get("pain_solution_briefs")
    if not isinstance(briefs, list) or len(briefs) > 30:
        raise ValueError("unbounded upstream pain briefs")
    hypotheses = []
    seen_pains = set()
    for row in briefs:
        if not isinstance(row, Mapping):
            raise ValueError("invalid existing pain brief")
        pain = row.get("pain_point")
        if not isinstance(pain, str) or pain not in SOLUTION_MAP or pain in seen_pains:
            raise ValueError("invalid, duplicate or unmapped existing pain")
        seen_pains.add(pain)
        mentions = _int(row.get("observed_mentions"), upper=100000)
        high = _int(row.get("high_intent_mentions"), upper=100000)
        if high > mentions or row.get("execution_authority") != "none":
            raise ValueError("source brief inflates public intent")
        if row.get("offer_key") != SOLUTION_MAP[pain]["offer_key"]:
            raise ValueError("untrusted upstream offer mapping")
        configured = SOLUTION_MAP[pain]["products"]
        if row.get("products") != list(configured):
            raise ValueError("product catalogue does not match existing controlled map")
        if row.get("evidence_strength") not in ("thin","moderate","strong"):
            raise ValueError("untrusted source strength label")
        hypotheses.append({
            "problem_key": pain,
            "existing_offer_key": row["offer_key"],
            "existing_product_hypotheses": list(configured),
            "public_mentions_reported": mentions,
            "high_intent_tags_reported": high,
            "product_category_research_plan": {
                "app": "RESEARCH_APP_REVIEWS_CHURN_PRICE_AND_ACTIVATION",
                "product": "RESEARCH_PRODUCT_ORDERS_RETURNS_PRICE_AND_AVAILABILITY",
                "service": "RESEARCH_VERIFIED_QUOTES_BOOKINGS_AND_RENEWALS",
                "data_product": "RESEARCH_ACCEPTED_FEEDS_API_CONTRACTS_AND_USAGE",
            },
            "jobs_to_be_done": "reduce_friction_or_improve_outcome",
            "time_saved_measured": False,
            "cash_saved_measured": False,
            "willingness_to_pay_authenticated": False,
            "buyer_identity_authenticated": False,
            "source_mentions_are_distinct_people": False,
            "product_fit_proven": False,
            "next_action": "VALIDATE_PURCHASE_BEHAVIOR_AND_MONTHLY_TIME_MONEY_BASELINE",
        })
    hypotheses.sort(key=lambda item:(-item["high_intent_tags_reported"],-item["public_mentions_reported"],item["problem_key"]))
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "status": "EXISTING_COMMUNITY_NEEDS_RESEARCH_BRIDGED",
        "source_schema": COMMUNITY_SCHEMA,
        "source_observation_time": at.isoformat(),
        "research_theme_count": len(hypotheses),
        "hypotheses": hypotheses,
        "coverage_of_all_products_apps_services_verified": False,
        "independent_purchase_data_connected": False,
        "time_or_money_benefit_verified": False,
        "research_only_not_a_sales_forecast": True,
        "prospective_quant_issuance_authorized": False,
        "model_calibration_performed": False,
        "outbound_sent": False,
        "database_writes": False,
        "execution_authority": "none",
    }


def review_existing_community_needs_runtime(
    repo_root: str | Path, *, as_of: datetime,
) -> dict[str, Any]:
    """Read only existing aggregate JSON. Never reads posts, authors or URLs."""
    root = Path(repo_root).resolve()
    source = root / "runtime/community_intent/latest.json"
    if (source.is_symlink() or source.parent.is_symlink()
            or (root / "runtime").is_symlink()
            or not source.is_file() or not 0 < source.stat().st_size <= 3_000_000):
        raise ValueError("canonical aggregate source missing or unsafe")
    payload = json.loads(source.read_text(encoding="utf-8"))
    return review_existing_community_needs(payload, as_of=as_of)
