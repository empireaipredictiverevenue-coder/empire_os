import pytest

from empire_os.typed_decision_shadow_collector import (
    build_label_review_queue,
    collect_shadow_candidates,
    shadow_collection_summary,
)


def test_reply_collection_creates_review_queue_without_provider_call():
    batch = collect_shadow_candidates([
        {
            "reply_id": "r1",
            "provider_message_id": "m1",
            "subject": "Re: proposal",
            "body_text": "Interested, tell me more.",
            "received_at": "2026-09-20T10:00:00Z",
        }
    ], task_key="reply_classification")
    assert batch["ready_count"] == 1
    assert batch["provider_called"] is False
    queue = build_label_review_queue(batch)
    assert queue["queue_count"] == 1
    assert queue["auto_label_applied"] is False
    assert queue["queue"][0]["review_state"] == "pending"


def test_keyword_collection_preserves_observed_intent_as_reference_only():
    batch = collect_shadow_candidates([
        {
            "query_id": "q1",
            "query": "predictive revenue pricing",
            "intent": "commercial",
            "observed_at": "2026-09-20T10:00:00Z",
            "source_ref": "search:q1",
        }
    ], task_key="keyword_intent")
    queue = build_label_review_queue(batch)
    assert queue["queue"][0]["existing_observed_label"] == "commercial"
    assert queue["auto_label_applied"] is False


def test_duplicate_cases_are_blocked():
    row = {
        "buyer_ref": "buyer:1",
        "corridor_ref": "roofing:manchester",
        "observed_at": "2026-09-20T10:00:00Z",
        "source_ref": "fit:1",
    }
    batch = collect_shadow_candidates([row, row], task_key="buyer_corridor_fit")
    assert batch["ready_count"] == 1
    assert batch["blocked_count"] == 1
    assert batch["blocked"][0]["blockers"] == ["duplicate_case_id"]


def test_unsupported_task_fails_closed():
    with pytest.raises(ValueError, match="unsupported task_key"):
        collect_shadow_candidates([], task_key="unknown")


def test_collection_summary_never_claims_real_labels_or_provider_outputs():
    a = collect_shadow_candidates([], task_key="reply_classification")
    b = collect_shadow_candidates([], task_key="keyword_intent")
    s = shadow_collection_summary([a, b])
    assert s["real_labels_collected"] == 0
    assert s["provider_outputs_collected"] == 0
    assert s["production_routing"] is False
