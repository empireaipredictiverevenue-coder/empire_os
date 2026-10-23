from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_revenue_prime import (
    review_churn_signals,
    simulate_pipeline_scenarios,
)
from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review

NOW = datetime(2026, 10, 23, 18, tzinfo=timezone.utc)
TENANT = "tenant-1"


def deal(**updates):
    value = {
        "tenant_id": TENANT, "deal_id": "d1", "stage": "PROPOSAL",
        "currency": "GBP", "value_cents": 10001,
        "win_probability_basis_points": 5000, "evidence_refs": ["crm:1"],
        "probability_evidence_refs": ["forecast:cohort"],
        "updated_at": NOW.isoformat(), "cycle_days": 14,
    }
    value.update(updates)
    return value


def sim(*deals, **kwargs):
    return simulate_pipeline_scenarios(
        tenant_id=TENANT, as_of=NOW, open_deals=list(deals),
        simulations=1000, seed=2026, **kwargs,
    )


def test_scenario_replay_is_stable_bounded_and_not_revenue():
    first = sim(deal())
    second = sim(deal())
    assert first == second
    row = first["currency_scenarios"][0]
    assert row["p10_contract_cents"] <= row["p50_contract_cents"] <= row["p90_contract_cents"]
    assert row["p10_contract_cents"] == 0
    assert row["p90_contract_cents"] == 10001
    assert row["cash_receipts_forecast"] is False
    assert row["recognized_revenue_forecast"] is False
    assert row["inputs_independently_calibrated"] is False
    assert row["distribution_assumes_independent_deal_wins"] is True
    assert first["model_promoted"] is False


def test_simulation_deterministic_independent_of_deal_order():
    d1 = deal(deal_id="a", value_cents=125, win_probability_basis_points=3000)
    d2 = deal(deal_id="b", value_cents=730, win_probability_basis_points=7000)
    assert sim(d1, d2) == sim(d2, d1)


def test_probability_zero_and_certain_are_exact():
    row = sim(
        deal(deal_id="never", value_cents=999, win_probability_basis_points=0),
        deal(deal_id="always", value_cents=1001, win_probability_basis_points=10000),
    )["currency_scenarios"][0]
    assert row["p10_contract_cents"] == row["p50_contract_cents"] == row["p90_contract_cents"] == 1001


def test_simulation_keeps_currencies_separate():
    rows = sim(deal(), deal(deal_id="usd", currency="USD"))["currency_scenarios"]
    assert [r["currency"] for r in rows] == ["GBP", "USD"]


@pytest.mark.parametrize("changed", [
    {"tenant_id": "alien"}, {"value_cents": 1.5},
    {"value_cents": -5}, {"win_probability_basis_points": None},
    {"win_probability_basis_points": 11000},
    {"probability_evidence_refs": []},
    {"evidence_refs": []}, {"stage": "CLOSED_WON"},
    {"updated_at": NOW + timedelta(seconds=1)},
])
def test_invalid_simulation_inputs_fail_closed(changed):
    with pytest.raises(ValueError):
        sim(deal(**changed))


def test_duplicate_simulation_ids_fail_closed():
    with pytest.raises(ValueError):
        sim(deal(), deal())


def test_simulation_size_and_seed_are_bounded():
    with pytest.raises(ValueError):
        simulate_pipeline_scenarios(
            tenant_id=TENANT, as_of=NOW, open_deals=[deal()],
            simulations=1,
        )
    with pytest.raises(ValueError):
        simulate_pipeline_scenarios(
            tenant_id=TENANT, as_of=NOW, open_deals=[deal()],
            simulations=1000, seed=-1,
        )


def signal(**updates):
    base = {
        "tenant_id": TENANT, "signal_id": "churn-s1",
        "account_id": "acct-1", "signal_type": "usage_decline",
        "observed_at": NOW.isoformat(), "evidence_refs": ["usage:s1"],
        "email_address": "do-not-include@example.test",
        "claimed_churn_probability": 0.95,
        "outbound_allowed": True,
    }
    base.update(updates)
    return base


def review(*rows):
    return review_churn_signals(tenant_id=TENANT, as_of=NOW, signals=list(rows))


def test_churn_is_review_only_and_does_not_leak_email():
    result = review(signal())
    assert result["automatic_winback_disabled"] is True
    assert result["estimated_churn_probability"] is None
    assert result["review_count"] == 1
    row = result["reviews"][0]
    assert row["churn_probability"] is None
    assert row["outbound_allowed"] is False
    assert row["intervention_sent"] is False
    assert row["suppression_checked"] is False
    assert row["review_action"] == "FOUNDER_RETENTION_REVIEW"
    assert "do-not-include" not in str(result)


@pytest.mark.parametrize("changed", [
    {"tenant_id": "alien"}, {"evidence_refs": []},
    {"signal_type": "prediction_with_95_percent_certainty"},
    {"observed_at": NOW + timedelta(seconds=1)},
])
def test_churn_fails_closed(changed):
    with pytest.raises(ValueError):
        review(signal(**changed))


def test_churn_duplicate_id_fails_closed():
    with pytest.raises(ValueError):
        review(signal(), signal())


def test_prime_attached_to_existing_jev_bridge_as_opt_in():
    result = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        crm_deals=[deal()],
        churn_signals=[signal()],
        simulate_pipeline=True, simulations=1000,
    )
    assert result["prime_scenarios"]["currency_scenarios"][0]["simulations_run"] == 1000
    assert result["prime_churn_review"]["review_count"] == 1
    assert result["prime_interventions_executed"] is False
    assert result["recognized_revenue_cents"] is None
    assert result["revenue_verified"] is False
    assert result["execution_authority"] == "none"


def test_no_prime_simulation_without_explicit_opt_in():
    result = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW, crm_deals=[deal()]
    )
    assert result["prime_scenarios"] is None
    assert result["prime_churn_review"]["review_count"] == 0


def test_prime_simulation_requires_all_probabilities_if_requested():
    with pytest.raises(ValueError):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            crm_deals=[deal(win_probability_basis_points=None)],
            simulate_pipeline=True, simulations=1000,
        )


def test_closed_won_not_in_simulation_but_not_recognized_revenue():
    result = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        crm_deals=[
            deal(deal_id="open"),
            deal(deal_id="won", stage="CLOSED_WON", value_cents=500_000),
        ],
        simulate_pipeline=True, simulations=1000,
    )
    assert result["prime_scenarios"]["currency_scenarios"][0]["open_deal_count"] == 1
    assert result["crm_pipeline"]["currency_groups"][0]["closed_won_contract_cents"] == 500_000
    assert result["recognized_revenue_cents"] is None
