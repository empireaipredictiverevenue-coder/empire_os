"""Indexability evaluation and auditable lifecycle recommendations."""
from __future__ import annotations

from .models import (
    CanonicalRecommendation,
    IndexabilityRecommendation,
    PageLifecycleState,
    QualityResult,
    SearchExecutionMode,
    TransitionRecommendation,
)

_ALLOWED = {
    PageLifecycleState.DISCOVERED: {PageLifecycleState.DRAFT, PageLifecycleState.ARCHIVED},
    PageLifecycleState.DRAFT: {PageLifecycleState.QUALITY_REVIEW, PageLifecycleState.ARCHIVED},
    PageLifecycleState.QUALITY_REVIEW: {
        PageLifecycleState.APPROVED,
        PageLifecycleState.NOINDEX,
        PageLifecycleState.DRAFT,
    },
    PageLifecycleState.APPROVED: {PageLifecycleState.PUBLISHED, PageLifecycleState.ARCHIVED},
    PageLifecycleState.PUBLISHED: {
        PageLifecycleState.INDEXABLE,
        PageLifecycleState.NOINDEX,
        PageLifecycleState.REFRESH_REQUIRED,
    },
    PageLifecycleState.INDEXABLE: {
        PageLifecycleState.SUBMITTED,
        PageLifecycleState.NOINDEX,
        PageLifecycleState.REFRESH_REQUIRED,
    },
    PageLifecycleState.SUBMITTED: {
        PageLifecycleState.DISCOVERED_BY_GOOGLE,
        PageLifecycleState.DECLINED,
        PageLifecycleState.REFRESH_REQUIRED,
    },
    PageLifecycleState.DISCOVERED_BY_GOOGLE: {
        PageLifecycleState.CRAWLED,
        PageLifecycleState.DECLINED,
    },
    PageLifecycleState.CRAWLED: {
        PageLifecycleState.INDEXED,
        PageLifecycleState.DECLINED,
        PageLifecycleState.REFRESH_REQUIRED,
    },
    PageLifecycleState.INDEXED: {
        PageLifecycleState.REFRESH_REQUIRED,
        PageLifecycleState.NOINDEX,
        PageLifecycleState.ARCHIVED,
    },
    PageLifecycleState.REFRESH_REQUIRED: {
        PageLifecycleState.DRAFT,
        PageLifecycleState.QUALITY_REVIEW,
        PageLifecycleState.NOINDEX,
    },
    PageLifecycleState.NOINDEX: {
        PageLifecycleState.DRAFT,
        PageLifecycleState.QUALITY_REVIEW,
        PageLifecycleState.ARCHIVED,
    },
    PageLifecycleState.DECLINED: {
        PageLifecycleState.DRAFT,
        PageLifecycleState.ARCHIVED,
    },
    PageLifecycleState.ARCHIVED: set(),
}


def recommend_indexability(
    *,
    current_state: PageLifecycleState,
    quality: QualityResult,
    canonical: CanonicalRecommendation,
    mode: SearchExecutionMode = SearchExecutionMode.OBSERVE,
) -> IndexabilityRecommendation:
    reasons: list[str] = []
    eligible = quality.eligible_for_approval and not canonical.requires_review
    if not quality.eligible_for_approval:
        reasons.append("quality_firewall_failed")
    if canonical.requires_review:
        reasons.append("canonical_review_required")

    recommended = (
        PageLifecycleState.APPROVED
        if eligible
        else PageLifecycleState.NOINDEX
    )
    return IndexabilityRecommendation(
        current_state=current_state,
        recommended_state=recommended,
        robots="index,follow" if eligible else "noindex,follow",
        eligible_for_approval=eligible,
        # Foundation authority is OBSERVE-only even if a caller manually
        # constructs a future enum value.
        blocked_by_observe=True,
        reasons=tuple(reasons),
    )


def recommend_transition(
    current: PageLifecycleState,
    requested: PageLifecycleState,
    *,
    mode: SearchExecutionMode = SearchExecutionMode.OBSERVE,
) -> TransitionRecommendation:
    valid = requested in _ALLOWED[current]
    if not valid:
        return TransitionRecommendation(
            current_state=current,
            requested_state=requested,
            transition_valid=False,
            execution_allowed=False,
            blocked_reason="invalid_state_transition",
        )
    return TransitionRecommendation(
        current_state=current,
        requested_state=requested,
        transition_valid=True,
        execution_allowed=False,
        blocked_reason=(
            "observe_mode"
            if mode is SearchExecutionMode.OBSERVE
            else "execution_mode_not_enabled"
        ),
    )
