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


# Public video descriptions supply creator-labelled chapters, not a transcript.
_CHAPTER_LINE = re.compile(
    r"^\s*(?P<clock>(?:\d{1,2}:)?\d{1,2}:\d{2})[ \t\\-–—]+(?P<label>[^\r\n]{3,180})\s*$"
)
_YOUTUBE_WORKFLOW_LABELS = {
    "prompt_quality": ("prompt", "instruction", "teach", "mistake", "example"),
    "workflow_library": ("workflow", "github", "automating", "reus", "combine"),
    "avatar_presenter": ("face", "voice", "talking", "avatar"),
    "edit_animation": ("animation", "film", "video style", "vertical", "export"),
    "source_analysis": ("youtube video", "reference video"),
}


def extract_creator_chapters(description: str) -> list[dict[str, Any]]:
    """Parse official-description chapter labels without inventing scenes."""
    if len(str(description or "")) > 100_000:
        raise ValueError("YouTube description exceeds review bound")
    chapters: list[dict[str, Any]] = []
    last = -1
    for line in str(description or "").splitlines():
        match = _CHAPTER_LINE.match(line)
        if not match:
            continue
        units = [int(x) for x in match["clock"].split(":")]
        if any(x >= 60 for x in units[1:]):
            continue
        seconds = sum(part * 60 ** power for power, part in enumerate(reversed(units)))
        if seconds <= last or seconds > 12 * 3600:
            continue
        label = match["label"].strip()
        if not label:
            continue
        tag = []
        low = label.lower()
        for category, keywords in _YOUTUBE_WORKFLOW_LABELS.items():
            if any(key in low for key in keywords):
                tag.append(category)
        chapters.append({
            "at_seconds": seconds,
            "at": match["clock"],
            "creator_label": label,
            "workflow_topics": tag,
            "evidence_type": "CREATOR_PUBLISHED_DESCRIPTION_ONLY",
            "observed_video_content": False,
        })
        last = seconds
    return chapters


def youtube_inspiration_review(
    *,
    video_id: str,
    title: str,
    creator: str,
    published_description: str = "",
) -> dict[str, Any]:
    """Review-labelled ideas, not a claim of having watched or transcribed."""
    from empire_os.youtube_read_adapter import normalize_youtube_video_id
    validated_id = normalize_youtube_video_id(video_id)
    chapters = extract_creator_chapters(published_description)
    topics = sorted({topic for row in chapters for topic in row["workflow_topics"]})
    return {
        "schema_version": "empire.media.youtube_inspiration_review.v1",
        "mode": "OBSERVE",
        "video_id": validated_id,
        "watch_url": "https://www.youtube.com/watch?v=" + validated_id,
        "title": str(title).strip(),
        "creator": str(creator).strip(),
        "chapters": chapters,
        "workflow_topics": topics,
        "chapter_count": len(chapters),
        "transcript_obtained": False,
        "visual_scenes_observed": False,
        "voice_or_face_downloaded": False,
        "claims_verified_from_chapters": False,
        "ideas_are_unverified_candidates": True,
        "production_auto_publish": False,
        "execution_authority": "none",
        "evidence_refs": ["youtube:video_description:" + validated_id] if published_description else [],
    }


# Existing YouTube Intelligence -> Empire commercial prioritisation. NO new queue.
EMPIRE_VIDEO_VERTICAL_TERMS = {
    "roofing": ("roofing", "roofer", "roof repair", "roof replacement"),
    "solar": ("solar", "photovoltaic", "pv installation"),
    "hvac": ("hvac", "heat pump", "air conditioning", "furnace"),
    "dental": ("dental", "dentist", "dentistry"),
    "ai_consultancy": ("ai consultancy", "ai consulting", "ai strategy", "business automation"),
    "enterprise_ai": ("enterprise ai", "predictive revenue", "revenue intelligence"),
}
EMPIRE_VIDEO_MARKET_CUES = {
    "UK": ("uk", "united kingdom", "britain", "british", "london", "manchester", "bolton"),
    "USA": ("usa", "united states", "america", "us roofing", "texas", "chicago", "new york"),
}


