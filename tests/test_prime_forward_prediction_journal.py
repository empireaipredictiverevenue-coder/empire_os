"""Offline original-owner journal and Quant/economic shadow regressions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from empire_os.prime_forward_prediction_journal import (
    review_prime_forward_journal, summarize_prime_forward_founder,
)
from test_authenticated_commercial_outcome_intelligence import (
    original_verified_feedback, NOW, TENANT, ORDER,
)
from test_verified_outcome_learning_continuity import prediction as original_prediction


def owner_row():
    p = original_prediction()
    p["tenant_id"] = TENANT
    return {
        "exact_order_id": ORDER,
        "feedback": original_verified_feedback(),
        "original_prediction": p,
    }


def forecast(row=None, **changes):
    p = (row or owner_row())["original_prediction"]
    f = {
        "tenant_id": TENANT,
        "prediction_ref": p["prediction_ref"],
        "opportunity_key": p["opportunity_key"],
        "prediction_type": p["prediction_type"],
        "predicted_probability": p["predicted_probability"],
        "predicted_at": p["predicted_at"],
        "journal_recorded_at": "2026-10-01T12:05:00+00:00",
        "horizon_until": p["horizon_until"],
        "last_feature_observed_at": "2026-10-01T11:59:59+00:00",
        "feature_lineage_sha256": sha256(b"original-opaque-fixture-features").hexdigest(),
        "model_version_sha256": sha256(b"model-v1").hexdigest(),
        "decision_policy_sha256": sha256(b"policy-v1").hexdigest(),
        "research_decision": "PREDICT_POSITIVE",
    }
    f.update(changes)
    return f


def review(rows=None, outcomes=None, as_of=NOW):
    return review_prime_forward_journal(
        tenant_id=TENANT, as_of=as_of,
        original_predictions=rows, owner_outcome_rows=outcomes,
    )


def test_unknown_inputs_never_promote_real_accuracy_or_economic_results():
    r = review()
    assert r["journal_input_count"] is None
    assert r["matched_original_owner_review_count"] is None
    assert r["verified_total_economic_value_cents"] is None
    assert r["recognised_revenue_verified_by_this_module"] is False
    assert r["original_prediction_registry_authenticity_verified"] is False
    assert "NO_PREDECLARED_JOURNAL_INPUT_NOT_VERIFIED_ZERO" in r["blockers"]
    founder = summarize_prime_forward_founder(r)
    assert founder["journal_record_count_band"] is None
    assert founder["shadow_brier"] is None
    assert founder["true_economic_value_verified"] is False


def test_predeclared_fixture_prediction_matches_original_calibration_and_quant():
    r = review([forecast()], [owner_row()])
    assert r["journal_input_count"] == 1
    assert r["matched_original_owner_review_count"] == 1
    assert r["shadow_quant_prediction_quality"]["brier_score"] == 0.16
    assert r["shadow_quant_prediction_quality"]["true_positive"] == 1
    assert r["research_action_confusion_counts"]["true_positive"] == 1
    assert r["owner_reviewed_financial_wins_with_cost_count"] == 1
    assert r["partial_owner_supplied_gross_profit_cents"] == -200
    assert r["verified_total_economic_value_cents"] is None
    assert r["production_accuracy_verified"] is False
    assert r["empiredb_written"] is False
    assert r["execution_authority"] == "none"
    output = summarize_prime_forward_founder(r)
    assert output["paired_terminal_review_count_band"] == "0-4"
    assert output["shadow_accuracy"] is None
    assert output["owner_claimed_gross_profit_cents"] is None
    assert TENANT not in str(output) and ORDER not in str(output)


def test_missing_outcome_does_not_become_automatic_failure_or_success():
    row = forecast()
    r = review([row], [])
    assert r["matched_original_owner_review_count"] == 0
    assert r["unresolved_prediction_count"] == 1
    assert r["matured_unknown_outcome_count"] == 0
    assert r["shadow_quant_prediction_quality"] is None
    as_of = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    later = review([row], [], as_of=as_of)
    assert later["matured_unknown_outcome_count"] == 1
    assert "MATURED_PREDICTIONS_WITH_UNKNOWN_OUTCOMES" in later["blockers"]


def test_negative_and_abstain_records_preserved_separately():
    positive = forecast()
    negative = forecast(
        prediction_ref="original:negative", opportunity_key="buyer:negative",
        predicted_probability=0.2, research_decision="PREDICT_NEGATIVE",
    )
    abstain = forecast(
        prediction_ref="original:abstain", opportunity_key="buyer:abstain",
        predicted_probability=0.8, research_decision="ABSTAIN",
    )
    result = review([positive, negative, abstain], [])
    assert result["journal_input_count"] == 3
    assert result["negative_research_decision_count"] == 1
    assert result["abstained_research_decision_count"] == 1
    assert result["unresolved_prediction_count"] == 3
    assert result["unmatched_predictions_not_assumed_losses"] is True
    assert result["verified_economic_roi"] is None


@pytest.mark.parametrize("changes,reason", [
    ({"predicted_probability": 1.1}, "bounded_finite"),
    ({"predicted_probability": float("nan")}, "bounded_finite"),
    ({"predicted_probability": True}, "bounded_finite"),
    ({"feature_lineage_sha256": "raw-private@test.com"}, "feature_lineage_sha256"),
    ({"model_version_sha256": "model-not-pinned"}, "model_version_sha256"),
    ({"decision_policy_sha256": "policy-not-pinned"}, "decision_policy_sha256"),
    ({"journal_recorded_at": "2026-10-09T12:00:00Z"}, "future_leakage"),
    ({"last_feature_observed_at": "2026-10-02T12:00:00Z"}, "future_leakage"),
    ({"horizon_until": "2026-10-01T12:01:00Z"}, "future_leakage"),
    ({"prediction_type": "TRADING"}, "separate_trading"),
    ({"predicted_probability": 0.2}, "classification_policy"),
    ({"research_decision": "BUY_AND_TRADE"}, "unknown_original"),
])
def test_bad_predecision_probabilities_and_time_leakage_fail(changes, reason):
    with pytest.raises(ValueError, match=reason):
        review([forecast(**changes)], [])


def test_unknown_field_cannot_add_financial_authority():
    row = forecast()
    row["auto_trade"] = True
    with pytest.raises(ValueError, match="exact_original"):
        review([row], [])


def test_original_outcome_cannot_backfill_missing_journal():
    with pytest.raises(ValueError, match="backfill"):
        review(None, [owner_row()])
    with pytest.raises(ValueError, match="not_in_predeclared"):
        review([forecast(prediction_ref="wrong")], [owner_row()])


def test_changed_prediction_probability_is_rejected_even_with_original_owner_feedback():
    with pytest.raises(ValueError, match="predeclared_probability"):
        review([forecast(predicted_probability=0.7)], [owner_row()])


def test_original_predicted_and_outcome_time_identity_required():
    row = owner_row()
    row["original_prediction"]["predicted_at"] = "2026-10-01T13:00:00Z"
    with pytest.raises(ValueError, match="predeclared_journal"):
        review([forecast()], [row])
    row = owner_row()
    with pytest.raises(ValueError, match="noncausal"):
        review([forecast(journal_recorded_at="2026-10-05T11:00:00Z")], [row])


def test_tampered_canonical_outcome_and_cross_tenant_rejected():
    altered = owner_row()
    altered["feedback"]["actual_revenue_cents"] = 999999
    with pytest.raises(ValueError):
        review([forecast()], [altered])
    with pytest.raises(ValueError, match="cross_tenant"):
        review([forecast(tenant_id="other-tenant")], [])


def test_duplicate_original_forecast_and_entity_opportunity_refused():
    with pytest.raises(ValueError, match="duplicate_prediction"):
        review([forecast(), forecast()], [])
    with pytest.raises(ValueError, match="duplicate_prediction"):
        review([forecast(), forecast(prediction_ref="other")], [])


def test_duplicate_outcome_is_rejected_and_no_revenue_laundering():
    with pytest.raises(ValueError):
        review([forecast()], [owner_row(), owner_row()])


def test_only_real_original_verified_contract_can_supply_terminal_label():
    row = owner_row()
    row["feedback"]["verified_label"] = 0
    with pytest.raises(ValueError):
        review([forecast()], [row])


def test_caller_cannot_invent_financial_fields_or_change_any_inputs():
    p, f = forecast(), owner_row()
    inputs = deepcopy(([p], [f]))
    review([p], [f])
    assert ([p], [f]) == inputs
    report = summarize_prime_forward_founder(review([p], [f]))
    assert report["owner_claimed_gross_profit_cents"] is None
    assert "prediction_ref" not in str(report)


def test_original_predictive_cloud_bridge_composes_forward_journal_without_leaking_details():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    r = build_predictive_revenue_brain_review(
        tenant_id=TENANT, as_of=NOW,
        original_forward_journal_predictions=[forecast()],
        original_forward_journal_owner_outcomes=[owner_row()],
    )
    public = r["prime_forward_prediction_journal_shadow"]
    assert public["journal_record_count_band"] == "0-4"
    assert public["paired_terminal_review_count_band"] == "0-4"
    assert public["shadow_accuracy"] is None
    assert public["shadow_brier"] is None
    assert public["true_economic_value_verified"] is False
    assert r["original_outcome_calibration_shadow"]["shadow_prediction_pair_count"] is None
    assert r["astra_dispatch_executed"] is False
    assert r["forecast_model_promoted"] is False
    assert r["outbound_sent"] is False
    assert TENANT not in str(public)
    assert ORDER not in str(public)


def test_original_bridge_rejects_owner_outcome_without_preregistered_journal():
    from empire_os.predictive_revenue_brain_bridge import build_predictive_revenue_brain_review
    with pytest.raises(ValueError, match="backfill"):
        build_predictive_revenue_brain_review(
            tenant_id=TENANT, as_of=NOW,
            original_forward_journal_owner_outcomes=[owner_row()],
        )
