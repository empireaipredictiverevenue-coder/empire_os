import pytest
from empire_os.quant_brain import (
    brier_score, expected_economics, monte_carlo_economics,
    portfolio_concentration, rank_candidates, update_beta_posterior,
    value_of_information,
)

def test_beta_updates_only_with_verified_real_outcomes():
    p=update_beta_posterior(prior_alpha=1,prior_beta=1,successes=8,failures=2,
                            verified_real_outcomes=True)
    assert round(p.mean_probability,4)==0.75
    with pytest.raises(ValueError,match="verified real outcomes"):
        update_beta_posterior(prior_alpha=1,prior_beta=1,successes=1,failures=0,
                              verified_real_outcomes=False)

def test_expected_economics_never_claims_actual():
    e=expected_economics(probability_success=.4,conditional_revenue_cents=100000,
                         fixed_cost_cents=10000,success_cost_cents=10000)
    assert e.expected_revenue_cents==40000
    assert e.expected_cost_cents==14000
    assert e.expected_gross_profit_cents==26000
    assert e.actual_revenue is False

def test_brier_score_calibration():
    r=brier_score([.9,.2],[1,0])
    assert r["available"] is True
    assert r["brier_score"]==0.025

def test_ranking_uses_risk_time_confidence():
    rows=rank_candidates([
        {"candidate_id":"fast","expected_gross_profit_cents":50000,
         "downside_cents":5000,"uncertainty":.2,"time_to_revenue_days":5,"confidence":.9},
        {"candidate_id":"risky","expected_gross_profit_cents":70000,
         "downside_cents":50000,"uncertainty":.9,"time_to_revenue_days":60,"confidence":.5},
    ])
    assert rows[0]["candidate_id"]=="fast"
    assert rows[0]["rank"]==1
    assert rows[0]["execution_authority"]=="none"

def test_monte_carlo_is_deterministic_simulation():
    kwargs=dict(probability_success=.5,revenue_low_cents=100000,revenue_high_cents=120000,
                fixed_cost_cents=10000,success_cost_low_cents=10000,
                success_cost_high_cents=20000,trials=1000,seed=42)
    a=monte_carlo_economics(**kwargs)
    b=monte_carlo_economics(**kwargs)
    assert a==b
    assert a["simulation_only"] is True
    assert a["actual_revenue"] is False

def test_value_of_information():
    r=value_of_information(current_expected_value_cents=10000,
                           informed_expected_value_cents=30000,
                           information_cost_cents=2000,
                           probability_information_changes_decision=.5)
    assert r["gross_value_of_information_cents"]==10000
    assert r["net_value_of_information_cents"]==8000
    assert r["worth_collecting"] is True

def test_portfolio_concentration():
    r=portfolio_concentration({"roofing":50,"legal":25,"dental":25})
    assert r["available"] is True
    assert r["herfindahl_index"]==0.375
    assert r["largest_weight"]==0.5
