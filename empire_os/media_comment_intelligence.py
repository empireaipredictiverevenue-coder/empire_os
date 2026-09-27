"""Comment intelligence for Empire Media OS.

Consumes public/owned-channel comment observations and emits evidence-linked
voice-of-buyer signals. It does not post replies or infer purchase intent from
ambiguous language.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class MediaCommentObservation:
    comment_id: str
    channel_id: str
    video_id: str
    text: str
    evidence_ref: str
    observed_at: str | None = None
    author_ref: str | None = None
    public_source: bool = True

    def validate(self) -> None:
        if not self.comment_id.strip():
            raise ValueError("comment_id is required")
        if not self.video_id.strip():
            raise ValueError("video_id is required")
        if not self.text.strip():
            raise ValueError("comment text is required")
        if not self.evidence_ref.strip():
            raise ValueError("comment evidence_ref is required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def classify_comment_signal(
    comment: MediaCommentObservation,
    *,
    explicit_categories: Iterable[str] = (),
    explicit_buying_language: bool = False,
    product_request: bool = False,
    competitor_mention: bool = False,
    requested_follow_up: bool = False,
) -> dict[str, Any]:
    comment.validate()
    allowed = {
        "question",
        "objection",
        "confusion",
        "positive_reaction",
        "negative_reaction",
        "product_request",
        "competitor_mention",
        "follow_up_request",
        "emerging_topic",
    }
    categories = sorted({
        str(value).strip()
        for value in explicit_categories
        if str(value).strip() in allowed
    })
    if product_request:
        categories.append("product_request")
    if competitor_mention:
        categories.append("competitor_mention")
    if requested_follow_up:
        categories.append("follow_up_request")
    categories = sorted(set(categories))

    return {
        "schema_version": "empire.media.comment_signal.v1",
        "mode": "OBSERVE",
        "comment": comment.as_dict(),
        "categories": categories,
        "explicit_buying_language_observed": bool(
            explicit_buying_language
        ),
        "buying_intent_inferred": False,
        "product_request_observed": bool(product_request),
        "competitor_mention_observed": bool(competitor_mention),
        "requested_follow_up_observed": bool(requested_follow_up),
        "feed_targets": [
            "community_intent",
            "conversation_os",
            "opportunity_factory",
            "media_os",
        ],
        "reply_publish_authorized": False,
        "execution_authority": "none",
    }


def prepare_comment_reply_draft(
    *,
    comment_signal: dict[str, Any],
    reply_text: str,
    policy_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [str(x).strip() for x in policy_refs if str(x).strip()]
    if not str(reply_text or "").strip():
        raise ValueError("reply_text is required")
    if not refs:
        raise ValueError("comment reply policy_refs are required")
    return {
        "schema_version": "empire.media.comment_reply_draft.v1",
        "mode": "OBSERVE",
        "comment_id": (
            (comment_signal.get("comment") or {}).get("comment_id")
        ),
        "reply_text": reply_text.strip(),
        "policy_refs": refs,
        "brand_policy_check_required": True,
        "usefulness_review_required": True,
        "generic_bot_reply_allowed": False,
        "publish_authorized": False,
        "publish_action_performed": False,
        "execution_authority": "none",
    }
