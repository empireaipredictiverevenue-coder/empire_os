"""Canonical mathematical scenario review; zero execution or revenue attribution."""
import math
from copy import deepcopy
import pytest

from empire_os.predictive_revenue_formula import (
    CORE_FACTORS, expected_revenue_value,
    predictive_revenue_formula, revenue_formula_identification_bounds,
    review_revenue_factor_counterfactuals,
)
from empire_os.predictive_cloud_formula import (
    CLOUD_FACTORS, predictive_cloud_formula, review_cloud_quality_counterfactuals,
)


def revenue_inputs(**updates):
    result = dict.fromkeys(CORE_FACTORS, 0.8)
    result["ltv_cents"] = 100_000
    result.update(updates)
    return result


def cloud_inputs(**updates):
    result = dict.fromkeys(CLOUD_FACTORS, 0.8)
    result.update(updates)
    return result


def provenance(keys):
    return {key: [f"canonical:evidence:{key}"] for key in keys}


def buyer_scenarios(**updates):
    params = {
        "inputs": revenue_inputs(),
        "interventions": [
            {"action_key": "qualify_buyers", "factor": "buyer_match",
             "target_value": 0.9, "scenario_cost_cents": 20},
            {"action_key": "improve_terms", "factor": "terms",
             "target_value": 0.85, "scenario_cost_cents": 10},
        ],
        "factor_evidence_refs": provenance((*CORE_FACTORS, "ltv_cents")),
    }
    params.update(updates)
    return params


def cloud_scenarios(**updates):
    params = {
        "factors": cloud_inputs(),
        "residual_uncertainty": 0.2,
        "opportunities": [{
            "opportunity_key": "one",
            "status": "AVAILABLE",
            "expected_revenue_value_cents": 10000,
        }],
        "constraints": {
            "capacity": True, "compliance": True, "inventory": True,
            "cash": True, "authority": True, "fulfilment": True,
        },
        "improvements": [
            {"action_key": "source_health",
             "factor": "signal_freshness", "target_value": 0.9},
            {"action_key": "reduce_uncertainty",
             "factor": "residual_uncertainty", "target_value": 0.1},
        ],
        "evidence_refs": provenance((*CLOUD_FACTORS, "residual_uncertainty")),
    }
    params.update(updates)
    return params


def test_revenue_bounds_distinguish_unknown_from_real_zero():
    partial = revenue_formula_identification_bounds({
        "demand": 0.8, "quality": 0.5, "ltv_cents": 10000
    })
    assert partial["status"] == "PARTIALLY_IDENTIFIED"
    assert partial["lower_bound_cents"] == 0
    assert partial["upper_bound_cents"] == pytest.approx(4000)
    assert partial["missing_fields"]
    assert partial["interval_type"].startswith("deterministic")
    full = revenue_formula_identification_bounds(revenue_inputs(conversion=0))
    assert full["status"] == "FULLY_SPECIFIED_SCENARIO"
    assert full["lower_bound_cents"] == 0
    assert full["upper_bound_cents"] == 0
    no_ltv = revenue_formula_identification_bounds({"demand": 0})
    assert no_ltv["status"] == "UNAVAILABLE"
    assert no_ltv["upper_bound_cents"] is None


def test_revenue_sensitivity_is_exact_one_factor_difference():
    params = buyer_scenarios()
    frozen = deepcopy(params)
    review = review_revenue_factor_counterfactuals(**params)
    baseline = predictive_revenue_formula(params["inputs"])["predicted_revenue_cents"]
    scenario = review["scenarios"][0]
    computed = dict(params["inputs"], buyer_match=0.9)
    new_value = predictive_revenue_formula(computed)["predicted_revenue_cents"]
    assert review["status"] == "HYPOTHETICAL_REVIEW"
    assert scenario["action_key"] == "qualify_buyers"
    assert scenario["hypothetical_incremental_revenue_cents"] == pytest.approx(
        new_value - baseline
    )
    assert scenario["hypothetical_net_change_cents"] == pytest.approx(
        new_value - baseline - 20
    )
    assert scenario["marginal_sensitivity_cents_per_unit"] == pytest.approx(
        100_000 * 0.8 ** 9
    )
    assert review["actual_revenue"] is False
    assert review["execution_authority"] == "none"
    assert review["independence_and_calibration_not_proven"] is True
    assert params == frozen


