"""Shadow calibration using original canonical verification fixtures only."""
from copy import deepcopy

import pytest

from empire_os.commercial_verified_learning_review import (
    review_verified_learning_candidate,
)
from test_authenticated_commercial_outcome_intelligence import (
    original_verified_feedback, ORDER, OTHER_ORDER, TENANT, NOW,
)
from test_verified_outcome_learning_continuity import prediction as owner_prediction


def pred():
    p = owner_prediction()
    p["tenant_id"] = TENANT
    return p


def run(*, feedback=None, prediction=None):
    return review_verified_learning_candidate(
        feedback=feedback if feedback is not None else original_verified_feedback(),
        original_prediction=prediction, tenant_id=TENANT,
        exact_order_id=ORDER, now=NOW,
    )


def test_verified_financial_outcome_with_no_original_prediction_only_requests_owner():
    r = run()
    assert r["status"] == "ORIGINAL_PRE_OUTCOME_PREDICTION_REQUIRED"
    assert r["verified_terminal_outcome_count"] == 1
    assert r["recognized_revenue_cents"] == 1000
    assert r["verified_actual_cost_cents"] == 1200
    assert r["verified_gross_profit_cents"] == -200
    assert r["calibration_metric_computed"] is False
    assert r["economic_feedback_reviewable"] is True
    assert r["model_training_authorized"] is False
    assert r["payments_executed"] is False
    assert TENANT not in str(r) and ORDER not in str(r)
    assert "payment-1" not in str(r)


def test_real_original_predecision_probability_can_be_calibrated_readonly():
    f, p = original_verified_feedback(), pred()
    before = (deepcopy(f), deepcopy(p))
    r = run(feedback=f, prediction=p)
    assert (f, p) == before
    assert r["status"] == "SHADOW_METRIC_FROM_SUPPLIED_PREDICTION_ORIGIN_REVIEW_REQUIRED"
    assert r["original_prediction_independently_authenticated_by_this_review"] is False
    assert r["calibration_training_ready"] is False
    assert r["original_probability"] == 0.6
    assert r["realized_binary_outcome"] == 1
    assert r["brier_score"] == 0.16
    assert r["signed_probability_error"] == 0.4
    assert r["next_existing_owner"] == "revenue_os_calibration_and_model_review"
    assert r["commercial_bid_or_price_change_authorized"] is False


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(tenant_id=OTHER_ORDER),
    lambda p: p.update(predicted_at="2026-10-06T12:00:00+00:00"),
    lambda p: p.update(horizon_until="2026-10-02T12:00:00+00:00"),
    lambda p: p.update(prediction_ref="fake-owner-prediction"),
    lambda p: p.update(predicted_probability=1.1),
    lambda p: p.update(evidence_refs=[]),
])
def test_unbound_or_future_prediction_fails_closed(mutation):
    p = pred()
    mutation(p)
    with pytest.raises((ValueError, TypeError)):
        run(prediction=p)


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(synthetic=True),
    lambda f: f.update(actual_revenue_cents=999999),
    lambda f: f.update(fulfilment_order_id=OTHER_ORDER),
    lambda f: f.update(execution_authority="send"),
    lambda f: f.update(tenant_id=OTHER_ORDER),
])
def test_forged_outcome_not_admitted(mutation):
    f = original_verified_feedback()
    mutation(f)
    with pytest.raises(ValueError):
        run(feedback=f, prediction=pred())
