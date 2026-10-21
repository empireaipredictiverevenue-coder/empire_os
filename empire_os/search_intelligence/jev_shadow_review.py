"""Read-only SEO/Quora Jev task readiness, NOT provider inference.

Reuses the canonical Quora review, typed-decision request, and Jev readiness
contracts. There are no authenticated question pages or real labeled SEO cases
yet, so this endpoint reports a blocked shadow provider honestly.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from empire_os.jev_strategy import review_jev_use_case
from empire_os.typed_decision_provider import TypedDecisionRequest
from empire_os.typed_decision_readiness import review_task_readiness

from .quora_intelligence import review_quora_research

SCHEMA = "empire.search.quora_jev_shadow_readiness.v1"
ALLOWED_LABELS = (
    "INFORMATIONAL_RESEARCH",
    "COMMERCIAL_RESEARCH",
    "EMPLOYMENT_EXCLUDE",
    "ABSTAIN",
)
LABEL_CRITERIA = {
    "INFORMATIONAL_RESEARCH": "Independent question text primarily seeks learning, not service.",
    "COMMERCIAL_RESEARCH": "Independent question text compares providers, prices, or services.",
    "EMPLOYMENT_EXCLUDE": "Independent question text asks for jobs, careers, or recruitment.",
    "ABSTAIN": "Evidence insufficient, contradictory or too ambiguous to classify.",
}


class JevSeoEvidenceError(ValueError):
    pass


def review_quora_jev_shadow(
    quora_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create bounded provider-ready requests without evaluating or writing them."""
    review = review_quora_research() if quora_review is None else quora_review
    if (not isinstance(review, Mapping)
            or review.get("schema_version") != "empire.search_intelligence.quora_research.v1"
            or review.get("mode") != "OBSERVE"
            or review.get("execution_authority") != "NONE"
            or review.get("automated_posting_authorized") is not False
            or review.get("production_writes") is not False
            or review.get("external_requests_performed") is not False
            or review.get("third_party_visits_first_party") is not False
            or review.get("owner_editorial_signoff_verified") is not False
            or review.get("verified_quora_questions") != 0
            or review.get("published_answers_verified") != 0):
        raise JevSeoEvidenceError("QUORA_RESEARCH_EVIDENCE_UNTRUSTED")
    topics = review.get("topics")
    if (not isinstance(topics, list) or not 1 <= len(topics) <= 64
            or len(topics) != review.get("topic_count")
            or len({t.get("item_id") for t in topics if isinstance(t, Mapping)}) != len(topics)):
        raise JevSeoEvidenceError("QUORA_TOPICS_NOT_BOUNDED")
    queue = []
    for topic in topics:
        if (not isinstance(topic, Mapping)
                or topic.get("answer_publication_state") != "RESEARCH_ONLY"
                or topic.get("editorial_review_required") is not True
                or topic.get("proposed_page_public_verified") is not False
                or not isinstance(topic.get("item_id"), str)
                or not isinstance(topic.get("question_theme"), str)
                or not isinstance(topic.get("vertical"), str)
                or topic.get("vertical") not in {"roofing","hvac","solar","dental","legal","b2b"}):
            raise JevSeoEvidenceError("QUORA_TOPIC_NOT_APPROVED_FOR_RESEARCH")
        specialist = topic.get("vertical") in {"dental", "legal"}
        if topic.get("specialist_editorial_review_required") is not specialist:
            raise JevSeoEvidenceError("SPECIALIST_REVIEW_CONTRACT_DRIFT")
        request = TypedDecisionRequest(
            task_key="keyword_intent",
            decision_schema_ref="empire.search.quora_jev_keyword_intent.v1",
            state_ref="quora-topic:" + topic["item_id"],
            state={
                "topic_theme": topic["question_theme"],
                "vertical": topic["vertical"],
                "source_truth": "EDITORIAL_HYPOTHESIS_ONLY",
                "existing_semantic_hypothesis": topic.get("intent_hypothesis"),
                "quora_origin_question_verified": False,
            },
            allowed_labels=ALLOWED_LABELS,
            risk_class="high" if specialist else "medium",
            label_criteria=LABEL_CRITERIA,
        )
        request.validate()
        queue.append({
            "topic_id": topic["item_id"],
            "vertical": topic["vertical"],
            "task_key": request.task_key,
            "typed_decision_schema_ref": request.decision_schema_ref,
            "state_ref": request.state_ref,
            "allowed_labels": list(request.allowed_labels),
            "risk_class": request.risk_class,
            "existing_semantic_hypothesis": topic.get("intent_hypothesis"),
            "original_quora_question_verified": False,
            "real_labeled_case_available": False,
            "specialist_editorial_review_required": specialist,
            "next_research_action": (
                "VERIFY_ORIGINAL_QUESTION_AND_SPECIALIST_REVIEW" if specialist
                else "VERIFY_ORIGINAL_QUESTION"
            ),
            "jev_prediction": None,
            "jev_confidence": None,
            "published_answer_approved": False,
            "outbound_authorized": False,
        })
    readiness = review_task_readiness({
        "task_key": "keyword_intent",
        "real_labeled_case_count": 0,
        "provider_output_count": 0,
        "shadow_record_count": 0,
        "independent_review_count": 0,
        "calibration_observed": False,
        "fallback_tested": False,
        "drift_monitor_defined": False,
        "schema_failure_measured": False,
        "synthetic_cases_present": False,
    })
    use_case = review_jev_use_case({
        "task_key": "keyword_intent",
        "risk_class": "medium",
        "decision_schema_ref": "empire.search.quora_jev_keyword_intent.v1",
        "baseline_ref": "empire.search_intelligence.semantic_opportunity_review",
        "evaluation_dataset_refs": [],
        "deterministic_possible": True,
        "open_ended_generation": False,
        "consequential_authority": False,
    })
    counts = dict(sorted(Counter(t["vertical"] for t in queue).items()))
    if counts != review.get("vertical_topic_counts"):
        raise JevSeoEvidenceError("QUORA_VERTICAL_COUNTS_MISMATCH")
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "provider_key": "disabled",
        "provider_invoked": False,
        "external_requests_performed": False,
        "external_tokens_billed": 0,
        "jev_model_predictions_count": 0,
        "real_labeled_case_count": 0,
        "reviewed_topics_count": len(queue),
        "vertical_topic_counts": counts,
        "typed_request_contract": "Validated existing TypedDecisionRequest; unexecuted",
        "cases_ready_for_model_evaluation": 0,
        "topic_review_queue": queue,
        "jev_use_case_readiness": use_case,
        "typed_decision_task_readiness": readiness,
        "actual_quora_questions_verified": 0,
        "publishing_authorized": False,
        "buyer_routing_authorized": False,
        "revenue_recognition_authorized": False,
        "production_writes": False,
        "execution_authority": "NONE",
    }
