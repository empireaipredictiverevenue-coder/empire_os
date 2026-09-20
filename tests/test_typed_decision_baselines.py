from empire_os.typed_decision_baselines import evaluate_reply_classifier_dataset
from empire_os.typed_decision_dataset import freeze_dataset, reply_classifier_fixture_rows
from empire_os.typed_decision_eval import evaluate_provider_outputs


def test_deterministic_reply_baseline_runs_same_frozen_cases():
    manifest=freeze_dataset(reply_classifier_fixture_rows(),dataset_id="reply-fixture",version="v1")
    rows=evaluate_reply_classifier_dataset(manifest)
    assert len(rows)==manifest["case_count"]
    report=evaluate_provider_outputs(rows,minimum_samples=1)
    assert report["provider_key"]=="deterministic_rules"
    assert report["model_key"]=="reply_classifier_v1"
    assert report["production_routing"] is False
