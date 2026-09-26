from empire_os.typed_decision_labels import (
    build_real_eval_case,
    resolve_label_consensus,
    review_label_record,
)


def label(label_id="l1",value="positive",source="human_review",state="accepted"):
    return {
        "label_id":label_id,
        "case_id":"case-1",
        "task_key":"reply_classification",
        "proposed_label":value,
        "label_source":source,
        "source_ref":f"labelsrc:{label_id}",
        "reviewer_ref":"reviewer:1" if state=="accepted" else None,
        "review_state":state,
        "point_in_time_ref":"pit:1",
        "tenant_key":"tenant:1",
    }


def test_accepted_human_label_can_enter_dataset():
    r=review_label_record(label())
    assert r["accepted_for_dataset"] is True
    assert r["commercial_evidence"] is False


def test_deterministic_rule_label_not_real_promotion_evidence():
    r=review_label_record(label(source="deterministic_rule"))
    assert r["accepted_for_dataset"] is False
    assert "deterministic_rule_not_real_human_or_outcome_label" in r["blockers"]


def test_label_disagreement_blocks_consensus():
    r=resolve_label_consensus([
        label("l1","positive"),
        label("l2","negative"),
    ])
    assert r["available"] is False
    assert r["reason"]=="label_disagreement"
    assert r["promotion_eligible"] is False


def test_reviewed_real_observation_builds_non_synthetic_case():
    labels=[
        label("l1","positive","human_review"),
        label("l2","positive","independent_verifier"),
    ]
    r=build_real_eval_case(
        observation={
            "inputs":{"body_text":"Interested, tell me more."},
            "source_ref":"reply:real:1",
            "point_in_time_ref":"pit:reply:1",
        },
        labels=labels,
    )
    assert r["ready"] is True
    assert r["case"]["synthetic_test_fixture"] is False
    assert r["case"]["ground_truth"]=="positive"
    assert r["commercial_evidence"] is False