def test_incomplete_evidence_holds_scenarios_without_numbers():
    params = buyer_scenarios()
    params["factor_evidence_refs"].pop("payment")
    out = review_revenue_factor_counterfactuals(**params)
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["scenarios"] == []
    assert out["missing_factor_evidence_refs"] == ["payment"]
    params["inputs"]["payment"] = None
    out = review_revenue_factor_counterfactuals(**params)
    assert "payment" in out["missing_factor_inputs"]
    assert out["identification_bounds"]["status"] == "PARTIALLY_IDENTIFIED"


@pytest.mark.parametrize("intervention", [
    {"action_key": "bad", "factor": "buyer_match", "target_value": 0.7,
     "scenario_cost_cents": 0},
    {"action_key": "bad", "factor": "new_factor", "target_value": 0.9,
     "scenario_cost_cents": 0},
    {"action_key": "bad", "factor": "terms", "target_value": 1.5,
     "scenario_cost_cents": 0},
    {"action_key": "bad", "factor": "terms", "target_value": 0.9,
     "scenario_cost_cents": -1},
    {"action_key": "bad", "factor": "terms", "target_value": float("nan"),
     "scenario_cost_cents": 0},
])
def test_revenue_interventions_refuse_invalid_hypotheses(intervention):
    with pytest.raises(ValueError):
        review_revenue_factor_counterfactuals(
            **buyer_scenarios(interventions=[intervention])
        )


def test_known_zero_factor_does_not_magically_create_revenue():
    inputs = revenue_inputs(payment=0, buyer_match=0)
    out = review_revenue_factor_counterfactuals(
        **buyer_scenarios(
            inputs=inputs, interventions=[{
                "action_key": "buyer_improvement",
                "factor": "buyer_match",
                "target_value": 1,
                "scenario_cost_cents": 0,
            }],
        )
    )
    assert out["scenarios"][0]["hypothetical_incremental_revenue_cents"] == 0
    assert out["scenarios"][0]["marginal_sensitivity_cents_per_unit"] == 0


def test_cloud_formula_marks_partially_unknown_portfolio_without_breaking_legacy_sum():
    snapshot = predictive_cloud_formula(
        factors=cloud_inputs(),
        residual_uncertainty=0.2,
        opportunities=[
            {"opportunity_key": "known", "status": "AVAILABLE",
             "expected_revenue_value_cents": 10000},
            {"opportunity_key": "unknown", "status": "UNAVAILABLE",
             "expected_revenue_value_cents": None},
        ],
    )
    assert snapshot["status"] == "AVAILABLE"
    assert snapshot["portfolio"]["portfolio_value_scope"] == "AVAILABLE_ONLY"
    assert snapshot["portfolio"]["unknown_opportunities_included_as_zero"] is False
    assert snapshot["cloud_adjusted_portfolio_value_cents"] > 0
    assert snapshot["cloud_adjusted_portfolio_value_is_partial"] is True
    assert snapshot["cloud_adjusted_full_portfolio_value_cents"] is None


def test_cloud_quality_counterfactual_recomputes_original_formula():
    params = cloud_scenarios()
    frozen = deepcopy(params)
    result = review_cloud_quality_counterfactuals(**params)
    baseline = predictive_cloud_formula(
        factors=params["factors"], residual_uncertainty=params["residual_uncertainty"],
        opportunities=params["opportunities"], constraints=params["constraints"],
    )
    assert result["status"] == "HYPOTHETICAL_REVIEW"
    assert result["portfolio_complete"] is True
    assert result["baseline_cloud_operating_score"] == baseline["cloud_operating_score"]
    changed = predictive_cloud_formula(
        factors=params["factors"], residual_uncertainty=0.1,
        opportunities=params["opportunities"], constraints=params["constraints"],
    )
    row = next(r for r in result["hypothetical_scenarios"]
               if r["action_key"] == "reduce_uncertainty")
    assert row["hypothetical_cloud_score_change"] == pytest.approx(
        changed["cloud_operating_score"] - baseline["cloud_operating_score"]
    )
    assert row["hypothetical_complete_portfolio_value_change_cents"] == pytest.approx(
        changed["cloud_adjusted_full_portfolio_value_cents"]
        - baseline["cloud_adjusted_full_portfolio_value_cents"]
    )
    assert result["improvements_have_no_causal_proof"] is True
    assert result["commercial_authority"] == "none"
    assert params == frozen


