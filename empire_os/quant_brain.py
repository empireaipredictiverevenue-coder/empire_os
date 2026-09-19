"""Deterministic quantitative intelligence primitives for Empire AI.

No external side effects. Predictions/simulations are explicitly non-actual.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from random import Random
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


def _prob(value: Any, name: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not 0 <= x <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return x


def _number(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


@dataclass(frozen=True)
class BetaPosterior:
    alpha: float
    beta: float
    mean_probability: float
    observed_successes: int
    observed_failures: int
    real_outcomes_only: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def update_beta_posterior(
    *,
    prior_alpha: float,
    prior_beta: float,
    successes: int,
    failures: int,
    verified_real_outcomes: bool,
) -> BetaPosterior:
    a = _number(prior_alpha, "prior_alpha")
    b = _number(prior_beta, "prior_beta")
    if a <= 0 or b <= 0:
        raise ValueError("beta prior parameters must be positive")
    if successes < 0 or failures < 0:
        raise ValueError("success/failure counts must be nonnegative")
    if not verified_real_outcomes and (successes or failures):
        raise ValueError("commercial posterior updates require verified real outcomes")
    alpha = a + successes
    beta = b + failures
    return BetaPosterior(
        alpha=alpha,
        beta=beta,
        mean_probability=alpha / (alpha + beta),
        observed_successes=successes,
        observed_failures=failures,
    )


@dataclass(frozen=True)
class ExpectedEconomics:
    probability_success: float
    conditional_revenue_cents: float
    fixed_cost_cents: float
    success_cost_cents: float
    expected_revenue_cents: float
    expected_cost_cents: float
    expected_gross_profit_cents: float
    downside_if_failure_cents: float
    prediction_only: bool = True
    actual_revenue: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def expected_economics(
    *,
    probability_success: float,
    conditional_revenue_cents: float,
    fixed_cost_cents: float = 0,
    success_cost_cents: float = 0,
) -> ExpectedEconomics:
    p = _prob(probability_success, "probability_success")
    revenue = _number(conditional_revenue_cents, "conditional_revenue_cents")
    fixed = _number(fixed_cost_cents, "fixed_cost_cents")
    success_cost = _number(success_cost_cents, "success_cost_cents")
    if min(revenue, fixed, success_cost) < 0:
        raise ValueError("economics inputs must be nonnegative")
    expected_revenue = p * revenue
    expected_cost = fixed + (p * success_cost)
    return ExpectedEconomics(
        probability_success=p,
        conditional_revenue_cents=revenue,
        fixed_cost_cents=fixed,
        success_cost_cents=success_cost,
        expected_revenue_cents=expected_revenue,
        expected_cost_cents=expected_cost,
        expected_gross_profit_cents=expected_revenue - expected_cost,
        downside_if_failure_cents=fixed,
    )


def brier_score(predictions: Sequence[float], outcomes: Sequence[int]) -> dict[str, Any]:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        return {"available": False, "reason": "no_samples", "sample_count": 0}
    ps = [_prob(p, "prediction") for p in predictions]
    ys = [int(y) for y in outcomes]
    if any(y not in (0, 1) for y in ys):
        raise ValueError("binary outcomes must be 0 or 1")
    score = sum((p-y) ** 2 for p, y in zip(ps, ys)) / len(ps)
    return {
        "available": True,
        "sample_count": len(ps),
        "brier_score": round(score, 6),
        "lower_is_better": True,
    }


def risk_adjusted_score(
    *,
    expected_gross_profit_cents: float,
    downside_cents: float,
    uncertainty: float,
    time_to_revenue_days: float,
    confidence: float,
) -> dict[str, Any]:
    gp = _number(expected_gross_profit_cents, "expected_gross_profit_cents")
    downside = _number(downside_cents, "downside_cents")
    uncertainty_value = _prob(uncertainty, "uncertainty")
    confidence_value = _prob(confidence, "confidence")
    days = _number(time_to_revenue_days, "time_to_revenue_days")
    if downside < 0 or days < 0:
        raise ValueError("downside and time_to_revenue_days must be nonnegative")
    risk_penalty = downside * (0.5 + uncertainty_value)
    time_discount = 1 / (1 + days / 30)
    score = (gp - risk_penalty) * confidence_value * time_discount
    return {
        "risk_adjusted_score": round(score, 4),
        "expected_gross_profit_cents": gp,
        "risk_penalty_cents": round(risk_penalty, 4),
        "time_discount": round(time_discount, 6),
        "confidence": confidence_value,
        "recommendation_only": True,
        "execution_authority": "none",
    }


def rank_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows=[]
    for raw in candidates:
        candidate_id=str(raw.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("candidate_id required")
        scored=risk_adjusted_score(
            expected_gross_profit_cents=raw.get("expected_gross_profit_cents"),
            downside_cents=raw.get("downside_cents",0),
            uncertainty=raw.get("uncertainty"),
            time_to_revenue_days=raw.get("time_to_revenue_days",0),
            confidence=raw.get("confidence"),
        )
        rows.append({"candidate_id":candidate_id, **scored})
    rows.sort(key=lambda x:(x["risk_adjusted_score"],x["candidate_id"]),reverse=True)
    for i,row in enumerate(rows,1):
        row["rank"]=i
    return rows


def monte_carlo_economics(
    *,
    probability_success: float,
    revenue_low_cents: float,
    revenue_high_cents: float,
    fixed_cost_cents: float,
    success_cost_low_cents: float = 0,
    success_cost_high_cents: float = 0,
    trials: int = 5000,
    seed: int = 0,
) -> dict[str, Any]:
    p=_prob(probability_success,"probability_success")
    lo=_number(revenue_low_cents,"revenue_low_cents")
    hi=_number(revenue_high_cents,"revenue_high_cents")
    fixed=_number(fixed_cost_cents,"fixed_cost_cents")
    scl=_number(success_cost_low_cents,"success_cost_low_cents")
    sch=_number(success_cost_high_cents,"success_cost_high_cents")
    if lo<0 or hi<lo or fixed<0 or scl<0 or sch<scl:
        raise ValueError("invalid Monte Carlo bounds")
    if trials<100 or trials>100000:
        raise ValueError("trials must be between 100 and 100000")
    rng=Random(seed)
    gps=[]
    for _ in range(trials):
        if rng.random()<p:
            revenue=rng.uniform(lo,hi)
            success_cost=rng.uniform(scl,sch)
            gp=revenue-fixed-success_cost
        else:
            gp=-fixed
        gps.append(gp)
    gps.sort()
    q=lambda frac:gps[min(int(frac*(trials-1)),trials-1)]
    return {
        "simulation_only":True,
        "actual_revenue":False,
        "trial_count":trials,
        "seed":seed,
        "mean_gross_profit_cents":round(mean(gps),2),
        "p05_gross_profit_cents":round(q(0.05),2),
        "p50_gross_profit_cents":round(q(0.50),2),
        "p95_gross_profit_cents":round(q(0.95),2),
        "probability_negative_gross_profit":round(sum(1 for x in gps if x<0)/trials,6),
        "execution_authority":"none",
    }


def value_of_information(
    *,
    current_expected_value_cents: float,
    informed_expected_value_cents: float,
    information_cost_cents: float,
    probability_information_changes_decision: float,
) -> dict[str, Any]:
    current=_number(current_expected_value_cents,"current_expected_value_cents")
    informed=_number(informed_expected_value_cents,"informed_expected_value_cents")
    cost=_number(information_cost_cents,"information_cost_cents")
    p=_prob(probability_information_changes_decision,"probability_information_changes_decision")
    if cost<0:
        raise ValueError("information_cost_cents must be nonnegative")
    gross=max(0.0,informed-current)*p
    net=gross-cost
    return {
        "gross_value_of_information_cents":round(gross,2),
        "information_cost_cents":cost,
        "net_value_of_information_cents":round(net,2),
        "worth_collecting":net>0,
        "estimate_only":True,
        "execution_authority":"none",
    }


def portfolio_concentration(weights: Mapping[str, float]) -> dict[str, Any]:
    if not weights:
        return {"available":False,"reason":"no_weights"}
    cleaned={}
    for key,value in weights.items():
        w=_number(value,f"weight:{key}")
        if w<0:
            raise ValueError("weights must be nonnegative")
        cleaned[str(key)]=w
    total=sum(cleaned.values())
    if total<=0:
        raise ValueError("portfolio weight total must be positive")
    normalized={k:v/total for k,v in cleaned.items()}
    hhi=sum(w*w for w in normalized.values())
    return {
        "available":True,
        "normalized_weights":normalized,
        "herfindahl_index":round(hhi,6),
        "effective_number_of_positions":round(1/hhi,4) if hhi else None,
        "largest_weight":round(max(normalized.values()),6),
        "recommendation_only":True,
    }
