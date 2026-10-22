"""AI does first-pass investigation, not counterfeit human ground truth."""
from dataclasses import replace

import pytest

from empire_os.search_intelligence.ai_first_seo_review import (
    LABELS, SeoAiFirstHeld, public_safe_ai_summary,
    request_for_case, review_cases_with_local_ai,
)
from empire_os.typed_decision_provider import TypedDecisionResult


def synthetic_rows():
    return [{
        "path": "/aeo/roofing/ABCD/",
        "case_id": f"gsc404:{i:024d}",
        "source_ref": f"gsc-page-origin-sha256:{i:064x}",
        "window": ["2026-10-07","2026-10-19"],
        "observed_origin_http_status": 404,
        "observed_page_dimension_impressions": 2,
        "observed_page_dimension_clicks": 0,
        "deterministic_review_category": "ROOFING_RESEARCH_REVIEW",
    } for i in range(30)]


class LocalStub:
    def __init__(self, confidence=0.92, label="SOURCE_AUDIT", fail=False):
        self.confidence=confidence
        self.label=label
        self.fail=fail
        self.calls=[]

    def evaluate(self, request):
        assert request.allowed_labels == LABELS
        assert request.state["publisher_rights_verified"] is False
        assert request.state["origin_http_status"] == 404
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("model unavailable")
        return TypedDecisionResult(
            provider_key="laya_http",model_key="convaiinnovations/laya:onnx",
            task_key=request.task_key,decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref,label=self.label,confidence=self.confidence,
            latency_ms=3.0, source_ref="laya:http:shadow:case",
            shadow_only=True,execution_authority="none",
        )


def test_30_local_model_calls_produce_only_advisory():
    stub=LocalStub()
    packet=review_cases_with_local_ai(synthetic_rows(), provider=stub)
    assert len(stub.calls)==30
    assert packet["ai_candidate_count"]==30
    assert packet["external_paid_jev_calls"]==0
    assert packet["human_ground_truth_labels_created"]==0
    assert packet["publication_or_redirect_authorized"] is False
    assert all(c["decision_status"]=="UNVERIFIED_AI_ADVISORY_FOR_REVIEW" for c in packet["case_reviews"])
    assert all(c["source_content_verified_by_ai"] is False for c in packet["case_reviews"])
    summary=public_safe_ai_summary(packet)
    assert summary["model_candidates_returned"]==30
    assert summary["deep_ai_research_queue_count"]==0
    assert "/aeo/" not in str(summary)


def test_low_confidence_routes_to_deeper_ai_not_fake_label():
    packet=review_cases_with_local_ai(synthetic_rows(),provider=LocalStub(confidence=.18))
    assert packet["review_status_counts"]["DEEPER_AI_SOURCE_RESEARCH_REQUIRED"]==30
    assert public_safe_ai_summary(packet)["deep_ai_research_queue_count"]==30
    assert packet["human_ground_truth_labels_created"]==0


def test_offline_provider_failures_do_not_escape_or_trigger_external_fallback():
    packet=review_cases_with_local_ai(synthetic_rows(),provider=LocalStub(fail=True))
    assert packet["review_status_counts"]["MODEL_FAILURE_ESCALATE_TO_DEEPER_AI_RESEARCH"]==30
    assert packet["ai_candidate_count"]==0
    assert packet["external_paid_jev_calls"]==0


@pytest.mark.parametrize("label",["PUBLISH_NOW","REDIRECT_NOW","buyer_confirmed"])
def test_unauthorised_label_is_never_accepted(label):
    packet=review_cases_with_local_ai(synthetic_rows(),provider=LocalStub(label=label))
    assert packet["ai_candidate_count"]==0
    assert public_safe_ai_summary(packet)["deep_ai_research_queue_count"]==30


def test_no_unbounded_cohort_or_inference_count():
    with pytest.raises(SeoAiFirstHeld):
        review_cases_with_local_ai(synthetic_rows()[:29],provider=LocalStub())
    with pytest.raises(SeoAiFirstHeld):
        review_cases_with_local_ai(synthetic_rows(),provider=LocalStub(),limit=500)


def test_summary_rejects_false_ground_truth_and_authority():
    packet=review_cases_with_local_ai(synthetic_rows(),provider=LocalStub())
    packet["human_ground_truth_labels_created"]=30
    with pytest.raises(SeoAiFirstHeld):
        public_safe_ai_summary(packet)
    packet["human_ground_truth_labels_created"]=0
    packet["case_reviews"][0]["automatic_seo_change_authorized"]=True
    with pytest.raises(SeoAiFirstHeld):
        public_safe_ai_summary(packet)


def test_request_uses_original_sample_only():
    req=request_for_case(synthetic_rows()[0])
    req.validate()
    assert req.state["owned_url_path"] == "/aeo/roofing/ABCD/"
    assert req.state["buyer_conversion_verified"] is False
    assert req.risk_class=="medium"
