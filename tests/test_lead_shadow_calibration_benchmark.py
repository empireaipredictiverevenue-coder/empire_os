"""Scientific lead benchmark: provenance, chronology and no authority bypass."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.lead_shadow_calibration_benchmark import evaluate_shadow_calibration
from test_verified_outcome_learning_continuity import memory, feedback, prediction, TENANT

AS_OF = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


def test_no_outcome_history_reports_insufficient_evidence():
    empty = {
        "schema_version": "empire.economic_memory.v1", "mode": "OBSERVE",
        "execution_authority": "none", "promoted_learning": False,
        "tenant_id": None, "calibration_evidence": [], "verified_learning_feedback": [],
    }
    result = evaluate_shadow_calibration(empty, tenant_id=None, as_of=AS_OF)
    assert result["verified_review_count"] == 0
    assert result["candidate_brier"] is None
    assert result["candidate_beats_baseline"] is None
    assert not result["evaluation_ready"]
    assert not result["model_weight_mutation"]


def test_one_canonical_calibration_is_insufficient_for_learning():
    result = evaluate_shadow_calibration(memory(), tenant_id=TENANT, as_of=AS_OF)
    assert result["verified_review_count"] == 1
    assert result["temporal_holdout_count"] == 0
    assert result["candidate_beats_baseline"] is None
    assert result["training_performed"] is False


def test_tampered_outcome_or_prediction_is_rejected():
    tampered = deepcopy(memory())
    tampered["calibration_evidence"][0]["predicted_value"] = 0.99
    with pytest.raises(ValueError, match="tampered"):
        evaluate_shadow_calibration(tampered, tenant_id=TENANT, as_of=AS_OF)


def test_duplicate_reviews_are_rejected():
    duplicated = deepcopy(memory())
    duplicated["calibration_evidence"].append(deepcopy(duplicated["calibration_evidence"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_shadow_calibration(duplicated, tenant_id=TENANT, as_of=AS_OF)


def test_cross_tenant_and_future_outcomes_are_rejected():
    with pytest.raises(ValueError, match="tenant"):
        evaluate_shadow_calibration(memory(), tenant_id="other-tenant", as_of=AS_OF)
    with pytest.raises(ValueError):
        evaluate_shadow_calibration(memory(), tenant_id=TENANT,
                                    as_of=datetime(2026, 10, 3, tzinfo=timezone.utc))


def test_untrusted_memory_mode_rejected():
    data = deepcopy(memory())
    data["mode"] = "EXECUTE"
    with pytest.raises(ValueError, match="unsafe"):
        evaluate_shadow_calibration(data, tenant_id=TENANT, as_of=AS_OF)


def test_time_safe_baseline_never_sees_future_outcomes(monkeypatch):
    # Only the source-validation function is replaced for this isolated time-split test.
    # Separate tests above exercise the real canonical reviewer.
    from empire_os import lead_shadow_calibration_benchmark as target
    baseline = deepcopy(memory()["calibration_evidence"][0])
    cases = []
    from datetime import timedelta
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # Two early observations available before the third prediction.
    for i in range(5):
        item = deepcopy(baseline)
        predicted = start + timedelta(days=3*i)
        actual = predicted + timedelta(days=2)
        item.update(prediction_ref=f"pred-{i}", opportunity_key=f"op-{i}",
                    outcome_ref=f"out-{i}", predicted_at=predicted.isoformat(),
                    actual_at=actual.isoformat(), actual_value=i%2,
                    predicted_value=0.8, brier_score=round((0.8-i%2)**2, 6))
        item["feedback"]["outcome_ref"] = f"out-{i}"
        cases.append(item)
    mock_memory = dict(deepcopy(memory()),calibration_evidence=cases,
                       verified_learning_feedback=[case["feedback"] for case in cases])
    # Isolate the chronology algorithm; these artificial row clones are NOT
    # eligible for canonical provenance validation or actual learning.
    monkeypatch.setattr(target, "validate_verified_feedback", lambda *args, **kwargs: None)
    monkeypatch.setattr(target, "review_commercial_prediction", lambda *, prediction, feedback, tenant_id, as_of:
                        next(case for case in cases if case["feedback"] is feedback))
    result=target.evaluate_shadow_calibration(mock_memory,tenant_id=TENANT,
              as_of=datetime(2026,7,1,tzinfo=timezone.utc),min_history=2,min_evaluations=2)
    assert result["verified_review_count"]==5
    assert result["temporal_holdout_count"]==3
    assert result["candidate_brier"] is not None
    assert result["historical_baseline_brier"] is not None
    assert result["evaluation_ready"] is True
    assert result["promoted_learning"] is False


def test_canonical_verified_feedback_refresh_opt_in_writes_shadow(tmp_path):
    import json
    from empire_os.economic_memory import refresh_economic_memory_snapshot

    class VerifiedReadRepository:
        def verified_outcome_feedback(self, order_id, *, tenant_id, repo_root, as_of):
            assert order_id == "order-1" and tenant_id == TENANT
            return feedback()

    p = prediction()
    m = refresh_economic_memory_snapshot(
        tmp_path, repository=VerifiedReadRepository(),
        fulfilment_order_ids=["order-1"], tenant_id=TENANT,
        original_predictions={p["prediction_ref"]: p}, as_of=AS_OF,
        shadow_calibration=True,
    )
    source = tmp_path / "runtime/economic_memory/latest.json"
    output = tmp_path / "runtime/lead_intelligence_calibration/shadow_latest.json"
    assert source.exists() and output.exists()
    result = json.loads(output.read_text())
    assert m["calibration_evidence_count"] == 1
    assert result["verified_review_count"] == 1
    assert result["temporal_holdout_count"] == 0
    assert result["candidate_beats_baseline"] is None
    assert result["model_weight_mutation"] is False
    assert output.stat().st_mode & 0o777 == 0o600


def test_shadow_hook_disabled_by_default(tmp_path):
    from empire_os.economic_memory import refresh_economic_memory_snapshot

    refresh_economic_memory_snapshot(tmp_path)
    assert (tmp_path / "runtime/economic_memory/latest.json").is_file()
    assert not (tmp_path / "runtime/lead_intelligence_calibration/shadow_latest.json").exists()
    with pytest.raises(ValueError, match="boolean"):
        refresh_economic_memory_snapshot(tmp_path, shadow_calibration="true")


def test_verified_feedback_without_original_prediction_is_reported_not_trained():
    data = deepcopy(memory())
    data["calibration_evidence"] = []
    report = evaluate_shadow_calibration(data, tenant_id=TENANT, as_of=AS_OF)
    assert report["verified_outcome_feedback_count"] == 1
    assert report["unpaired_verified_outcome_count"] == 1
    assert "verified_outcome_original_prediction_missing" in report["blockers"]
    assert report["candidate_beats_baseline"] is None
    assert report["lead_research_formula_evaluated"] is False


def test_unpaired_forged_feedback_cannot_claim_verified_outcomes():
    data = deepcopy(memory())
    data["calibration_evidence"] = []
    data["verified_learning_feedback"][0]["verified_outcome"] = False
    with pytest.raises(ValueError, match="unverified"):
        evaluate_shadow_calibration(data, tenant_id=TENANT, as_of=AS_OF)
