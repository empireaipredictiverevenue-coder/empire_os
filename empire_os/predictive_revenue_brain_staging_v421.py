"""EmpireOS V4.21 staging Predictive Brain: original, read-only signal guards.

Only mathematical screening of separately supplied historical observations.
This module DOES NOT train, predict customer revenue, place capital at risk,
remove original evidence, infer a verified bank settlement, or write EmpireDB.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, localcontext
from math import exp, log
from typing import Any, Mapping, Sequence

from empire_os.predictive_revenue_universal_margin import _canonical_hash, _utc

SCHEMA = "empire.predictive-revenue-v421-brain-shields.staging"
HALF_LIFE_HOURS = {
    "WEATHER_STORM": 12,
    "SEARCH_DEMAND": 24,
    "PERMIT_FILING": 168,
    "CRM_CAPACITY": 1,
}
MIN_ANOMALY_BASELINE = 12
MAX_ANOMALY_BASELINE = 365
Z_THRESHOLD = Decimal("3.0")
NORMAL_APPROX_MULTIPLIER = Decimal("1.96")
MAX_AMOUNT_MINOR = 10**13


def decay_weight(*, signal_family: str, occurred_at_utc: str,
                 published_at_utc: str, as_of_utc: str) -> dict:
    """Use actual signal clocks, never an internal summary file's mtime."""
    if signal_family not in HALF_LIFE_HOURS:
        raise ValueError("brain_unknown_signal_family_no_fallback")
    occurred = _utc(occurred_at_utc)
    published = _utc(published_at_utc)
    now = _utc(as_of_utc)
    if not occurred <= published <= now:
        raise ValueError("brain_signal_future_or_unpublished_at_cutoff")
    age_hours = (now - occurred).total_seconds() / 3600
    half_life = HALF_LIFE_HOURS[signal_family]
    weight = exp(-log(2) * age_hours / half_life)
    return {
        "signal_family": signal_family,
        "half_life_hours": half_life,
        "event_age_hours": round(age_hours, 6),
        "source_published_at_utc": published.isoformat(),
        "as_of_utc": now.isoformat(),
        "decay_weight_research_only": round(weight, 12),
        "underlying_event_time_independently_attested": False,
        "live_forecast_impact_authorized": False,
        "execution_authority": "none",
    }