def review_youtube_commercial_opportunities(
    observations: Iterable[Mapping[str, Any]],
    *,
    commercial_capacity: Mapping[str, Mapping[str, Any]] | None = None,
    now: datetime | None = None,
    max_observation_age_hours: int = 48,
    max_video_age_days: int = 90,
    minimum_outlier_ratio: float = 2.0,
    limit: int = 20,
) -> dict[str, Any]:
    """Rank *research*, not revenue, using only normalized YouTube observations.

    Existing buyer-capacity status is informative, never an execution gate
    grant. Numbers are descriptive heuristics, not view or sales forecasts.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("timezone-aware now required")
    moment = moment.astimezone(timezone.utc)
    if not 1 <= int(limit) <= 100:
        raise ValueError("opportunity review limit out of bounds")
    if not 1 <= max_observation_age_hours <= 24 * 14:
        raise ValueError("invalid observation freshness window")
    if not 1 <= max_video_age_days <= 365:
        raise ValueError("invalid publication window")
    if not 1 <= float(minimum_outlier_ratio) <= 100:
        raise ValueError("invalid baseline threshold")

    def parsed(raw: Any) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)

    def matches(text: str, term: str) -> bool:
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text))

    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    count = 0
    for row in observations:
        count += 1
        if count > 2000:
            raise ValueError("bounded research observations exceeded")
        if not isinstance(row, Mapping) or row.get("schema_version") != "empire.media.youtube_video_observation.v1":
            raise ValueError("normalized video observation required")
        ref = row.get("video_id")
        if not isinstance(ref, str) or not ref.strip() or len(ref) > 128:
            raise ValueError("video id required")
        if ref in seen:
            excluded["duplicate_video_id"] = excluded.get("duplicate_video_id", 0) + 1
            continue
        seen.add(ref)
        reasons = []
        evidence = row.get("evidence_refs")
        if not isinstance(evidence, (list, tuple)) or not any(isinstance(x, str) and x.strip() for x in evidence):
            reasons.append("NO_SOURCE_EVIDENCE")
        title = str(row.get("title") or "").lower()
        description = str(row.get("description") or "").lower()
        verticals = [
            name for name, terms in EMPIRE_VIDEO_VERTICAL_TERMS.items()
            if any(matches(title, term) for term in terms)
        ]
        # Description alone is not enough to declare the main video topic.
        if not verticals:
            reasons.append("NO_TITLE_LEVEL_VERTICAL_MATCH")
        market_text = title + " " + description
        market_cues = [
            market for market, terms in EMPIRE_VIDEO_MARKET_CUES.items()
            if any(matches(market_text, term) for term in terms)
        ]
        observed_at = parsed(row.get("observed_at"))
        published_at = parsed(row.get("published_at"))
        # A normalization within the same batch can postdate a caller-captured
        # clock by milliseconds. Permit up to 60 seconds of bounded skew.
        if observed_at is None or not -60 <= (moment - observed_at).total_seconds() <= 3600 * max_observation_age_hours:
            reasons.append("STALE_OR_UNKNOWN_OBSERVATION")
        if published_at is None or not 0 <= (moment - published_at).total_seconds() <= 86400 * max_video_age_days:
            reasons.append("STALE_OR_UNKNOWN_PUBLICATION")
        baseline = row.get("channel_baseline")
        metric = row.get("primary_performance_metric")
        ratio = None
        if isinstance(baseline, Mapping) and baseline.get("baseline_state") == "OBSERVED_MEDIAN" and baseline.get("metric") == metric and isinstance(baseline.get("sample_size"), int) and baseline["sample_size"] >= MIN_BASELINE_VIDEOS:
            ratio = outlier_ratio(row.get("primary_performance_value"), baseline.get("value"))
        if ratio is None:
            reasons.append("NO_COMPARABLE_CHANNEL_BASELINE")
        elif ratio < minimum_outlier_ratio:
            reasons.append("BELOW_OUTLIER_THRESHOLD")

        if reasons:
            for reason in reasons:
                excluded[reason] = excluded.get(reason, 0) + 1
            continue
        # No invented market certainty from words in a video title/description.
        sector = verticals[0]
        capacity = (commercial_capacity or {}).get(sector, {})
        if not isinstance(capacity, Mapping):
            raise ValueError("commercial capacity entries must be mappings")
        status = str(capacity.get("status") or "NOT_VERIFIED")
        if status not in {"NOT_VERIFIED", "NO_VERIFIED_CAPACITY", "TERMS_PENDING", "VERIFIED_CAPACITY"}:
            raise ValueError("unrecognized buyer capacity state")
        capacity_refs = capacity.get("evidence_refs") or []
        if status == "VERIFIED_CAPACITY" and not capacity_refs:
            status = "NOT_VERIFIED"
        age_days = round((moment - published_at).total_seconds() / 86400, 2)
        # Priority is an editorial heuristic, not a performance or cash projection.
        priority = (
            "HIGH_SIGNAL_REVIEW" if ratio >= 3 and market_cues
            else "RESEARCH_REVIEW"
        )
        candidates.append({
            "video_id": ref,
            "title": row.get("title"),
            "channel_id": row.get("channel_id"),
            "vertical": sector,
            "matched_verticals": verticals,
            "market_cues_not_territory_proof": market_cues,
            "published_age_days": age_days,
            "outlier_ratio_descriptive": ratio,
            "priority": priority,
            "upstream_reported_buyer_capacity_status": status,
            "buyer_capacity_evidence_refs": list(capacity_refs),
            "buyer_capacity_independently_verified_here": False,
            "suggested_next_step": (
                "REVIEW_EVIDENCE_AND_EDITORIAL_ANGLE" if status == "VERIFIED_CAPACITY"
                else "RESEARCH_EDUCATIONAL_CONTENT_NO_PAYABLE_LEAD_CLAIMS"
            ),
            "evidence_refs": [str(x) for x in evidence if isinstance(x, str) and x.strip()],
            "competitor_transcript_verified": bool(row.get("transcript_ref")),
            "commercial_buyer_intent_verified": False,
            "revenue_proven": False,
            "public_publish_authorized": False,
        })
    candidates.sort(key=lambda item: (
        item["priority"] != "HIGH_SIGNAL_REVIEW",
        -float(item["outlier_ratio_descriptive"]),
        item["published_age_days"],
        item["video_id"],
    ))
    return {
        "schema_version": "empire.media.youtube_commercial_opportunities.v1",
        "mode": "OBSERVE",
        "observation_count": count,
        "unique_video_count": len(seen),
        "candidate_count": len(candidates),
        "candidates": candidates[:limit],
        "excluded_reason_counts": dict(sorted(excluded.items())),
        "comparison_method": "CHANNEL_MEDIAN_OUTLIER_HEURISTIC_NOT_AGE_NORMALIZED",
        "performance_benchmark_against_vidiq_proven": False,
        "owned_channel_conversion_attribution_proven": False,
        "revenue_recognized": False,
        "commercial_activation_authorized": False,
        "automatic_video_generation_authorized": False,
        "automatic_publication_authorized": False,
        "execution_authority": "none",
    }
