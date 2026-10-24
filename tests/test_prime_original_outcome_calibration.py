"""Original prediction/outcome matching -> PRIME shadow metrics, no promotion."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.prime_original_outcome_calibration import (
    review_prime_outcome_calibration, MAX_OUTCOME_REVIEWS,
)
from empire_os.predictive_revenue_brain_bridge import (
    build_predictive_revenue_brain_review,
)
from empire_os.predictive_revenue_prime_status import read_prime_founder_status
from test_authenticated_commercial_outcome_intelligence import (
    original_verified_feedback, ORDER, OTHER_ORDER, TENANT, NOW,
)
from test_verified_outcome_learning_continuity import prediction as baseline_prediction


def valid_row():
    original = baseline_prediction()
    original["tenant_id"] = TENANT
    return {
        "exact_order_id": ORDER,
        "feedback": original_verified_feedback(),
        "original_prediction": original,
    }


def shadow(rows=None, tenant=TENANT):
    return review_prime_outcome_calibration(
        owner_outcome_rows=rows, tenant_id=tenant, as_of=NOW,
    )


def test_unknown_is_not_an_observed_zero_or_auto_training():
    out = shadow()
    assert out["status"] == "NOT_CONNECTED_NOT_A_VERIFIED_ZERO"
    assert out["shadow_prediction_pair_count"] is None
    assert out["shadow_brier_score"] is None
    assert out["beta_posterior_promoted"] is False
    assert out["model_weights_modified"] is False
    assert out["training_authorized"] is False
    assert out["execution_authority"] == "none"


def test_explicit_empty_owner_input_is_not_verified_platform_zero():
    out = shadow([])
    assert out["status"] == "OWNER_INPUT_EMPTY_NOT_PROOF_OF_ZERO_OUTCOMES"
    assert out["owner_input_count"] == 0
    assert out["shadow_prediction_pair_count"] == 0
    assert out["source_owner_authenticated_by_this_module"] is False
    assert out["shadow_brier_score"] is None


def test_one_original_verified_learning_fixture_yields_shadow_score_only():
    row = valid_row()
    before = deepcopy(row)
    out = shadow([row])
    assert row == before
    assert out["status"] == "SHADOW_COHORT_INSUFFICIENT_UNPROMOTED"
    assert out["owner_reviewed_terminal_outcome_count"] == 1
    assert out["observed_outcome_wins_in_owner_supplied_samples"] == 1
    assert out["shadow_prediction_pair_count"] == 1
    assert out["shadow_brier_score"] == 0.16
    assert out["shadow_signed_probability_bias"] == 0.4
    assert out["calibration_cohort_sufficient"] is False
    assert out["original_prediction_provenance_independently_verified"] is False
    assert out["cash_receipts_or_revenue_verified_by_this_module"] is False
    assert out["prime_forecasts_promoted"] is False
    assert out["database_writes"] is False
    assert out["outbound_sent"] is False
    assert out["payments_made"] is False
    assert ORDER not in str(out) and TENANT not in str(out)


def test_missing_original_prediction_preserves_unknown_score():
    row = valid_row()
    row["original_prediction"] = None
    out = shadow([row])
    assert out["owner_reviewed_terminal_outcome_count"] == 1
    assert out["unpaired_outcome_count"] == 1
    assert out["shadow_prediction_pair_count"] == 0
    assert out["shadow_brier_score"] is None
    assert out["training_authorized"] is False


def test_original_prediction_cannot_be_cloned_to_count_as_more_outcomes():
    with pytest.raises(ValueError, match="duplicate"):
        shadow([valid_row(), valid_row()])


def test_hypothetical_or_unauthenticated_financial_labels_cannot_enter():
    for bad in ("synthetic", "verified_outcome", "actual_revenue_cents"):
        row = valid_row()
        row["feedback"][bad] = (
            True if bad == "synthetic" else
            False if bad == "verified_outcome" else 1234567
        )
        with pytest.raises(ValueError):
            shadow([row])


def test_order_and_tenant_cannot_be_cross_bound():
    row = valid_row()
    row["exact_order_id"] = OTHER_ORDER
    with pytest.raises(ValueError):
        shadow([row])
    with pytest.raises(ValueError):
        shadow([valid_row()], tenant=OTHER_ORDER)


def test_future_or_unbound_prediction_rejected():
    row = valid_row()
    row["original_prediction"]["prediction_ref"] = "fake-old-ref"
    with pytest.raises(ValueError):
        shadow([row])
    row = valid_row()
    row["original_prediction"]["predicted_at"] = "2026-10-30T12:00:00Z"
    with pytest.raises((TypeError, ValueError)):
        shadow([row])


def test_unknown_fields_can_never_claim_model_training_or_revenue():
    row = valid_row()
    row["model_training_authorized"] = True
    with pytest.raises(ValueError, match="exact"):
        shadow([row])
    row = valid_row()
    row["paid_revenue"] = 100000
    with pytest.raises(ValueError, match="exact"):
        shadow([row])


def test_outcome_cohort_has_bounded_size_and_aware_clock():
    with pytest.raises(ValueError, match="bounded"):
        shadow([valid_row()] * (MAX_OUTCOME_REVIEWS + 1))
    with pytest.raises(ValueError, match="aware"):
        review_prime_outcome_calibration(
            owner_outcome_rows=None, tenant_id=TENANT,
            as_of=datetime(2026, 10, 24),
        )


def test_prior_official_source_does_not_turn_into_outcome_calibration():
    r = build_predictive_revenue_brain_review(
        tenant_id="empire-internal",
        as_of=NOW, original_owner_calibration_rows=None,
    )
    assert r["original_outcome_calibration_shadow"]["shadow_brier_score"] is None
    assert r["original_outcome_calibration_shadow"]["status"] == (
        "NOT_CONNECTED_NOT_A_VERIFIED_ZERO"
    )
    assert r["prime_scenarios"] is None
    assert r["recognized_revenue_cents"] is None
    assert r["prime_calibration_never_promotes_model_weights"] is True


def test_optional_owner_calibration_reaches_existing_brain_but_no_execution():
    r = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        original_owner_calibration_rows=[valid_row()],
    )
    x = r["original_outcome_calibration_shadow"]
    assert x["shadow_brier_score"] == 0.16
    assert r["revenue_verified"] is False
    assert r["recognized_revenue_cents"] is None
    assert r["opportunity_count"] == 0
    assert r["astra_dispatch_executed"] is False
    assert r["database_writes"] is False


def test_founder_status_shows_only_aggregate_shadow_stats(tmp_path):
    r = read_prime_founder_status(
        repo_root=tmp_path, tenant_id=TENANT,
        as_of=NOW, original_owner_calibration_rows=[valid_row()],
    )
    assert r["original_outcome_calibration_status"] == "SHADOW_COHORT_INSUFFICIENT_UNPROMOTED"
    assert r["original_outcome_shadow_pair_count"] == 1
    assert r["original_outcome_shadow_brier_score"] == 0.16
    assert r["original_outcome_calibration_training_authorized"] is False
    assert "tenant_id" not in str(r)
    assert ORDER not in str(r) and TENANT not in str(r)
    assert r["realized_revenue_cents"] is None


def test_invalid_owner_feedback_fails_closed_on_founder_status(tmp_path):
    row = valid_row()
    row["feedback"]["synthetic"] = True
    r = read_prime_founder_status(
        repo_root=tmp_path, tenant_id=TENANT, as_of=NOW,
        original_owner_calibration_rows=[row],
    )
    assert r["status"] == "READ_ONLY_SOURCE_REVIEW_UNAVAILABLE"
    assert r["original_outcome_shadow_pair_count"] is None
    assert r["realized_revenue_cents"] is None


@pytest.mark.parametrize("broken_probability", [float("nan"), float("inf"), -0.1, 1.1])
def test_nonfinite_or_out_of_range_probability_cannot_enter_shadow_score(
    broken_probability,
):
    row = valid_row()
    row["original_prediction"]["predicted_probability"] = broken_probability
    with pytest.raises(ValueError):
        shadow([row])