def _amount(value: Any, field: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_AMOUNT_MINOR:
        raise ValueError("brain_invalid_" + field + "_minor")
    return value


def rpc_risk_screen(*, currency: str, predicted_rpc_minor: int | None,
                    signal_uncertainty_minor: int | None,
                    target_margin_minor: int | None = None) -> dict:
    """Normal-approx research screen, NOT a Bayesian 95% credible interval.

    The 1.96 factor from the founder specification is a normal-theory
    approximation. Without independently calibrated uncertainty its
    band has NO statistical coverage claim and cannot unlock capital.
    """
    if (type(currency) is not str or len(currency) != 3
        or not currency.isascii() or not currency.isupper()):
        raise ValueError("brain_explicit_currency_required")
    if target_margin_minor is None:
        # The founder's $15 rule is USD-specific, never implicitly GBP.
        target = 1500 if currency == "USD" else None
    else:
        target = _amount(target_margin_minor, "target")
    if predicted_rpc_minor is not None:
        predicted = _amount(predicted_rpc_minor, "predicted_rpc")
    else:
        predicted = None
    if signal_uncertainty_minor is not None:
        uncertainty = _amount(signal_uncertainty_minor, "uncertainty")
    else:
        uncertainty = None
    base = {
        "currency": currency, "target_margin_minor": target,
        "interval_method": "UNVALIDATED_NORMAL_APPROXIMATION_NOT_BAYESIAN",
        "coverage_95_percent_independently_calibrated": False,
        "capital_throttle_active_fail_closed": True,
        "paid_media_or_funds_authorized": False,
        "live_forecast_or_risk_execution_authorized": False,
        "execution_authority": "none",
    }
    if target is None or predicted is None or uncertainty is None:
        return {
            **base, "research_interval_lower_minor": None,
            "research_interval_upper_minor": None,
            "research_lower_below_target": None,
            "decision": "HOLD_MISSING_CURRENCY_THRESHOLD_OR_FORECAST_UNCERTAINTY",
        }
    spread = NORMAL_APPROX_MULTIPLIER * Decimal(uncertainty)
    low = Decimal(predicted) - spread
    high = Decimal(predicted) + spread
    low_under = low < target
    return {
        **base,
        "research_interval_lower_minor": str(low),
        "research_interval_upper_minor": str(high),
        "research_lower_below_target": low_under,
        "decision": (
            "THROTTLE_RESEARCH_LOWER_BOUND_BELOW_TARGET"
            if low_under else
            "HOLD_NORMAL_BAND_NOT_CALIBRATED_NO_CAPITAL_AUTHORITY"
        ),
    }


def historical_z_shield(*, previous_counts: Sequence[int],
                        candidate_count: int) -> dict:
    """Non-destructive z-score on earlier, bounded aggregate counts.

    Only supplied historical baseline values may determine mean/std.
    No same-candidate fitting, no raw payload, and no automatic deletion.
    """
    if (not isinstance(previous_counts, (tuple, list))
        or not MIN_ANOMALY_BASELINE <= len(previous_counts) <= MAX_ANOMALY_BASELINE):
        raise ValueError("brain_anomaly_requires_historical_baseline")
    counts = [_amount(value, "historical_count") for value in previous_counts]
    candidate = _amount(candidate_count, "candidate_count")
    with localcontext() as context:
        context.prec = 40
        n = Decimal(len(counts))
        mean = sum(map(Decimal, counts)) / n
        variance = sum((Decimal(v) - mean) ** 2 for v in counts) / n
        deviation = abs(Decimal(candidate) - mean)
        if variance == 0:
            changed = deviation != 0
            zscore = None
            anomalous = changed
            decision = (
                "FLAG_FOR_REVIEW_ZERO_VARIANCE_BASELINE"
                if changed else "NO_Z_ANOMALY_CONSTANT_BASELINE"
            )
        else:
            zscore = deviation / variance.sqrt()
            anomalous = zscore > Z_THRESHOLD
            decision = (
                "FLAG_FOR_REVIEW_Z_ABOVE_3"
                if anomalous else "NO_Z_ANOMALY_IN_SUPPLIED_HISTORY"
            )
        return {
            "baseline_count": len(counts),
            "historical_mean": format(mean, ".6f"),
            "historical_population_std": format(variance.sqrt(), ".6f"),
            "absolute_z_score": (
                format(zscore, ".6f") if zscore is not None else None
            ),
            "anomaly_threshold_strictly_above": "3.0",
            "flag_for_manual_review": anomalous,
            "raw_records_deleted_or_modified": False,
            "historical_population_completeness_proven": False,
            "anomaly_is_financial_fraud_proof": False,
            "execution_authority": "none",
            "decision": decision,
        }


def inspect_signed_company_brain(*, signed_review: Mapping[str, Any]) -> dict:
    """Attach staging brain status to an already-verified signed export.

    A signed CSV opportunity timeline cannot prove source-family event
    timestamps, revenue-per-click model uncertainty or complete months.
    Only a bounded retrospective activity anomaly screen can run, and
    even its flags never remove evidence or authorize a financial action.
    """
    if (not isinstance(signed_review, Mapping)
        or signed_review.get("mode") != "SIGNED_COMPANY_EXPORT_REVIEW_ONLY"
        or signed_review.get("signature_mathematically_valid_for_supplied_trusted_key") is not True
        or signed_review.get("execution_authority") != "none"
        or signed_review.get("eligible_for_training_or_live_prediction") is not False):
        raise ValueError("brain_requires_prior_signed_readonly_company_review")
    history = signed_review.get("historical_company_timeline")
    if (not isinstance(history, Mapping)
        or history.get("tenant_scope") != signed_review.get("tenant_scope")
        or history.get("company_scope") != signed_review.get("company_scope")
        or history.get("currency") != signed_review.get("currency")
        or history.get("execution_authority") != "none"):
        raise ValueError("brain_mismatched_company_timeline")
    now = _utc(signed_review["as_of_utc"])
    months = history.get("monthly_event_time_timeline_not_issued_forecasts")
    if not isinstance(months, list) or len(months) > 2400:
        raise ValueError("brain_invalid_bounded_monthly_source_timeline")
    anomaly_status = "HOLD_INCOMPLETE_COMPANY_MONTHLY_BASELINE"
    anomaly = None
    eligible = []
    for month in months:
        if not isinstance(month, Mapping):
            raise ValueError("brain_invalid_monthly_row")
        period = month.get("event_month_utc")
        if type(period) is not str or len(period) != 7:
            raise ValueError("brain_invalid_month_label")
        try:
            stamped = datetime.strptime(period, "%Y-%m")
        except ValueError as exc:
            raise ValueError("brain_invalid_month_label") from exc
        count = _amount(
            month.get("opportunities_opened_events"), "monthly_opportunity_count"
        )
        # Current calendar month is partial: never claim completed coverage.
        if (stamped.year, stamped.month) < (now.year, now.month):
            eligible.append((stamped.year * 12 + stamped.month, count))
    eligible.sort()
    if len({p for p, _ in eligible}) != len(eligible):
        raise ValueError("brain_duplicate_month_bucket")
    if len(eligible) >= MIN_ANOMALY_BASELINE + 1:
        recent = eligible[-(MIN_ANOMALY_BASELINE + 1):]
        if all(recent[i][0] + 1 == recent[i + 1][0]
               for i in range(MIN_ANOMALY_BASELINE)):
            anomaly = historical_z_shield(
                previous_counts=[value for _, value in recent[:-1]],
                candidate_count=recent[-1][1],
            )
            anomaly_status = "UNVERIFIED_AGGREGATE_ANOMALY_SCREEN_NOT_ACTIONABLE"
    report = {
        "schema_version": SCHEMA,
        "mode": "STAGING_OBSERVE_NO_AUTONOMOUS_ACTIONS",
        "tenant_scope": signed_review["tenant_scope"],
        "company_scope": signed_review["company_scope"],
        "currency": signed_review["currency"],
        "as_of_utc": now.isoformat(),
        "source_signed_review_snapshot_sha256": signed_review.get(
            "snapshot_sha256_not_external_attestation"
        ),
        "adaptive_decay": {
            "half_lives_hours": dict(HALF_LIFE_HOURS),
            "status": "HOLD_NO_AUTHENTICATED_SOURCE_FAMILY_EVENT_TIMES",
            "weights_computed_for_company_export": False,
        },
        "rpc_risk": rpc_risk_screen(
            currency=signed_review["currency"],
            predicted_rpc_minor=None, signal_uncertainty_minor=None,
        ),
        "historical_activity_anomaly": anomaly,
        "historical_activity_anomaly_status": anomaly_status,
        "complete_company_monthly_census_proven": False,
        "verified_bank_cash_or_accepted_orders_proven": False,
        "real_30_60_90_day_model_accuracy_proven": False,
        "training_or_model_promotion_authorized": False,
        "automatic_data_quarantine_or_deletion_executed": False,
        "paid_media_outbound_trading_or_funds_authorized": False,
        "empiredb_or_smart_crm_read_or_written": False,
        "execution_authority": "none",
    }
    report["snapshot_sha256_not_source_attestation"] = _canonical_hash(report)
    return report


# V5.0 cloud — extend the original V4.21 staging brain rather than
# installing a parallel service, tenant database, or execution agent.
V5_CLOUD_SCHEMA = "empire.predictive-revenue-v5-cloud.staging-observe"
V5_CORE_NICHES = (
    "PAY_PER_CALL", "HOME_SERVICES", "ECOMMERCE", "SAAS_USAGE",
)
V5_HORIZONS = (30, 60, 90)
V5_USD_FLOOR_MINOR = 1800
V5_SIGNAL_FIELDS = frozenset({
    "signal_id", "tenant_scope", "company_scope", "sector",
    "family", "source_id", "source_receipt_sha256", "occurred_at_utc",
    "published_at_utc", "ingested_at_utc", "observed_count",
    "previous_counts", "evidence_basis",
})
V5_FORECAST_FIELDS = frozenset({
    "forecast_id", "opportunity_id", "tenant_scope", "company_scope", "sector",
    "currency", "horizon_days", "issued_at_utc",
    "feature_published_at_utc", "target_at_utc",
    "predicted_rpc_minor", "uncertainty_minor",
    "predicted_cvr_bps", "original_issuance_receipt_sha256",
    "evidence_basis",
})


def review_v5_cloud_staging(*, signed_company_review: Mapping[str, Any],
                            signal_rows: Sequence[Mapping[str, Any]] = (),
                            issued_forecast_rows: Sequence[Mapping[str, Any]] = ()) -> dict:
    """V5 read-only signal -> decay/anomaly -> USD 18 RPC floor -> horizon HOLD.

    Caller-supplied signal receipts and issuance fingerprints do not constitute
    source rights, an issuance registry or bank attestation. The adapter cannot
    issue bids, score financial outcomes, fit a model or migrate EmpireDB.
    """
    import re
    from datetime import timedelta

    if (not isinstance(signed_company_review, Mapping)
        or signed_company_review.get("mode") != "SIGNED_COMPANY_EXPORT_REVIEW_ONLY"
        or signed_company_review.get("signature_mathematically_valid_for_supplied_trusted_key") is not True
        or signed_company_review.get("eligible_for_training_or_live_prediction") is not False
        or signed_company_review.get("execution_authority") != "none"
        or signed_company_review.get("model_promotion_or_payment_authorized") is not False
        or signed_company_review.get("financial_settlement_refunds_or_costs_reconciled") is not False
        or signed_company_review.get("source_registry_and_data_rights_independently_authenticated") is not False):
        raise ValueError("v5_requires_signed_readonly_source_and_negative_authority")
    timeline = signed_company_review.get("historical_company_timeline")
    if (not isinstance(timeline, Mapping)
        or timeline.get("tenant_scope") != signed_company_review.get("tenant_scope")
        or timeline.get("company_scope") != signed_company_review.get("company_scope")
        or timeline.get("currency") != signed_company_review.get("currency")
        or timeline.get("execution_authority") != "none"):
        raise ValueError("v5_cross_company_timeline_denied")
    tenant = signed_company_review["tenant_scope"]
    company = signed_company_review["company_scope"]
    currency = signed_company_review["currency"]
    now = _utc(signed_company_review["as_of_utc"])
    if (not isinstance(signal_rows, (tuple, list))
        or len(signal_rows) > 500
        or not isinstance(issued_forecast_rows, (tuple, list))
        or len(issued_forecast_rows) > 1500):
        raise ValueError("v5_bounded_source_and_forecast_rows_required")

    niches = {sector: {
        "signal_observations_unverified": 0,
        "anomaly_manual_review_flags": 0,
        "research_forecast_rows_by_horizon": {
            str(h): 0 for h in V5_HORIZONS
        },
        "research_lower_bound_below_floor_rows": 0,
        "risk_throttle_active": True,
        "approved_bids_observed_or_authorized": 0,
        "real_world_bid_approval_rate_verified": None,
        "reconciled_financial_residual_mae_minor": None,
        "decision": "HOLD_NO_VERIFIED_SOURCE_ISSUANCES_AND_FINANCE",
    } for sector in V5_CORE_NICHES}
    sightings = set()
    signals = []
    for item in signal_rows:
        if not isinstance(item, Mapping) or set(item) != V5_SIGNAL_FIELDS:
            raise ValueError("v5_signal_exact_source_event_contract_required")
        if (item["tenant_scope"] != tenant or item["company_scope"] != company
            or item["sector"] not in niches):
            raise ValueError("v5_cross_tenant_company_or_niche_signal_denied")
        if (item["evidence_basis"] != "UNRECONCILED"
            or item["family"] not in HALF_LIFE_HOURS):
            raise ValueError("v5_unverified_or_unknown_signal_family")
        sid = item["signal_id"]
        if (type(sid) is not str or len(sid) > 100 or len(sid) < 4
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]*", sid) is None
            or sid in sightings):
            raise ValueError("v5_invalid_or_duplicate_signal_id")
        sightings.add(sid)
        source_id = item["source_id"]
        if (type(source_id) is not str or len(source_id) < 4
            or len(source_id) > 100
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]*", source_id) is None):
            raise ValueError("v5_invalid_source_id")
        receipt = item["source_receipt_sha256"]
        if type(receipt) is not str or not re.fullmatch(r"[0-9a-f]{64}", receipt):
            raise ValueError("v5_signal_receipt_fingerprint_required")
        appeared = _utc(item["occurred_at_utc"])
        published = _utc(item["published_at_utc"])
        ingested = _utc(item["ingested_at_utc"])
        if not appeared <= published <= ingested <= now:
            raise ValueError("v5_signal_timeline_future_information_denied")
        count = _amount(item["observed_count"], "observed_count")
        decay = decay_weight(
            signal_family=item["family"],
            occurred_at_utc=appeared.isoformat(),
            published_at_utc=published.isoformat(),
            as_of_utc=now.isoformat(),
        )
        baseline = item["previous_counts"]
        anomaly = (None if baseline is None else historical_z_shield(
            previous_counts=baseline, candidate_count=count
        ))
        sector = item["sector"]
        niches[sector]["signal_observations_unverified"] += 1
        niches[sector]["anomaly_manual_review_flags"] += int(
            bool(anomaly and anomaly["flag_for_manual_review"])
        )
        signals.append({
            "signal_id": sid, "sector": sector,
            "family": item["family"],
            "source_id_supplied_not_independently_authorized": source_id,
            "research_event_decay": decay,
            "historical_anomaly_review": anomaly,
            "raw_payload_stored_or_quarantined": False,
            "source_rights_verified": False,
        })

    forecast_ids = set()
    seen_opportunity_horizons = set()
    forecast_screens = []
    for item in issued_forecast_rows:
        if not isinstance(item, Mapping) or set(item) != V5_FORECAST_FIELDS:
            raise ValueError("v5_exact_issued_forecast_contract_required")
        if (item["tenant_scope"] != tenant or item["company_scope"] != company
            or item["sector"] not in niches or item["currency"] != currency
            or item["evidence_basis"] != "UNRECONCILED"):
            raise ValueError("v5_cross_tenant_company_currency_or_basis_forecast")
        fid = item["forecast_id"]
        if (type(fid) is not str or not 4 <= len(fid) <= 100
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]*", fid) is None
            or fid in forecast_ids):
            raise ValueError("v5_duplicate_or_invalid_forecast_identity")
        forecast_ids.add(fid)
        opportunity = item["opportunity_id"]
        if (type(opportunity) is not str
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{3,99}", opportunity) is None):
            raise ValueError("v5_invalid_opportunity_reference")
        horizon = item["horizon_days"]
        if type(horizon) is not int or horizon not in V5_HORIZONS:
            raise ValueError("v5_exact_30_60_90_horizons_required")
        if (opportunity, horizon) in seen_opportunity_horizons:
            raise ValueError("v5_duplicate_opportunity_horizon")
        seen_opportunity_horizons.add((opportunity, horizon))
        receipt = item["original_issuance_receipt_sha256"]
        if type(receipt) is not str or not re.fullmatch(r"[0-9a-f]{64}", receipt):
            raise ValueError("v5_original_issuance_receipt_fingerprint_required")
        published = _utc(item["feature_published_at_utc"])
        issued = _utc(item["issued_at_utc"])
        target = _utc(item["target_at_utc"])
        if (not published <= issued <= now
            or target != issued + timedelta(days=horizon)):
            raise ValueError("v5_hindsight_or_wrong_horizon_denied")
        pcvr = item["predicted_cvr_bps"]
        if pcvr is not None and (type(pcvr) is not int or not 0 <= pcvr <= 10000):
            raise ValueError("v5_invalid_predicted_cvr_basis_points")
        # No cross-currency conversion and no silent change of the USD floor.
        rpc = rpc_risk_screen(
            currency=currency,
            predicted_rpc_minor=item["predicted_rpc_minor"],
            signal_uncertainty_minor=item["uncertainty_minor"],
            target_margin_minor=(V5_USD_FLOOR_MINOR if currency == "USD" else None),
        )
        sector = item["sector"]
        niches[sector]["research_forecast_rows_by_horizon"][str(horizon)] += 1
        niches[sector]["research_lower_bound_below_floor_rows"] += int(
            rpc["research_lower_below_target"] is True
        )
        forecast_screens.append({
            "forecast_id": fid, "sector": sector,
            "horizon_days": horizon,
            "issued_at_utc": issued.isoformat(),
            "research_risk_band": rpc,
            "eligible_for_bid": False,
            "issued_forecast_independently_attested": False,
            "bank_matched_outcome": None,
        })

    report = {
        "schema_version": V5_CLOUD_SCHEMA,
        "mode": "OFFLINE_STAGING_OBSERVER",
        "tenant_scope": tenant, "company_scope": company,
        "currency": currency, "as_of_utc": now.isoformat(),
        "original_platform": "EmpireOS / EmpireDB / Smart CRM",
        "source_company_signed_review_sha256_not_rights_attestation":
            signed_company_review.get("snapshot_sha256_not_external_attestation"),
        "all_four_core_niches": niches,
        "signal_ingest_research_rows_unverified": signals,
        "issued_forecast_risk_screens_unverified": forecast_screens,
        "horizons_days": list(V5_HORIZONS),
        "usd_rpc_floor_minor": V5_USD_FLOOR_MINOR,
        "rpc_floor_is_not_verified_net_margin": True,
        "claim_100000_real_staging_events_independently_verified": False,
        "claim_22_2_percent_real_mae_gain_independently_verified": False,
        "independent_source_authorization_and_entitlements_verified": False,
        "full_opportunity_denominator_verified": False,
        "original_forecast_issuance_registry_verified": False,
        "finance_one_to_one_bank_and_refund_matching_verified": False,
        "mature_30_60_90_forecast_outcome_evaluation": None,
        "financial_outcome_matcher_state":
            "HOLD_NO_CANONICAL_FINANCE_ISSUANCE_AND_SETTLEMENT_CUSTODY",
        "model_arena_human_promotion_or_retraining_authorized": False,
        "autonomous_bid_approved_or_sent": False,
        "capital_risk_throttle_active_all_niches": True,
        "anomaly_original_records_deleted_or_quarantined": False,
        "production_migrations_066_071_applied": False,
        "live_network_database_crm_or_finance_access": False,
        "execution_authority": "none",
        "decision": "HOLD_REAL_COMPANY_SOURCE_RIGHTS_FORECAST_ISSUANCE_AND_CASH",
    }
    report["snapshot_sha256_not_production_attestation"] = _canonical_hash(report)
    return report
