"""Jev SEO readiness is real source-gated shadow infrastructure, not AI claims."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from empire_os.search_intelligence.jev_shadow_review import (
    JevSeoEvidenceError, review_quora_jev_shadow,
)
from empire_os.search_intelligence.quora_intelligence import review_quora_research
from empire_os.search_intelligence.service import build_search_intelligence_service


def test_all_six_sectors_get_existing_typed_decision_contracts():
    packet = review_quora_jev_shadow()
    assert packet["schema_version"] == "empire.search.quora_jev_shadow_readiness.v1"
    assert packet["reviewed_topics_count"] == 56
    assert packet["vertical_topic_counts"] == {
        "roofing": 16, "hvac": 8, "solar": 8,
        "dental": 8, "legal": 8, "b2b": 8,
    }
    assert len(packet["topic_review_queue"]) == 56
    assert len({x["topic_id"] for x in packet["topic_review_queue"]}) == 56
    assert all(x["task_key"] == "keyword_intent" for x in packet["topic_review_queue"])
    assert all(x["state_ref"].startswith("quora-topic:") for x in packet["topic_review_queue"])
    assert all(x["jev_prediction"] is None and x["jev_confidence"] is None
               for x in packet["topic_review_queue"])
    assert all(x["original_quora_question_verified"] is False
               for x in packet["topic_review_queue"])
    assert all(x["published_answer_approved"] is False
               for x in packet["topic_review_queue"])
    assert all(x["outbound_authorized"] is False
               for x in packet["topic_review_queue"])


def test_jev_remains_disabled_without_real_ground_truth_or_provider():
    data = review_quora_jev_shadow()
    assert data["provider_key"] == "disabled"
    assert data["provider_invoked"] is False
    assert data["jev_model_predictions_count"] == 0
    assert data["real_labeled_case_count"] == 0
    assert data["cases_ready_for_model_evaluation"] == 0
    assert data["external_requests_performed"] is False
    assert data["external_tokens_billed"] == 0
    assert data["production_writes"] is False
    assert data["execution_authority"] == "NONE"
    assert data["publishing_authorized"] is False
    assert data["buyer_routing_authorized"] is False
    assert data["revenue_recognition_authorized"] is False
    readiness = data["typed_decision_task_readiness"]
    assert readiness["promotion_review_ready"] is False
    assert readiness["shadow_eval_ready"] is False
    assert "insufficient_real_labels" in readiness["blockers"]
    assert "calibration_not_observed" in readiness["blockers"]
    assert data["jev_use_case_readiness"]["provider_activation"] is False
    assert data["jev_use_case_readiness"]["review_ready"] is False
    assert "evaluation_dataset_refs_required" in data["jev_use_case_readiness"]["warnings"]


def test_dental_legal_hold_remains_high_risk_specialist_review():
    topics = review_quora_jev_shadow()["topic_review_queue"]
    restricted = [t for t in topics if t["vertical"] in ("dental", "legal")]
    assert len(restricted) == 16
    assert all(t["risk_class"] == "high" for t in restricted)
    assert all(t["specialist_editorial_review_required"] is True for t in restricted)
    assert all(t["next_research_action"] ==
               "VERIFY_ORIGINAL_QUESTION_AND_SPECIALIST_REVIEW" for t in restricted)
    regular = [t for t in topics if t["vertical"] not in ("dental", "legal")]
    assert len(regular) == 40
    assert all(t["risk_class"] == "medium" for t in regular)


@pytest.mark.parametrize("key, value", [
    ("execution_authority", "PUBLISH"),
    ("mode", "LIVE"),
    ("automated_posting_authorized", True),
    ("production_writes", True),
    ("external_requests_performed", True),
    ("third_party_visits_first_party", True),
    ("owner_editorial_signoff_verified", True),
    ("verified_quora_questions", 1),
    ("published_answers_verified", 1),
])
def test_untrusted_approval_or_source_state_fails_closed(key, value):
    original = review_quora_research()
    original[key] = value
    with pytest.raises(JevSeoEvidenceError, match="QUORA_RESEARCH_EVIDENCE_UNTRUSTED"):
        review_quora_jev_shadow(original)


def test_fake_sector_counts_and_specialist_bypass_fail_closed():
    raw = review_quora_research()
    changed = deepcopy(raw)
    changed["topics"][0]["specialist_editorial_review_required"] = True
    with pytest.raises(JevSeoEvidenceError, match="SPECIALIST_REVIEW_CONTRACT_DRIFT"):
        review_quora_jev_shadow(changed)
    changed = deepcopy(raw)
    changed["vertical_topic_counts"]["roofing"] += 1
    with pytest.raises(JevSeoEvidenceError, match="QUORA_VERTICAL_COUNTS_MISMATCH"):
        review_quora_jev_shadow(changed)


def test_http_endpoint_is_fully_read_only_and_unverifiable_source_held(monkeypatch):
    client = TestClient(build_search_intelligence_service())
    live = client.get("/v1/search/quora/jev-shadow/review")
    assert live.status_code == 200
    assert live.headers["cache-control"] == "no-store"
    assert live.headers["x-content-type-options"] == "nosniff"
    assert live.json()["reviewed_topics_count"] == 56
    assert live.json()["provider_invoked"] is False
    import empire_os.search_intelligence.jev_shadow_review as adapter

    def broken():
        raise JevSeoEvidenceError("secret_untrusted_file")
    monkeypatch.setattr(adapter, "review_quora_research", broken)
    unavailable = client.get("/v1/search/quora/jev-shadow/review")
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "quora_jev_shadow_source_unavailable"
    assert "secret" not in str(unavailable.json())


def test_no_provider_called_even_if_existing_disabled_provider_is_patched(monkeypatch):
    from empire_os.typed_decision_provider import DisabledTypedDecisionProvider
    def forbidden(*args, **kwargs):
        raise AssertionError("Provider should never be called in readiness GET")
    monkeypatch.setattr(DisabledTypedDecisionProvider, "evaluate", forbidden)
    result = review_quora_jev_shadow()
    assert result["provider_invoked"] is False