def test_cloud_does_not_prorate_unknown_opportunities_as_zero():
    params = cloud_scenarios()
    params["opportunities"].append({
        "opportunity_key": "unknown",
        "status": "UNAVAILABLE",
        "expected_revenue_value_cents": None,
    })
    result = review_cloud_quality_counterfactuals(**params)
    assert result["portfolio_complete"] is False
    assert result["baseline_cloud_adjusted_full_portfolio_value_cents"] is None
    assert all(
        row["hypothetical_complete_portfolio_value_change_cents"] is None
        for row in result["hypothetical_scenarios"]
    )


def test_cloud_operating_constraints_are_inherited_not_overridden():
    params = cloud_scenarios()
    params["constraints"]["authority"] = False
    result = review_cloud_quality_counterfactuals(**params)
    assert result["operating_constraints"]["state"] == "BLOCKED"
    assert "authority" in result["operating_constraints"]["blockers"]
    assert all(row["action_authorized"] is False for row in result["hypothetical_scenarios"])


@pytest.mark.parametrize("improvement", [
    {"action_key": "bad", "factor": "not-real", "target_value": 1},
    {"action_key": "bad", "factor": "signal_freshness", "target_value": 0.3},
    {"action_key": "bad", "factor": "signal_freshness", "target_value": float("inf")},
    {"action_key": "bad", "factor": "residual_uncertainty", "target_value": 0.9},
])
def test_invalid_cloud_improvements_fail(improvement):
    with pytest.raises(ValueError):
        review_cloud_quality_counterfactuals(
            **cloud_scenarios(improvements=[improvement])
        )


def test_cloud_missing_evidence_is_not_a_formula_prediction():
    params = cloud_scenarios()
    params["evidence_refs"].pop("causal_confidence")
    result = review_cloud_quality_counterfactuals(**params)
    assert result["status"] == "EVIDENCE_HOLD"
    assert result["hypothetical_scenarios"] == []
    assert "causal_confidence" in result["missing_evidence_refs"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True])
def test_both_canonical_models_reject_nonfinite_or_boolean_inputs(bad):
    with pytest.raises(ValueError):
        predictive_revenue_formula(revenue_inputs(payment=bad))
    with pytest.raises(ValueError):
        revenue_formula_identification_bounds(revenue_inputs(payment=bad))
    with pytest.raises(ValueError):
        predictive_cloud_formula(
            factors=cloud_inputs(signal_freshness=bad),
            residual_uncertainty=0.2,
            opportunities=[],
        )
    with pytest.raises(ValueError):
        expected_revenue_value({
            "probability_close": bad,
            "probability_payment_given_close": 0.5,
            "probability_fulfilment_given_payment": 1,
            "ltv_cents": 100000,
            "margin_factor": 0.5,
            "capacity_factor": 0.5,
            "recency_factor": 0.9,
            "confidence": 0.8,
            "time_discount_factor": 0.9,
            "acquisition_cost_cents": 10,
            "fulfilment_cost_cents": 5,
            "risk_cost_cents": 1,
        })


def test_cloud_never_claims_complete_value_from_non_available_row():
    output = predictive_cloud_formula(
        factors=cloud_inputs(),
        residual_uncertainty=0.2,
        opportunities=[
            {"opportunity_key": "unapproved", "status": "REVIEW_ONLY",
             "expected_revenue_value_cents": 999_999_999},
            {"opportunity_key": "verified_input", "status": "AVAILABLE",
             "expected_revenue_value_cents": 1000},
        ],
    )
    assert output["portfolio"]["portfolio_expected_revenue_value_cents"] == 1000
    assert output["portfolio"]["complete_portfolio_value_known"] is False
    assert output["cloud_adjusted_full_portfolio_value_cents"] is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_cloud_rejects_non_finite_economic_item(value):
    with pytest.raises(ValueError):
        predictive_cloud_formula(
            factors=cloud_inputs(),
            residual_uncertainty=0.1,
            opportunities=[{
                "status": "AVAILABLE",
                "opportunity_key": "anomaly",
                "expected_revenue_value_cents": value,
            }],
        )


