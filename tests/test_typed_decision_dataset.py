import copy
from empire_os.typed_decision_dataset import (
    dataset_readiness,
    freeze_dataset,
    reply_classifier_fixture_rows,
    verify_frozen_dataset,
)


def test_frozen_dataset_has_stable_hash_independent_of_input_order():
    rows=reply_classifier_fixture_rows()
    a=freeze_dataset(rows,dataset_id="reply-fixture",version="v1")
    b=freeze_dataset(list(reversed(rows)),dataset_id="reply-fixture",version="v1")
    assert a["sha256"]==b["sha256"]
    assert a["case_count"]==14


def test_fixture_manifest_cannot_be_promotion_evidence():
    m=freeze_dataset(
        reply_classifier_fixture_rows(),
        dataset_id="reply-fixture",
        version="v1",
    )
    assert m["synthetic_test_fixture_count"]==14
    assert m["real_labeled_case_count"]==0
    assert m["eligible_for_production_promotion_evidence"] is False
    assert m["commercial_evidence"] is False


def test_hash_verification_detects_mutation():
    m=freeze_dataset(
        reply_classifier_fixture_rows(),
        dataset_id="reply-fixture",
        version="v1",
    )
    assert verify_frozen_dataset(m)["valid"] is True
    mutated=copy.deepcopy(m)
    mutated["cases"][0]["ground_truth"]="other"
    assert verify_frozen_dataset(mutated)["valid"] is False


def test_readiness_blocks_synthetic_and_insufficient_data():
    m=freeze_dataset(
        reply_classifier_fixture_rows(),
        dataset_id="reply-fixture",
        version="v1",
    )
    r=dataset_readiness(m,minimum_per_label=2)
    assert r["ready_for_provider_promotion_eval"] is False
    assert "synthetic_test_fixtures_present" in r["blockers"]
    assert "no_real_labeled_cases" in r["blockers"]
    assert r["execution_authority"]=="none"
