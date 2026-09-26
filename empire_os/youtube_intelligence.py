"""YouTube intelligence normalization and outlier analysis for Media OS.

This module contains deterministic analysis only. It does not scrape YouTube,
does not publish, and does not create buyer intent or revenue claims.

Public Data API observations and authorised owned-channel Analytics observations
should enter through adapters and preserve their source/evidence references.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from statistics import median
from typing import Any, Iterable, Mapping


VIEW_COUNT_SEMANTICS_CHANGE_DATE = "2026-08-24"
DEFAULT_OUTLIER_RATIO = 2.0
MIN_BASELINE_VIDEOS = 3


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?$"
)


def parse_iso8601_duration_seconds(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _DURATION_RE.match(text)
    if not match:
        return None
    parts = {
        key: int(raw or 0)
        for key, raw in match.groupdict().items()
    }
    return (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )


@dataclass(frozen=True)
class YouTubeBaseline:
    metric: str
    value: float | None
    sample_size: int
    baseline_state: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": self.value,
            "sample_size": self.sample_size,
            "baseline_state": self.baseline_state,
        }


def build_channel_baseline(
    values: Iterable[Any],
    *,
    metric: str = "views",
    minimum_samples: int = MIN_BASELINE_VIDEOS,
) -> YouTubeBaseline:
    observed = [
        value
        for raw in values
        if (value := _float_or_none(raw)) is not None
    ]
    if len(observed) < max(1, int(minimum_samples)):
        return YouTubeBaseline(
            metric=metric,
            value=None,
            sample_size=len(observed),
            baseline_state="INSUFFICIENT_EVIDENCE",
        )

    return YouTubeBaseline(
        metric=metric,
        value=float(median(observed)),
        sample_size=len(observed),
        baseline_state="OBSERVED_MEDIAN",
    )


def outlier_ratio(
    performance: Any,
    baseline: Any,
) -> float | None:
    perf = _float_or_none(performance)
    base = _float_or_none(baseline)
    if perf is None or base is None or base <= 0:
        return None
    return round(perf / base, 4)


def _safe_rate(numerator: Any, denominator: Any) -> float | None:
    num = _float_or_none(numerator)
    den = _float_or_none(denominator)
    if num is None or den is None or den <= 0:
        return None
    return round(num / den, 6)


def normalize_youtube_video_observation(
    raw: Mapping[str, Any],
    *,
    evidence_refs: Iterable[str],
    owned_channel: bool = False,
    channel_baseline: YouTubeBaseline | None = None,
) -> dict[str, Any]:
    """Normalize public/authorised YouTube observations.

    The input may be a flattened adapter record or a partial YouTube Data API
    resource. Missing values stay None.
    """
    refs = [
        str(ref).strip()
        for ref in evidence_refs
        if str(ref).strip()
    ]
    if not refs:
        raise ValueError("youtube observation requires evidence_refs")

    snippet = (
        dict(raw.get("snippet"))
        if isinstance(raw.get("snippet"), Mapping)
        else {}
    )
    stats = (
        dict(raw.get("statistics"))
        if isinstance(raw.get("statistics"), Mapping)
        else {}
    )
    details = (
        dict(raw.get("contentDetails"))
        if isinstance(raw.get("contentDetails"), Mapping)
        else {}
    )
    analytics = (
        dict(raw.get("analytics"))
        if isinstance(raw.get("analytics"), Mapping)
        else {}
    )

    video_id = str(raw.get("video_id") or raw.get("id") or "").strip()
    channel_id = str(
        raw.get("channel_id")
        or snippet.get("channelId")
        or ""
    ).strip()

    views = _int_or_none(
        raw.get("views")
        if raw.get("views") is not None
        else stats.get("viewCount")
    )
    likes = _int_or_none(
        raw.get("likes")
        if raw.get("likes") is not None
        else stats.get("likeCount")
    )
    comments = _int_or_none(
        raw.get("comments")
        if raw.get("comments") is not None
        else stats.get("commentCount")
    )

    duration = _int_or_none(raw.get("duration_seconds"))
    if duration is None:
        duration = parse_iso8601_duration_seconds(
            str(details.get("duration") or "")
        )

    # Owned-channel analytics are accepted only when the adapter explicitly
    # marks the channel as authorised/owned.
    owned_metrics = {
        "impressions": None,
        "impressions_ctr": None,
        "engaged_views": None,
        "watch_time_minutes": None,
        "average_view_duration_seconds": None,
        "average_view_percentage": None,
        "subscribers_gained": None,
        "subscribers_lost": None,
        "returning_viewers": None,
    }
    if owned_channel:
        owned_metrics = {
            "impressions": _int_or_none(analytics.get("impressions")),
            "impressions_ctr": _float_or_none(
                analytics.get("impressions_ctr")
            ),
            "engaged_views": _int_or_none(
                analytics.get("engaged_views")
            ),
            "watch_time_minutes": _float_or_none(
                analytics.get("watch_time_minutes")
            ),
            "average_view_duration_seconds": _float_or_none(
                analytics.get("average_view_duration_seconds")
            ),
            "average_view_percentage": _float_or_none(
                analytics.get("average_view_percentage")
            ),
            "subscribers_gained": _int_or_none(
                analytics.get("subscribers_gained")
            ),
            "subscribers_lost": _int_or_none(
                analytics.get("subscribers_lost")
            ),
            "returning_viewers": _int_or_none(
                analytics.get("returning_viewers")
            ),
        }

    baseline = channel_baseline or YouTubeBaseline(
        metric="views",
        value=None,
        sample_size=0,
        baseline_state="UNKNOWN",
    )

    primary_performance = views
    primary_metric = "views"
    if owned_channel and owned_metrics["engaged_views"] is not None:
        primary_performance = owned_metrics["engaged_views"]
        primary_metric = "engaged_views"

    ratio = (
        outlier_ratio(primary_performance, baseline.value)
        if baseline.metric == primary_metric
        else None
    )

    outlier_state = "UNKNOWN"
    if ratio is not None:
        outlier_state = (
            "OUTLIER_CANDIDATE"
            if ratio >= DEFAULT_OUTLIER_RATIO
            else "WITHIN_BASELINE"
        )

    published_at = str(
        raw.get("published_at")
        or snippet.get("publishedAt")
        or ""
    ).strip() or None

    return {
        "schema_version": "empire.media.youtube_video_observation.v1",
        "mode": "OBSERVE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "video_id": video_id or None,
        "channel_id": channel_id or None,
        "title": str(
            raw.get("title") or snippet.get("title") or ""
        ).strip() or None,
        "description": str(
            raw.get("description") or snippet.get("description") or ""
        ).strip() or None,
        "published_at": published_at,
        "duration_seconds": duration,
        "views": views,
        "likes": likes,
        "comments": comments,
        "like_view_rate": _safe_rate(likes, views),
        "comment_view_rate": _safe_rate(comments, views),
        "owned_channel": bool(owned_channel),
        "owned_analytics": owned_metrics,
        "primary_performance_metric": primary_metric,
        "primary_performance_value": primary_performance,
        "channel_baseline": baseline.as_dict(),
        "outlier_ratio": ratio,
        "outlier_state": outlier_state,
        "outlier_threshold": DEFAULT_OUTLIER_RATIO,
        "outlier_classification": "HEURISTIC",
        "transcript_ref": (
            str(raw.get("transcript_ref") or "").strip() or None
        ),
        "chapter_count": _int_or_none(raw.get("chapter_count")),
        "thumbnail_refs": [
            str(value).strip()
            for value in (raw.get("thumbnail_refs") or [])
            if str(value).strip()
        ],
        "topic_refs": [
            str(value).strip()
            for value in (raw.get("topic_refs") or [])
            if str(value).strip()
        ],
        "entity_refs": [
            str(value).strip()
            for value in (raw.get("entity_refs") or [])
            if str(value).strip()
        ],
        "product_refs": [
            str(value).strip()
            for value in (raw.get("product_refs") or [])
            if str(value).strip()
        ],
        "evidence_refs": refs,
        "view_count_semantics": {
            "change_date": VIEW_COUNT_SEMANTICS_CHANGE_DATE,
            "cross_period_comparison_requires_review": True,
            "preferred_owned_metric_when_available": "engaged_views",
        },
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "revenue_inferred": False,
        "actual_revenue": False,
        "public_action_performed": False,
        "execution_authority": "none",
    }


def build_outlier_candidates(
    observations: Iterable[Mapping[str, Any]],
    *,
    minimum_ratio: float = DEFAULT_OUTLIER_RATIO,
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in observations
        if isinstance(row, Mapping)
    ]
    threshold = max(1.0, float(minimum_ratio))
    candidates = [
        row
        for row in rows
        if (
            _float_or_none(row.get("outlier_ratio")) is not None
            and float(row["outlier_ratio"]) >= threshold
        )
    ]
    candidates.sort(
        key=lambda row: (
            -float(row.get("outlier_ratio") or 0),
            str(row.get("video_id") or ""),
        )
    )

    return {
        "schema_version": "empire.media.youtube_outliers.v1",
        "mode": "OBSERVE",
        "observation_count": len(rows),
        "candidate_count": len(candidates),
        "threshold": threshold,
        "classification": "HEURISTIC_CANDIDATE_ONLY",
        "candidates": candidates,
        "copy_competitor_creative_authorized": False,
        "public_action_performed": False,
        "execution_authority": "none",
    }
