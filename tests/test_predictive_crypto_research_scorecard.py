"""Win rate versus risk and expectancy, never 99%-accuracy certification."""
import math
import pytest

from empire_os.predictive_crypto_research_scorecard import (
    review_paper_outcomes,CryptoScorecardHold,
)


def test_99_wins_one_catastrophic_loss_is_not_profitable_or_certified():
    r=review_paper_outcomes([1.]*99+[-500.])
    assert r["paper_outcome_count"]==100
    assert r["paper_positive_rate"]==.99
    assert r["paper_total_net_quote_pnl"]==-401
    assert r["paper_mean_net_quote_pnl"]<0
    assert r["paper_positive_rate_wilson_lower_95"]<.99
    assert r["paper_profit_factor"]<1
    assert r["ninety_nine_percent_accuracy_validated"] is False
    assert r["approved_signal_subscription_product"] is False


def test_wilson_bounds_and_losing_streak_no_data():
    empty=review_paper_outcomes([])
    assert empty["paper_positive_rate"] is None
    assert empty["paper_profit_factor"] is None
    r=review_paper_outcomes([2,-1,-1,-1,3,0,-5,5])
    assert r["paper_longest_losing_streak"]==3
    assert r["paper_max_quote_drawdown"]>0
    assert 0<r["paper_positive_rate_wilson_lower_95"]<r["paper_positive_rate"]


def test_100_percent_in_20_observations_cannot_certify_99_percent():
    r=review_paper_outcomes([5.]*20)
    assert r["paper_positive_rate"]==1
    assert r["paper_positive_rate_wilson_lower_95"]<.99
    assert r["paper_outcomes_authenticated_from_exchange"] is False
    assert r["multiple_strategy_tests_adjusted"] is False
    assert r["ninety_nine_percent_accuracy_validated"] is False


@pytest.mark.parametrize("bad",[[float("nan")],[float("inf")],[True],[None],[10**12]])
def test_forged_results_fail_closed(bad):
    with pytest.raises(CryptoScorecardHold):
        review_paper_outcomes(bad)
