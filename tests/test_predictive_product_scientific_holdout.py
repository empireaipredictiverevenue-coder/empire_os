"""Local synthetic test fixtures: never authentic external customer evidence."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.predictive_calibration import review_commercial_prediction
from empire_os.predictive_product_scientific_holdout import (
    evaluate_product_scientific_holdout, ProductScienceHold, MIN_HISTORY,
)

TENANT = "fixture-tenant"
PRODUCT = "forecast_pro"
PID = "fixture-product-id"
NOW = datetime(2026, 10, 20, 17, tzinfo=timezone.utc)
START = datetime(2026, 8, 1, tzinfo=timezone.utc)
CATALOG = {"products": [
    {"product_id": PID, "product_code": PRODUCT,
     "catalog_state": "VERIFIED", "version_state": "VERIFIED"},
]}
# All typed historical feedback is local synthetic test data despite the
# flags satisfying the validated-feedback contract. It proves no issuer.


def packet(i, *, tenant=TENANT, product=PID, won=None, probability=0.35):
    issued = START + timedelta(days=i)
    outcome_time = issued + timedelta(days=1)
    actual_time = issued + timedelta(days=2)
    horizon = issued + timedelta(days=5)
    success = (i % 3 == 0) if won is None else won
    key = f"fixture-opportunity-{i}"
    pred_ref = f"fixture-prediction-{i}"
    outcome_ref = f"canonical:commercial_outcomes:fixture-{i}"
    order = f"fixture-order-{i}"
    label = int(success)
    references = [outcome_ref, f"canonical:synthetic-fixture-{i}"]
    feedback = {
        "schema_version": "empire.verified_outcome_feedback.v1",
        "tenant_id": tenant,
        "product_id": product,
        "outcome_ref": outcome_ref,
        "fulfilment_order_id": order,
        "opportunity_key": key,
        "prediction_ref": pred_ref,
        "decision_ref": None,
        "execution_ref": None,
        "conversion_outcome": "won" if success else "lost",
        "verified_label": label,
        "verified_outcome": True,
        "synthetic": False,  # deliberately forged in local tests
        "actual_revenue": success,
        "actual_revenue_cents": 100 if success else None,
        "actual_cost_cents": 20 if success else None,
        "gross_profit_cents": 80 if success else None,
        "outcome_recorded_at": outcome_time.isoformat(),
        "available_at": actual_time.isoformat(),
        "evidence_refs": references,
        "causal_lineage": None,
        "shadow_only": True,
        "execution_authority": "none",
        "cortex_packet": {
            "tenant_id": tenant,
            "label": {
                "available": True, "synthetic": False,
                "forecast_derived": False, "value": label,
                "outcome_ref": outcome_ref,
            },
            "verification": {
                "payment_verified": success,
                "fulfilment_verified": success,
                "recognized_revenue": success,
                "actual_revenue_cents": 100 if success else None,
                "actual_cost_cents": 20 if success else None,
                "gross_profit_cents": 80 if success else None,
                "outcome_recorded_at": outcome_time.isoformat(),
                "available_at": actual_time.isoformat(),
            },
            "learning_lineage": {
                "tenant_id": tenant, "opportunity_key": key,
                "prediction_ref": pred_ref, "decision_ref": None,
                "execution_ref": None, "outcome_ref": outcome_ref,
            },
        },
    }
    prediction = {
        "tenant_id": tenant,
        "opportunity_key": key,
        "prediction_ref": pred_ref,
        "prediction_type": "conversion_probability",
        "predicted_at": issued.isoformat(),
        "horizon_until": horizon.isoformat(),
        "predicted_probability": probability,
        "evidence_refs": [f"forecast:fixture-{i}"],
    }
    return review_commercial_prediction(
        prediction=prediction, feedback=feedback, tenant_id=tenant, as_of=NOW
    )


def evaluate(rows, *, catalog=CATALOG, tenant=TENANT):
    return evaluate_product_scientific_holdout(
        tenant_id=tenant, product_code=PRODUCT,
        calibration_packets=rows, catalog=catalog, as_of=NOW)


def test_no_real_outcomes_is_unknown_not_zero_or_revenue():
    r = evaluate([])
    assert r["status"] == "PRODUCT_HOLDOUT_INSUFFICIENT_ORIGINAL_EVIDENCE"
    assert r["model_brier"] is None
    assert r["out_of_sample_evaluation_count"] == 0
    assert r["forecast_eligible_for_customer"] is False


def test_predictive_science_computes_genuine_math_on_untrusted_fixture_only():
    rows = [packet(i) for i in range(44)]
    output = evaluate(rows[::-1])
    assert output["status"] == "SUPPLIED_PACKET_STATISTICS_ONLY_ORIGINAL_REGISTRY_HOLD"
    assert output["submitted_calibration_count"] == 44
    assert output["out_of_sample_evaluation_count"] >= 12
    assert output["historical_baseline_period_count"] >= MIN_HISTORY
    assert 0 <= output["model_brier"] <= 1
    assert 0 <= output["historical_baseline_brier"] <= 1
    assert 0 <= output["calibration_gap"] <= 1
    assert 0 <= output["observed_rate_wilson_95"]["low"] <= output["observed_rate_wilson_95"]["high"] <= 1
    assert output["original_registry_readback_authenticated"] is False
    assert output["model_production_skill_proven"] is False
    assert output["economic_memory_update_eligible"] is False
    assert output["realized_revenue_verified_by_this_review"] is False
    assert output["execution_authority"] == "none"
    assert TENANT not in json.dumps(output)
    assert "fixture-order-" not in json.dumps(output)
    assert "fixture-opportunity-" not in json.dumps(output)


def test_sample_order_changes_no_metrics():
    rows = [packet(i) for i in range(44)]
    a, b = evaluate(rows), evaluate(rows[::-1])
    assert a == b


def test_leakage_prevention_if_outcomes_not_available_before_next_forecast():
    rows = [packet(i) for i in range(44)]
    for i, r in enumerate(rows):
        # all forecast timestamps are August/September; source is finalized
        # just before NOW, so no prior outcome existed when predictions issued
        later = datetime(2026, 10, 18, tzinfo=timezone.utc).isoformat()
        r["feedback"]["available_at"] = later
        r["feedback"]["cortex_packet"]["verification"]["available_at"] = later
        # This contradicts the forecast horizon and must be held, not
        # accepted as hindsight-informed pre-forecast evidence.
    with pytest.raises(ProductScienceHold):
        evaluate(rows)


@pytest.mark.parametrize("mutator", [
    lambda r: r[0].update(tenant_id="other-tenant"),
    lambda r: r[0].update(actual_value=2),
    lambda r: r[0].update(calibration_ready=False),
    lambda r: r[0].update(shadow_only=False),
    lambda r: r[0].update(promoted_learning=True),
    lambda r: r[0].update(model_weight_mutation=True),
    lambda r: r[0].update(predicted_value=0.99),
    lambda r: r[0]["feedback"].update(product_id="other-product"),
    lambda r: r[0]["feedback"].update(tenant_id="other-tenant"),
    lambda r: r[0]["feedback"].update(synthetic=True),
    lambda r: r[0]["feedback"]["cortex_packet"]["label"].update(forecast_derived=True),
    lambda r: r[0]["prediction"].update(predicted_at="2026-10-21T00:00:00Z"),
    lambda r: r[0]["feedback"].update(fulfilment_order_id=""),
])
def test_all_lying_or_cross_tenant_packet_evidence_holds(mutator):
    rows = [packet(i) for i in range(44)]
    mutator(rows)
    with pytest.raises(ProductScienceHold):
        evaluate(rows)


def test_duplicate_outcome_and_order_and_prediction_refuse():
    rows = [packet(i) for i in range(44)]
    rows[1] = deepcopy(rows[0])
    with pytest.raises(ProductScienceHold, match="duplicate"):
        evaluate(rows)


def test_unknown_catalogue_version_must_not_be_calibrated():
    altered = deepcopy(CATALOG)
    altered["products"][0]["version_state"] = "PENDING"
    out = evaluate([packet(i) for i in range(44)], catalog=altered)
    assert out["model_brier"] is None
    assert out["forecast_eligible_for_customer"] is False


def test_empty_tenant_or_naive_asof_refused():
    with pytest.raises(ProductScienceHold):
        evaluate([packet(i) for i in range(44)], tenant="")
    with pytest.raises(ProductScienceHold):
        evaluate_product_scientific_holdout(
            tenant_id=TENANT, product_code=PRODUCT, calibration_packets=[],
            catalog=CATALOG, as_of=datetime(2026, 10, 20)
        )


def test_no_forged_customer_claim_from_perfect_synthetic_predictions():
    rows = [packet(i, probability=1.0 if i % 3 == 0 else 0.0) for i in range(44)]
    output = evaluate(rows)
    assert output["model_brier"] == 0
    assert output["skill_vs_past_only_baseline"] is not None
    assert output["model_production_skill_proven"] is False
    assert output["forecast_eligible_for_customer"] is False
