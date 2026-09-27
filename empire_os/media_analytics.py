"""Owned-channel analytics and retention intelligence for Media OS.

Consumes authorised analytics observations. It does not call YouTube APIs,
publish content, or infer revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable, Mapping


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


@dataclass(frozen=True)
class RetentionPoint:
    second: float
    audience_retention: float
    scene_id: str | None = None
    shot_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        second = max(0.0, float(self.second))
        retention = max(0.0, min(1.0, float(self.audience_retention)))
        return {
            "second": second,
            "audience_retention": retention,
            "scene_id": self.scene_id,
            "shot_id": self.shot_id,
        }


def normalize_owned_channel_analytics(
    raw: Mapping[str, Any],
    *,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [
        str(ref).strip()
        for ref in evidence_refs
        if str(ref).strip()
    ]
    if not refs:
        raise ValueError("owned analytics evidence_refs are required")

    numeric = {}
    for key in (
        "impressions",
        "impressions_ctr",
        "views",
        "engaged_views",
        "unique_viewers",
        "average_view_duration_seconds",
        "average_view_percentage",
        "watch_time_minutes",
        "returning_viewers",
        "subscribers_gained",
        "subscribers_lost",
        "estimated_revenue",
    ):
        numeric[key] = _finite(raw.get(key))

    return {
        "schema_version": "empire.media.owned_analytics.v1",
        "mode": "OBSERVE",
        "channel_id": raw.get("channel_id"),
        "video_id": raw.get("video_id"),
        "metrics": numeric,
        "traffic_sources": list(raw.get("traffic_sources") or []),
        "search_terms": list(raw.get("search_terms") or []),
        "suggested_video_sources": list(
            raw.get("suggested_video_sources") or []
        ),
        "geography": list(raw.get("geography") or []),
        "device": list(raw.get("device") or []),
        "playlist_behavior": list(raw.get("playlist_behavior") or []),
        "evidence_refs": refs,
        "owned_authorized_source_required": True,
        "revenue_truth_owner": "revenue_pulse",
        "estimated_revenue_is_platform_metric_only": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def analyse_retention(
    points: Iterable[RetentionPoint],
    *,
    scene_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    drop_threshold: float = 0.08,
) -> dict[str, Any]:
    rows = sorted(
        [point.as_dict() for point in points],
        key=lambda row: row["second"],
    )
    metadata = dict(scene_metadata or {})
    drops: list[dict[str, Any]] = []

    for before, after in zip(rows, rows[1:]):
        delta = after["audience_retention"] - before["audience_retention"]
        if delta > -abs(float(drop_threshold)):
            continue
        scene_id = after.get("scene_id") or before.get("scene_id")
        context = dict(metadata.get(scene_id) or {})
        hypotheses = []
        if context.get("static_frame") is True:
            hypotheses.append("static_frame")
        if context.get("explanation_seconds", 0) and float(
            context.get("explanation_seconds", 0)
        ) >= 15:
            hypotheses.append("long_explanation")
        if context.get("promise_delayed") is True:
            hypotheses.append("promise_delayed")
        drops.append({
            "from_second": before["second"],
            "to_second": after["second"],
            "retention_delta": round(delta, 4),
            "scene_id": scene_id,
            "hypotheses": hypotheses,
            "causal_claim": False,
        })

    return {
        "schema_version": "empire.media.retention_analysis.v1",
        "mode": "OBSERVE",
        "point_count": len(rows),
        "drop_count": len(drops),
        "drops": drops,
        "hypotheses_not_causal_findings": True,
        "experiment_review_owner": "experiment_intelligence",
        "public_action_performed": False,
        "execution_authority": "none",
    }


def shorts_to_long_form_funnel(
    *,
    short_views: int | None,
    subscribers_gained: int | None,
    channel_visits: int | None,
    long_form_continuations: int | None,
    returning_viewers: int | None,
    website_visits: int | None,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]
    if not refs:
        raise ValueError("shorts funnel evidence_refs are required")

    return {
        "schema_version": "empire.media.shorts_funnel.v1",
        "mode": "OBSERVE",
        "short_views": short_views,
        "subscribers_gained": subscribers_gained,
        "channel_visits": channel_visits,
        "long_form_continuations": long_form_continuations,
        "returning_viewers": returning_viewers,
        "website_visits": website_visits,
        "evidence_refs": refs,
        "optimized_for_raw_views_only": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }
