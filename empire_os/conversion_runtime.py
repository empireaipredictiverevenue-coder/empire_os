"""Canonical live conversion snapshot builder.

Reads only canonical evidence and produces the evidence inputs consumed by
Conversion Intelligence. Missing surfaces stay absent/UNKNOWN.
"""
from __future__ import annotations

from typing import Any, Callable

from empire_os.conversion_data_repository import (
    CanonicalConversionRepository,
    ConversionRepository,
    RequestConversionRepository,
)
from empire_os.conversion_intelligence import (
    ConversionStageEvidence,
    review_conversion_system,
)


Request = Callable[..., Any]


def _repository(
    request: Request | None,
    repository: ConversionRepository | None,
) -> ConversionRepository:
    if request is not None and repository is not None:
        raise ValueError("provide request or repository, not both")
    if repository is not None:
        return repository
    if request is not None:
        return RequestConversionRepository(request)
    return CanonicalConversionRepository.from_environment()


def _distinct(values):
    return {
        str(value).strip()
        for value in values
        if str(value or "").strip()
    }


def build_live_conversion_review(
    request: Request | None = None,
    *,
    repository: ConversionRepository | None = None,
    min_sample_size: int = 20,
) -> dict[str, Any]:
    store = _repository(request, repository)
    reviews = store.approved_reviews()
    intents = store.delivered_or_replied_intents()
    replies = store.commercial_replies()
    cases = store.closer_cases()
    terms = store.commercial_terms()
    orders = store.accepted_orders()
    payment_evidence = store.payment_evidence()
    outcomes = store.commercial_outcomes()

    approved_review_ids = _distinct(row.get("id") for row in reviews)
    delivered_review_ids = _distinct(
        (row.get("metadata") or {}).get("buyer_candidate_review_id")
        for row in intents
        if row.get("status") in {"delivered", "replied"}
        and isinstance(row.get("metadata"), dict)
    )
    delivered_recipients = _distinct(
        row.get("normalized_recipient")
        for row in intents
        if row.get("status") in {"delivered", "replied"}
    )
    replied_recipients = _distinct(
        row.get("normalized_recipient")
        for row in intents
        if row.get("status") == "replied"
    )
    commercial_reply_ids = _distinct(row.get("id") for row in replies)
    qualified_case_ids = _distinct(
        row.get("id")
        for row in cases
        if row.get("state") in {"qualified", "proposal_ready", "won"}
    )
    conversation_case_ids = _distinct(
        row.get("id")
        for row in cases
        if row.get("state") not in {"lost", "paused"}
    )
    terms_ids = _distinct(row.get("id") for row in terms)
    approved_terms_ids = _distinct(
        row.get("id") for row in terms if row.get("status") == "approved"
    )
    accepted_order_ids = _distinct(
        row.get("id")
        for row in orders
        if row.get("state") in {"accepted", "paid", "fulfilled"}
    )
    paid_order_ids = _distinct(
        row.get("fulfilment_order_id") for row in payment_evidence
    )
    fulfilled_order_ids = _distinct(
        row.get("id") for row in orders if row.get("state") == "fulfilled"
    )
    positive_outcome_order_ids = _distinct(
        row.get("fulfilment_order_id")
        for row in outcomes
        if str(row.get("delivery_outcome") or "").lower()
        in {"delivered", "success", "successful", "completed"}
        or str(row.get("conversion_outcome") or "").lower()
        in {"converted", "won", "success", "successful"}
    )

    stages = [
        ConversionStageEvidence(
            stage="buyer_review_to_delivered_outreach",
            entered=len(approved_review_ids),
            converted=len(delivered_review_ids & approved_review_ids),
            evidence_ref="canonical_data:buyer_candidate_reviews+outbound_intents",
        ),
        ConversionStageEvidence(
            stage="delivered_outreach_to_reply",
            entered=len(delivered_recipients),
            converted=len(replied_recipients),
            evidence_ref="canonical_data:outbound_intents",
        ),
        ConversionStageEvidence(
            stage="reply_to_qualified_conversation",
            entered=len(commercial_reply_ids),
            converted=len(qualified_case_ids),
            evidence_ref="canonical_data:outbound_replies+closer_cases",
        ),
        ConversionStageEvidence(
            stage="conversation_to_terms",
            entered=len(conversation_case_ids),
            converted=len(terms_ids),
            evidence_ref="canonical_data:closer_cases+commercial_terms_reviews",
        ),
        ConversionStageEvidence(
            stage="terms_to_acceptance",
            entered=len(approved_terms_ids),
            converted=len(accepted_order_ids),
            evidence_ref="canonical_data:commercial_terms_reviews+fulfilment_orders",
        ),
        ConversionStageEvidence(
            stage="acceptance_to_payment",
            entered=len(accepted_order_ids),
            converted=len(paid_order_ids & accepted_order_ids),
            evidence_ref="canonical_data:fulfilment_orders+bsc_payment_evidence",
        ),
        ConversionStageEvidence(
            stage="payment_to_fulfilment",
            entered=len(paid_order_ids),
            converted=len(fulfilled_order_ids & paid_order_ids),
            evidence_ref="canonical_data:bsc_payment_evidence+fulfilment_orders",
        ),
        ConversionStageEvidence(
            stage="fulfilment_to_positive_outcome",
            entered=len(fulfilled_order_ids),
            converted=len(positive_outcome_order_ids & fulfilled_order_ids),
            evidence_ref="canonical_data:fulfilment_orders+commercial_outcomes",
        ),
    ]

    review = review_conversion_system(
        stages,
        min_sample_size=min_sample_size,
    )
    payload = review.as_dict()
    payload["source"] = "canonical_data"
    payload["min_sample_size"] = min_sample_size
    payload["counts"] = {
        item.stage: {
            "entered": item.entered,
            "converted": item.converted,
        }
        for item in stages
    }
    payload["actual_revenue"] = False
    return payload