def test_joint_counterfactual_attributes_interactions_without_double_counting():
    from empire_os.predictive_revenue_formula import review_joint_revenue_counterfactual
    factors = {key: 1 for key in CORE_FACTORS}
    factors.update(buyer_match=0.5, terms=0.5, ltv_cents=10000)
    snapshot = deepcopy(factors)
    result = review_joint_revenue_counterfactual(
        factors,
        {"buyer_match": 1.0, "terms": 1.0},
        scenario_cost_cents=500,
        factor_evidence_refs=provenance((*CORE_FACTORS, "ltv_cents")),
    )
    assert result["status"] == "HYPOTHETICAL_REVIEW"
    assert result["baseline_predicted_revenue_cents"] == 2500
    assert result["hypothetical_joint_predicted_revenue_cents"] == 10000
    assert result["joint_delta_cents"] == 7500
    assert result["isolated_increment_sum_cents"] == 5000
    assert result["multi_factor_interaction_cents"] == 2500
    assert result["hypothetical_net_delta_cents"] == 7000
    shares = {row["factor"]: row["shapley_mathematical_share_cents"]
              for row in result["mathematical_factor_attributions"]}
    assert shares == {"buyer_match": 3750, "terms": 3750}
    assert result["attributions_not_causal_or_observed"] is True
    assert result["actual_revenue"] is False
    assert result["payment_authorized"] is False
    assert factors == snapshot


def test_joint_single_factor_equals_existing_counterfactual_delta():
    from empire_os.predictive_revenue_formula import review_joint_revenue_counterfactual
    inputs = revenue_inputs()
    ref = provenance((*CORE_FACTORS, "ltv_cents"))
    joint = review_joint_revenue_counterfactual(
        inputs, {"buyer_match": 0.9}, scenario_cost_cents=20,
        factor_evidence_refs=ref,
    )
    single = review_revenue_factor_counterfactuals(
        inputs, [{
            "action_key": "one",
            "factor": "buyer_match",
            "target_value": 0.9,
            "scenario_cost_cents": 20,
        }], factor_evidence_refs=ref,
    )
    assert joint["multi_factor_interaction_cents"] == 0
    assert joint["joint_delta_cents"] == pytest.approx(
        single["scenarios"][0]["hypothetical_incremental_revenue_cents"],
        abs=0.0001,
    )


def test_joint_requires_baseline_provenance_and_keeps_null():
    from empire_os.predictive_revenue_formula import review_joint_revenue_counterfactual
    refs = provenance((*CORE_FACTORS, "ltv_cents"))
    refs.pop("payment")
    out = review_joint_revenue_counterfactual(
        revenue_inputs(), {"buyer_match": 0.9},
        scenario_cost_cents=0, factor_evidence_refs=refs,
    )
    assert out["status"] == "EVIDENCE_HOLD"
    assert out["joint_delta_cents"] is None
    assert "payment" in out["missing_factor_evidence_refs"]


@pytest.mark.parametrize("targets,cost", [
    ({}, 0),
    ({"made_up_factor": 1.0}, 0),
    ({"buyer_match": 0.1}, 0),
    ({"buyer_match": float("nan")}, 0),
    ({"buyer_match": 1.0}, -10),
])
def test_invalid_joint_hypotheses_fail_closed(targets, cost):
    from empire_os.predictive_revenue_formula import review_joint_revenue_counterfactual
    with pytest.raises(ValueError):
        review_joint_revenue_counterfactual(
            revenue_inputs(), targets, scenario_cost_cents=cost,
            factor_evidence_refs=provenance((*CORE_FACTORS, "ltv_cents")),
        )
