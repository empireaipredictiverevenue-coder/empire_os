"""Content decay and refresh candidate logic for Empire Media OS."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def detect_content_decay(
    *,
    recent_values: Iterable[float],
    historical_values: Iterable[float],
    minimum_samples: int = 3,
    material_decline_ratio: float = 0.25,
) -> dict[str, Any]:
    recent = [float(x) for x in recent_values]
    historical = [float(x) for x in historical_values]

    if (
        len(recent) < minimum_samples
        or len(historical) < minimum_samples
    ):
        return {
            "schema_version": "empire.media.content_decay.v1",
            "state": "INSUFFICIENT_EVIDENCE",
            "structural_decay_detected": False,
            "execution_authority": "none",
        }

    recent_avg = sum(recent) / len(recent)
    hist_avg = sum(historical) / len(historical)
    if hist_avg <= 0:
        decline = None
        structural = False
    else:
        decline = (hist_avg - recent_avg) / hist_avg
        structural = decline >= float(material_decline_ratio)

    return {
        "schema_version": "empire.media.content_decay.v1",
        "state": (
            "STRUCTURAL_DECAY_CANDIDATE"
            if structural
            else "NORMAL_OR_NONSTRUCTURAL_VARIATION"
        ),
        "recent_average": round(recent_avg, 6),
        "historical_average": round(hist_avg, 6),
        "decline_ratio": (
            round(decline, 6)
            if decline is not None
            else None
        ),
        "structural_decay_detected": structural,
        "causal_explanation_created": False,
        "execution_authority": "none",
    }


def build_content_refresh_candidate(
    *,
    video_id: str,
    evidence_refs: Iterable[str],
    historical_value_observed: bool,
    falling_ctr_observed: bool,
    outdated_fact_observed: bool,
    product_version_changed: bool,
    old_thumbnail_observed: bool,
    search_demand_changed: bool,
) -> dict[str, Any]:
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]
    if not str(video_id or "").strip():
        raise ValueError("video_id is required")
    if not refs:
        raise ValueError("refresh evidence_refs are required")

    reasons = []
    if historical_value_observed:
        reasons.append("high_historical_value")
    if falling_ctr_observed:
        reasons.append("falling_ctr")
    if outdated_fact_observed:
        reasons.append("outdated_fact")
    if product_version_changed:
        reasons.append("product_version_changed")
    if old_thumbnail_observed:
        reasons.append("old_thumbnail")
    if search_demand_changed:
        reasons.append("search_demand_changed")

    actions = []
    if falling_ctr_observed or old_thumbnail_observed:
        actions.extend(["title_test_candidate", "thumbnail_test_candidate"])
    if outdated_fact_observed or product_version_changed:
        actions.extend(["description_refresh_candidate", "new_edition_candidate"])
    if search_demand_changed:
        actions.extend(["seo_refresh_candidate", "follow_up_candidate"])
    if historical_value_observed:
        actions.extend(["short_candidate", "sequel_candidate"])

    return {
        "schema_version": "empire.media.content_refresh_candidate.v1",
        "mode": "OBSERVE",
        "video_id": video_id,
        "evidence_refs": refs,
        "reasons": sorted(set(reasons)),
        "candidate_actions": sorted(set(actions)),
        "refresh_candidate": bool(reasons),
        "automatic_public_mutation": False,
        "execution_authority": "none",
    }


def kill_or_pivot_review(
    *,
    series_id: str,
    observed_episode_count: int,
    repeated_underperformance: bool,
    audience_mismatch_observed: bool,
    production_cost_disproportionate: bool,
    strategic_relevance_lost: bool,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]
    if not refs:
        raise ValueError("kill/pivot review evidence_refs are required")

    reasons = []
    for condition, label in (
        (repeated_underperformance, "repeated_underperformance"),
        (audience_mismatch_observed, "audience_mismatch"),
        (production_cost_disproportionate, "production_cost_disproportionate"),
        (strategic_relevance_lost, "strategic_relevance_lost"),
    ):
        if condition:
            reasons.append(label)

    if observed_episode_count < 3:
        decision = "HOLD_INSUFFICIENT_SERIES_EVIDENCE"
    elif len(reasons) >= 2:
        decision = "PIVOT_OR_RETIRE_CANDIDATE"
    elif reasons:
        decision = "REDUCE_OR_TEST_CANDIDATE"
    else:
        decision = "CONTINUE"

    return {
        "schema_version": "empire.media.kill_pivot_review.v1",
        "mode": "OBSERVE",
        "series_id": series_id,
        "observed_episode_count": int(observed_episode_count),
        "reasons": reasons,
        "decision": decision,
        "automatic_series_shutdown": False,
        "execution_authority": "none",
    }
