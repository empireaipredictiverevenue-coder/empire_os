"""Buyer Reply / Conversation Operations Agent.

Architecture:
docs/BUSINESS_AGENT_ARCHITECTURE_BATCH_1.md

This module turns observed inbound reply text into a governed internal next-action
state. It does not send outbound, accept terms, mutate suppression directly,
move funds, or recognize revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any, Mapping

from empire_os.gmail_reply_adapter import visible_reply_text
from empire_os.reply_classifier import classify_reply_text


@dataclass(frozen=True)
class BuyerReplyOpsDecision:
    classification: str
    confidence: float
    deterministic_auto_apply: bool
    next_action: str
    review_required: bool
    reasoning_required: bool
    draft_eligible: bool
    suppression_required: bool
    follow_up_recommended: bool
    visible_reply_sha256: str
    specialist_shadow: Mapping[str, Any] | None = None
    outbound_send_authority: bool = False
    terms_acceptance_authority: bool = False
    payment_authority: bool = False
    revenue_recognition_authority: bool = False
    actual_revenue: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def analyze_buyer_reply(
    body_text: Any,
    subject: Any = "",
    *,
    laya_shadow: Mapping[str, Any] | None = None,
) -> BuyerReplyOpsDecision:
    """Return an evidence-backed internal decision for one observed reply."""
    visible = visible_reply_text(body_text)
    classified = classify_reply_text(visible, subject)
    label = str(classified["classification"])
    confidence = float(classified["confidence"])
    auto_apply = bool(classified["auto_apply"])

    next_action = "manual_review"
    review_required = True
    reasoning_required = False
    draft_eligible = False
    suppression_required = False
    follow_up_recommended = False

    if label == "unsubscribe":
        next_action = "suppress_and_close"
        review_required = False
        suppression_required = True
    elif label == "negative":
        next_action = "close_negative"
        review_required = False
    elif label == "later":
        next_action = "schedule_followup_review"
        review_required = False
        follow_up_recommended = True
    elif label == "positive":
        next_action = "reason_and_prepare_reply"
        review_required = True
        reasoning_required = True
        draft_eligible = True
    elif label == "question":
        next_action = "answer_from_evidence_then_prepare_reply"
        review_required = True
        reasoning_required = True
        draft_eligible = True
    elif label == "objection":
        next_action = "reason_over_objection_then_prepare_reply"
        review_required = True
        reasoning_required = True
        draft_eligible = True

    specialist: dict[str, Any] | None = None
    if isinstance(laya_shadow, Mapping):
        specialist = {
            "label": str(laya_shadow.get("label") or "").strip() or None,
            "confidence": laya_shadow.get("confidence"),
            "accepted_for_shadow_analysis": bool(
                laya_shadow.get("accepted_for_shadow_analysis")
            ),
            "reason": str(laya_shadow.get("reason") or "").strip() or None,
            "authority": "shadow_only",
        }

    return BuyerReplyOpsDecision(
        classification=label,
        confidence=confidence,
        deterministic_auto_apply=auto_apply,
        next_action=next_action,
        review_required=review_required,
        reasoning_required=reasoning_required,
        draft_eligible=draft_eligible,
        suppression_required=suppression_required,
        follow_up_recommended=follow_up_recommended,
        visible_reply_sha256=_sha256(visible),
        specialist_shadow=specialist,
    )


def buyer_reply_ops_status() -> dict[str, Any]:
    return {
        "schema_version": "empire.buyer-reply-ops.v1",
        "supported_classes": [
            "positive",
            "question",
            "objection",
            "later",
            "negative",
            "unsubscribe",
            "other",
        ],
        "laya_role": "negative_unsubscribe_shadow_only",
        "positive_question_objection_route": "governed_reasoning_required",
        "outbound_send_authority": False,
        "terms_acceptance_authority": False,
        "payment_authority": False,
        "revenue_recognition_authority": False,
        "execution_authority": "none",
    }
