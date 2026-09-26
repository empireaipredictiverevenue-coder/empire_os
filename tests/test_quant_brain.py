import pytest
from empire_os.quant_brain import (
    brier_score,
    calibration_bins,
    expected_economics,
    log_loss,
    monte_carlo_economics,
    portfolio_concentration,
    quant_decision_packet,
    rank_candidates,
    update_beta_posterior,
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


def test_log_loss_and_reliability_bins():
    loss = log_loss([0.9, 0.2], [1, 0])
    reliability = calibration_bins([0.9, 0.2], [1, 0], bins=5)
    assert loss["available"] is True
    assert loss["log_loss"] > 0
    assert reliability["available"] is True
    assert reliability["sample_count"] == 2
    assert reliability["expected_calibration_error"] >= 0
    assert reliability["execution_authority"] == "none"


def test_decision_packet_fails_closed_when_economics_missing():
    packet = quant_decision_packet(
        candidate_id="opp:1",
        inputs={"probability_success": 0.5},
    )
    assert packet["status"] == "UNAVAILABLE"
    assert "conditional_revenue_cents" in packet["missing_fields"]
    assert packet["actual_revenue"] is False
    assert packet["execution_authority"] == "none"


def test_decision_packet_combines_economics_downside_and_voi():
    packet = quant_decision_packet(
        candidate_id="opp:2",
        inputs={
            "probability_success": 0.55,
            "conditional_revenue_cents": 150000,
            "fixed_cost_cents": 25000,
            "success_cost_cents": 30000,
            "revenue_low_cents": 120000,
            "revenue_high_cents": 180000,
            "success_cost_low_cents": 20000,
            "success_cost_high_cents": 40000,
            "uncertainty": 0.35,
            "time_to_revenue_days": 21,
            "confidence": 0.7,
            "current_expected_value_cents": 20000,
            "informed_expected_value_cents": 50000,
            "information_cost_cents": 5000,
            "probability_information_changes_decision": 0.5,
            "verified_predictions": [0.8, 0.3],
            "verified_outcomes": [1, 0],
            "calibration_bins": 5,
        },
        trials=1000,
        seed=42,
    )
    assert packet["status"] == "AVAILABLE"
    assert packet["expected_economics"]["actual_revenue"] is False
    assert packet["downside_simulation"]["simulation_only"] is True
    assert packet["risk_adjusted"]["execution_authority"] == "none"
    assert packet["value_of_information"]["worth_collecting"] is True
    assert packet["calibration"]["brier"]["available"] is True
    assert packet["capital_execution"] is False
