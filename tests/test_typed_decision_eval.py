import pytest

from empire_os.typed_decision_eval import (
    build_shadow_decision,
    compare_eval_reports,
    evaluate_provider_outputs,
    summarize_shadow_records,
)


def rows(provider="jev", model="jev-v1", n=40, wrong_every=10):
    out = []
    for i in range(n):
        truth = "positive" if i % 2 == 0 else "negative"
        pred = truth if i % wrong_every else ("negative" if truth == "positive" else "positive")
        out.append({
            "case_id": f"case-{i}",
            "task_key": "reply_classification",
            "provider_key": provider,
            "model_key": model,
            "ground_truth": truth,
            "predicted": pred,
            "confidence": .9 if pred == truth else .6,
            "latency_ms": 100 + i,
            "input_tokens": 50,
            "cost_cents": .001,
            "source_ref": f"eval:{i}",
        })
    return out


def test_offline_eval_computes_quality_calibration_latency_cost():
    r = evaluate_provider_outputs(rows(), minimum_samples=20)
    assert r["available"] is True
    assert r["sample_count"] == 40
    assert 0 <= r["accuracy"] <= 1
    assert 0 <= r["macro_f1"] <= 1
    assert 0 <= r["confidence_brier_score"] <= 1
    assert r["p95_latency_ms"] >= r["p50_latency_ms"]
    assert r["cost_per_million_input_tokens_cents"] is not None
    assert r["provider_activation"] is False
    assert r["production_routing"] is False


def test_insufficient_samples_stays_unavailable():
    r = evaluate_provider_outputs(rows(n=5), minimum_samples=20)
    assert r["available"] is False
    assert r["reason"] == "insufficient_samples"


def test_eval_batch_must_be_single_provider_task_model():
    mixed = rows(n=20)
    mixed[-1]["provider_key"] = "other"
    with pytest.raises(ValueError, match="one provider_key"):
        evaluate_provider_outputs(mixed, minimum_samples=1)


def test_comparison_ranks_for_review_but_selects_no_winner():
    a = evaluate_provider_outputs(rows("jev", "jev-v1"), minimum_samples=20)
    b_rows = rows("baseline", "small-v1")
    for item in b_rows[::5]:
        item["predicted"] = "other"
        item["confidence"] = .7
    b = evaluate_provider_outputs(b_rows, minimum_samples=20)
    result = compare_eval_reports([a, b])
    assert len(result["reports"]) == 2
    assert result["winner_selected"] is False
    assert result["production_provider_selected"] is False


def test_shadow_record_never_controls_live_route():
    r = build_shadow_decision({
        "shadow_id": "s1",
        "task_key": "reply_classification",
        "case_ref": "case:1",
        "incumbent_provider": "rules",
        "incumbent_decision": "positive",
        "candidate_provider": "jev",
        "candidate_decision": "negative",
        "candidate_confidence": .72,
        "decision_schema_ref": "schema:reply:v1",
    })
    assert r["agreement"] is False
    assert r["candidate_controlled_live_routing"] is False
    assert r["execution_performed"] is False


def test_shadow_summary_tracks_agreement_without_promotion():
    base = {
        "task_key": "reply_classification",
        "incumbent_provider": "rules",
        "candidate_provider": "jev",
        "candidate_confidence": .8,
        "decision_schema_ref": "schema:reply:v1",
    }
    r = summarize_shadow_records([
        {
            **base,
            "shadow_id": "s1",
            "case_ref": "c1",
            "incumbent_decision": "positive",
            "candidate_decision": "positive",
        },
        {
            **base,
            "shadow_id": "s2",
            "case_ref": "c2",
            "incumbent_decision": "negative",
            "candidate_decision": "positive",
        },
    ])
    assert r["agreement_rate"] == .5
    assert r["disagreement_count"] == 1
    assert r["production_routing"] is False
