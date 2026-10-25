"""EmpireOS Predictive Revenue V4.12: synthetic organic revenue cash twin.

Pure simulation with original V4.11 signed CRM + V4.10 HELD source gate.
No database, service, trading, capital, outbound or live execution actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, isfinite, log, sqrt
from typing import Any

import numpy as np

from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
from empire_os.predictive_revenue_v411_source_gate import review_revenue_source_candidate_held
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier

SCHEMA = "empire.predictive_revenue.v412.synthetic_cash_twin.v1"
HORIZONS = (30, 60, 90)
WEIGHTS = (0.35, 0.25, 0.25, 0.15)


@dataclass(frozen=True)
class RevenueResearchScenario:
    source_evidence_digest: str
    sector: str
    intent_velocity_score: float
    economic_capacity_score: float
    observed_need_score: float
    timing_alignment_score: float
    cohort_opportunities: int
    prior_observed_opportunities: int
    prior_observed_wins: int
    deal_value_cents: int
    fulfilment_cost_per_win_cents: int
    median_days_to_cash: float
    cash_lag_log_sigma: float = 0.65
    research_overhead_cents: int = 0
    iterations: int = 2000
    seed: int = 20261025
    acquisition_channel: str = "ORGANIC_ONLY"
    paid_media_budget_cents: int = 0

    def validate(self) -> None:
        from re import fullmatch
        if type(self.source_evidence_digest) is not str or not fullmatch(
            r"[a-f0-9]{64}", self.source_evidence_digest
        ):
            raise ValueError("V412_SOURCE_DIGEST_INVALID")
        if not isinstance(self.sector, str) or not 1 <= len(self.sector) <= 64 or not self.sector.replace("_", "").isalnum():
            raise ValueError("V412_SECTOR_INVALID")
        for value in (
            self.intent_velocity_score, self.economic_capacity_score,
            self.observed_need_score, self.timing_alignment_score,
        ):
            if type(value) not in (int, float) or not isfinite(value) or not 0 <= value <= 100:
                raise ValueError("V412_SCORE_OUT_OF_RANGE")
        for value in (
            self.cohort_opportunities, self.prior_observed_opportunities,
            self.prior_observed_wins, self.deal_value_cents,
            self.fulfilment_cost_per_win_cents, self.research_overhead_cents,
            self.iterations, self.seed, self.paid_media_budget_cents,
        ):
            if type(value) is not int:
                raise ValueError("V412_EXACT_INTEGER_REQUIRED")
        if not (
            0 <= self.cohort_opportunities <= 100000
            and 0 <= self.prior_observed_opportunities <= 1000000
            and 0 <= self.prior_observed_wins <= self.prior_observed_opportunities
            and 1 <= self.deal_value_cents <= 10**11
            and 0 <= self.fulfilment_cost_per_win_cents <= self.deal_value_cents
            and 0 <= self.research_overhead_cents <= 10**11
            and 2000 <= self.iterations <= 10000
            and 0 <= self.seed < 2**32
        ):
            raise ValueError("V412_ASSUMPTIONS_OUT_OF_RANGE")
        for value, lower, upper in (
            (self.median_days_to_cash, 1.0, 3650.0),
            (self.cash_lag_log_sigma, 0.1, 3.0),
        ):
            if type(value) not in (int, float) or not isfinite(value) or not lower <= value <= upper:
                raise ValueError("V412_INVALID_CASH_LAG")
        if self.acquisition_channel != "ORGANIC_ONLY" or self.paid_media_budget_cents != 0:
            raise ValueError("V412_PAID_TRAFFIC_NOT_SUPPORTED")


def score_opportunity_for_review(scenario: RevenueResearchScenario) -> dict[str, Any]:
    """35/25/25/15 priority only: not permission or causal identification."""
    scenario.validate()
    scores = (
        scenario.intent_velocity_score, scenario.economic_capacity_score,
        scenario.observed_need_score, scenario.timing_alignment_score,
    )
    score = round(sum(float(s) * weight for s, weight in zip(scores, WEIGHTS)), 2)
    tier = (
        "TIER_1_FOUNDER_REVIEW" if score >= 85
        else "TIER_2_RESEARCH_REVIEW" if score >= 70
        else "TIER_3_RESEARCH_NURTURE"
    )
    return {
        "score": score,
        "tier": tier,
        "score_weighting": "intent_35_capacity_25_need_25_timing_15",
        "causal_lift_established": False,
        "opportunity_commercially_qualified": False,
        "outbound_authorized": False,
        "paid_traffic_authorized": False,
    }


def _cash_cdf(horizon_days: int, median_days: float, sigma: float) -> float:
    # Explicit lognormal assumption on collectible cash lag, not measured data.
    z = (log(horizon_days) - log(median_days)) / (sigma * sqrt(2.0))
    return 0.5 * (1.0 + erf(z))


def _cash_quantiles(scenario: RevenueResearchScenario) -> dict[str, dict[str, int]]:
    """Joint 30/60/90 trajectories share one beta draw per simulated path.

    One multinomial 4-bin draw (0-30, 30-60, 60-90, later/no close) per path
    makes cumulative cash nondecreasing in each iteration. It is not an
    empirically calibrated customer or capital allocation forecast.
    """
    rng = np.random.default_rng(scenario.seed)
    # Research prior Beta(1,19) means 5% baseline before synthetic observations.
    alpha = 1.0 + scenario.prior_observed_wins
    beta = 19.0 + scenario.prior_observed_opportunities - scenario.prior_observed_wins
    win_rates = rng.beta(alpha, beta, size=scenario.iterations)
    f30, f60, f90 = (
        _cash_cdf(day, scenario.median_days_to_cash, scenario.cash_lag_log_sigma)
        for day in HORIZONS
    )
    probabilities = np.column_stack((
        win_rates * f30,
        win_rates * (f60 - f30),
        win_rates * (f90 - f60),
        1.0 - win_rates * f90,
    ))
    bins = rng.multinomial(scenario.cohort_opportunities, probabilities)
    cumulative_wins = np.cumsum(bins[:, :3], axis=1).astype(np.int64)
    gross_cash = cumulative_wins * scenario.deal_value_cents
    contribution_cash = (
        cumulative_wins * (
            scenario.deal_value_cents - scenario.fulfilment_cost_per_win_cents
        ) - scenario.research_overhead_cents
    )
    result = {}
    for i, horizon in enumerate(HORIZONS):
        gross = np.percentile(gross_cash[:, i], [10, 50, 90])
        contribution = np.percentile(contribution_cash[:, i], [10, 50, 90])
        result[str(horizon)] = {
            "p10_gross_cash_cents": int(round(float(gross[0]))),
            "p50_gross_cash_cents": int(round(float(gross[1]))),
            "p90_gross_cash_cents": int(round(float(gross[2]))),
            "p10_contribution_cents": int(round(float(contribution[0]))),
            "p50_contribution_cents": int(round(float(contribution[1]))),
            "p90_contribution_cents": int(round(float(contribution[2]))),
        }
    return result


def simulate_revenue_twin_held(
    scenario: RevenueResearchScenario,
    *,
    signed_crm_bearer: str,
    crm_verifier: SignedCrmTenantVerifier,
    source_rights_reader: EmpireDbHeldSourceRightsReader,
) -> dict[str, Any]:
    """Signed CRM research user; HELD source; bounded synthetic cohort only."""
    if type(scenario) is not RevenueResearchScenario:
        raise TypeError("V412_SCENARIO_TYPE_REQUIRED")
    scenario.validate()
    source_review = review_revenue_source_candidate_held(
        crm_bearer=signed_crm_bearer,
        crm_verifier=crm_verifier,
        source_rights_reader=source_rights_reader,
        source_evidence_digest=scenario.source_evidence_digest,
    )
    return {
        "schema_version": SCHEMA,
        "mode": "SIMULATION",
        "status": "SYNTHETIC_ORGANIC_REVENUE_TWIN_HELD",
        "simulation_only": True,
        "canonical_database": "EmpireDB_PostgreSQL",
        "canonical_tenant_id": source_review["canonical_tenant_id"],
        "source_evidence_digest": scenario.source_evidence_digest,
        "source_rights_decision": source_review["rights_decision"],
        "original_crm_membership_verified": True,
        "licensed_source_admitted": False,
        "causal_identification_verified": False,
        "forecast_empirically_calibrated": False,
        "confidence_intervals_empirically_validated": False,
        "scenario_assumptions": {
            "sector": scenario.sector,
            "channel": scenario.acquisition_channel,
            "day_zero_opportunity_cohort": scenario.cohort_opportunities,
            "research_observed_opportunities_unverified": scenario.prior_observed_opportunities,
            "research_observed_wins_unverified": scenario.prior_observed_wins,
            "synthetic_prior": "Beta(1,19)",
            "cash_lag": "lognormal_median_and_sigma_assumption",
            "deal_value_cents": scenario.deal_value_cents,
            "fulfilment_cost_per_win_cents": scenario.fulfilment_cost_per_win_cents,
            "research_overhead_cents": scenario.research_overhead_cents,
            "iterations": scenario.iterations,
            "seed": scenario.seed,
        },
        "opportunity_priority": score_opportunity_for_review(scenario),
        "forecast_horizons": _cash_quantiles(scenario),
        "roas": None,
        "revenue_recognised_cents": None,
        "approved_commercial_forecast": False,
        "capital_deployment_authorized": False,
        "buyer_outreach_authorized": False,
        "lead_delivery_authorized": False,
        "economic_memory_write_authorized": False,
        "redis_publish_authorized": False,
        "execution_authority": "none",
    }


def review_cash_twin_drift_held(
    forecast: dict[str, Any],
    *,
    horizon_days: int,
    observed_cash_cents: int,
    observation_evidence_digest: str,
) -> dict[str, Any]:
    """Diagnostic 12% reflector; caller-supplied outcomes are unverified.

    Never updates a causal DAG, model, CRM, financial ledger or production
    forecasts. Actual paid receipt reconciliation needs a separately trusted
    owner-controlled economic-memory evidence path.
    """
    from re import fullmatch

    if type(forecast) is not dict or forecast.get("schema_version") != SCHEMA:
        raise ValueError("V412_NONCANONICAL_RESEARCH_FORECAST")
    if (forecast.get("mode") != "SIMULATION" or
        forecast.get("execution_authority") != "none" or
        forecast.get("approved_commercial_forecast") is not False or
        forecast.get("revenue_recognised_cents") is not None):
        raise ValueError("V412_UNTRUSTED_FORECAST_AUTHORITY")
    if type(horizon_days) is not int or horizon_days not in HORIZONS:
        raise ValueError("V412_INVALID_REVIEW_HORIZON")
    if type(observed_cash_cents) is not int or not 0 <= observed_cash_cents <= 10**16:
        raise ValueError("V412_INVALID_OUTCOME")
    if (type(observation_evidence_digest) is not str or
        not fullmatch(r"[a-f0-9]{64}", observation_evidence_digest)):
        raise ValueError("V412_INVALID_UNVERIFIED_OBSERVATION_DIGEST")
    horizons = forecast.get("forecast_horizons")
    if not isinstance(horizons, dict):
        raise ValueError("V412_FORECAST_HORIZONS_MISSING")
    row = horizons.get(str(horizon_days))
    if not isinstance(row, dict):
        raise ValueError("V412_FORECAST_HORIZON_MISSING")
    p50 = row.get("p50_gross_cash_cents")
    if type(p50) is not int or not 0 <= p50 <= 10**16:
        raise ValueError("V412_FORECAST_P50_INVALID")
    if p50 == 0:
        variance_ratio = None
        threshold_crossed = False
        status = "ZERO_SYNTHETIC_P50_NOT_COMPARABLE_HELD"
    else:
        variance_ratio = round((observed_cash_cents - p50) / p50, 6)
        threshold_crossed = abs(variance_ratio) > 0.12
        status = ("RECALIBRATION_RESEARCH_REVIEW_HELD" if threshold_crossed
                  else "RESEARCH_VARIANCE_WITHIN_THRESHOLD_HELD")
    return {
        "schema_version": "empire.predictive_revenue.v412.reflector_held.v1",
        "mode": "OBSERVE",
        "status": status,
        "horizon_days": horizon_days,
        "synthetic_p50_gross_cash_cents": p50,
        "caller_supplied_observed_cash_cents": observed_cash_cents,
        "observation_evidence_digest_unverified": observation_evidence_digest,
        "variance_ratio": variance_ratio,
        "research_threshold_12_percent_exceeded": threshold_crossed,
        "actual_receipt_independently_verified": False,
        "causal_effect_identified": False,
        "automatic_retraining": False,
        "auto_dag_reweight": False,
        "outreach_authorized": False,
        "capital_allocation_authorized": False,
        "forecast_promoted_to_commercial": False,
        "execution_authority": "none",
    }
