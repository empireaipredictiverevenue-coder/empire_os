"""Offline evidence-only incumbent/challenger evaluation for JEV GTM."""
from copy import deepcopy
import pytest

from empire_os.typed_decision_dataset import freeze_dataset
from empire_os.jev_gtm_challenger import evaluate_jev_gtm_challenger


def dataset(size=100, *, synthetic=False):
    labels = ("accept", "review", "quarantine", "reject")
    rows = []
    for i in range(size):
        label = labels[i % 4]
        rows.append({
            "case_id": f"case:{i}",
            "task_key": "source_quality",
            "inputs": {"source_ref": f"source:{i}", "evidence_summary": "independently reviewed example"},
            "ground_truth": label,
            "label_source": "independent_human_review",
            "source_ref": f"source:{i}",
            "synthetic_test_fixture": synthetic,
        })
    return freeze_dataset(rows, dataset_id="holdout:gtm", version="v1")


def outputs(manifest, *, provider, errors=0, wrong_label=None):
    ret = []
    for i, case in enumerate(manifest["cases"]):
        predicted = case["ground_truth"]
        if i < errors:
            predicted = wrong_label or "review"
            if predicted == case["ground_truth"]:
                predicted = "reject"
        ret.append({
            "case_id": case["case_id"], "task_key": case["task_key"],
            "ground_truth": case["ground_truth"],
            "predicted": predicted, "confidence": .8,
            "provider_key": provider, "model_key": provider + ":v1",
            "latency_ms": 12, "input_tokens": None,
            "cost_cents": None, "source_ref": case["source_ref"],
        })
    return ret


def compare(manifest=None, **kw):
    manifest = manifest or dataset()
    return evaluate_jev_gtm_challenger(
        dataset=manifest,
        incumbent_outputs=outputs(manifest, provider="incumbent", errors=15),
        challenger_outputs=outputs(manifest, provider="challenger", errors=5),
        independent_review_refs=["review:1"],
        **kw,
    )


def test_comparable_case_aligned_reports_no_activation():
    result = compare()
    assert result["dataset_case_count"] == 100
    assert result["challenger"]["macro_f1"] > result["incumbent"]["macro_f1"]
    assert result["model_selected"] is False
    assert result["live_routing_activated"] is False
    assert result["execution_authority"] == "none"
    assert result["reviews_cryptographically_authenticated"] is False


def test_synthetic_fixture_never_counts_as_production_readiness():
    result = compare(manifest=dataset(synthetic=True))
    assert result["promotion_evidence_review_ready"] is False
    assert "synthetic_cases_cannot_prove_production_readiness" in result["blockers"]


def test_no_independent_review_blocks_readiness():
    m = dataset()
    r = evaluate_jev_gtm_challenger(
        dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
        challenger_outputs=outputs(m, provider="challenger"),
    )
    assert "independent_review_references_missing" in r["blockers"]


def test_undersized_holdout_never_eligible():
    r = compare(manifest=dataset(size=40))
    assert "insufficient_real_holdout_cases" in r["blockers"]


def test_worse_challenger_is_blocked():
    m = dataset()
    r = evaluate_jev_gtm_challenger(
        dataset=m, incumbent_outputs=outputs(m, provider="incumbent", errors=0),
        challenger_outputs=outputs(m, provider="challenger", errors=25),
        independent_review_refs=["review:1"],
    )
    assert "challenger_macro_f1_below_incumbent" in r["blockers"]


def test_tampered_hash_is_rejected():
    m = dataset()
    m["sha256"] = "deadbeef"
    with pytest.raises(ValueError, match="hash mismatch"):
        compare(manifest=m)


def test_different_source_ref_is_rejected():
    m = dataset()
    bad = outputs(m, provider="challenger")
    bad[0]["source_ref"] = "invented"
    with pytest.raises(ValueError, match="contradicts frozen"):
        evaluate_jev_gtm_challenger(
            dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
            challenger_outputs=bad,
        )


def test_label_leakage_is_rejected():
    m = dataset()
    bad = outputs(m, provider="challenger")
    bad[0]["ground_truth"] = "invented"
    with pytest.raises(ValueError, match="contradicts frozen"):
        evaluate_jev_gtm_challenger(
            dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
            challenger_outputs=bad,
        )


def test_missing_or_duplicate_cases_fail():
    m = dataset()
    bad = outputs(m, provider="challenger")
    bad[0]["case_id"] = bad[1]["case_id"]
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_jev_gtm_challenger(
            dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
            challenger_outputs=bad,
        )


def test_one_provider_per_cohort():
    m = dataset()
    bad = outputs(m, provider="challenger")
    bad[0]["provider_key"] = "other"
    with pytest.raises(ValueError, match="one provider"):
        evaluate_jev_gtm_challenger(
            dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
            challenger_outputs=bad,
        )


def test_cannot_relax_real_case_floor():
    with pytest.raises(ValueError, match="cannot be relaxed"):
        compare(minimum_real_cases=1)


def test_unacceptable_label_is_rejected():
    m = dataset()
    bad = outputs(m, provider="challenger")
    bad[0]["predicted"] = "SEND_MONEY"
    with pytest.raises(ValueError, match="not defined"):
        evaluate_jev_gtm_challenger(
            dataset=m, incumbent_outputs=outputs(m, provider="incumbent"),
            challenger_outputs=bad,
        )


def test_good_offline_metrics_still_require_authenticated_review():
    result = compare()
    assert result["offline_metrics_pass"] is True
    assert result["promotion_evidence_review_ready"] is False
    assert "independent_reviewer_authentication_not_verified" in result["blockers"]
