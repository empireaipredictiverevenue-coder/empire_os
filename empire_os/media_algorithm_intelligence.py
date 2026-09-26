"""Algorithm Intelligence for Empire Media OS.

This module learns from observed distribution and owned-channel analytics.
It does not claim to reproduce or know private YouTube ranking weights.

Responsibilities:
- surface-level distribution analysis (Search/Browse/Suggested/Shorts/etc.);
- observed recommendation-chain packets;
- rolling-baseline drift detection;
- evidence-linked algorithm hypotheses for Quant/Experiment review.

No public action, no engagement manipulation, no fake ranking certainty.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from statistics import median
from typing import Any, Iterable, Mapping


SURFACES = frozenset({
    "SEARCH",
    "BROWSE",
    "SUGGESTED",
    "SHORTS_FEED",
    "CHANNEL_PAGE",
    "NOTIFICATIONS",
    "PLAYLIST",
    "EXTERNAL",
    "DIRECT_OR_UNKNOWN",
})

SURFACE_METRICS = (
    "impressions",
    "views",
    "engaged_views",
    "watch_time_minutes",
    "average_view_duration_seconds",
    "average_view_percentage",
    "subscribers_gained",
    "returning_viewers",
)


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _rate(numerator: Any, denominator: Any) -> float | None:
    top = _number(numerator)
    bottom = _number(denominator)
    if top is None or bottom is None or bottom <= 0:
        return None
    return round(top / bottom, 6)


@dataclass(frozen=True)
class DistributionObservation:
    video_id: str
    surface: str
    evidence_refs: tuple[str, ...]
    impressions: float | None = None
    views: float | None = None
    engaged_views: float | None = None
    watch_time_minutes: float | None = None
    average_view_duration_seconds: float | None = None
    average_view_percentage: float | None = None
    subscribers_gained: float | None = None
    returning_viewers: float | None = None
    source_video_id: str | None = None
    query: str | None = None
    audience_cluster_ref: str | None = None

    def validate(self) -> None:
        if not self.video_id.strip():
            raise ValueError("video_id is required")
        if self.surface not in SURFACES:
            raise ValueError("unsupported distribution surface")
        if not self.evidence_refs:
            raise ValueError("distribution evidence_refs are required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        row = asdict(self)
        for key in SURFACE_METRICS:
            row[key] = _number(row.get(key))
        row["impressions_ctr"] = _rate(
            row.get("views"),
            row.get("impressions"),
        )
        row["subscriber_view_rate"] = _rate(
            row.get("subscribers_gained"),
            row.get("views"),
        )
        return row


def analyse_distribution(
    observations: Iterable[DistributionObservation],
) -> dict[str, Any]:
    rows = [row.as_dict() for row in observations]

    by_surface: dict[str, dict[str, Any]] = {}
    total_views = sum(
        float(row.get("views") or 0.0)
        for row in rows
    )

    for surface in sorted(SURFACES):
        subset = [row for row in rows if row["surface"] == surface]
        if not subset:
            continue

        metrics: dict[str, float | None] = {}
        for key in SURFACE_METRICS:
            values = [
                float(row[key])
                for row in subset
                if row.get(key) is not None
            ]
            metrics[key] = (
                round(sum(values), 6)
                if values
                and key in {
                    "impressions",
                    "views",
                    "engaged_views",
                    "watch_time_minutes",
                    "subscribers_gained",
                    "returning_viewers",
                }
                else round(sum(values) / len(values), 6)
                if values
                else None
            )

        surface_views = metrics["views"] or 0.0
        metrics["view_share"] = (
            round(surface_views / total_views, 6)
            if total_views > 0
            else None
        )
        metrics["impressions_ctr"] = _rate(
            metrics.get("views"),
            metrics.get("impressions"),
        )
        metrics["subscriber_view_rate"] = _rate(
            metrics.get("subscribers_gained"),
            metrics.get("views"),
        )

        by_surface[surface] = {
            "observation_count": len(subset),
            "metrics": metrics,
        }

    return {
        "schema_version": "empire.media.algorithm_distribution.v1",
        "mode": "OBSERVE",
        "observation_count": len(rows),
        "surface_count": len(by_surface),
        "surfaces": by_surface,
        "private_platform_weights_known": False,
        "ranking_probability_created": False,
        "distribution_observation_only": True,
        "manipulative_engagement_authorized": False,
        "execution_authority": "none",
    }


def build_surface_baseline(
    historical_distributions: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in historical_distributions]
    result: dict[str, Any] = {}

    for surface in sorted(SURFACES):
        samples: dict[str, list[float]] = {
            "view_share": [],
            "impressions_ctr": [],
            "average_view_percentage": [],
            "subscriber_view_rate": [],
        }
        for raw in rows:
            surface_row = (
                (raw.get("surfaces") or {}).get(surface) or {}
            )
            metrics = surface_row.get("metrics") or {}
            for key in samples:
                value = _number(metrics.get(key))
                if value is not None:
                    samples[key].append(value)

        if not any(samples.values()):
            continue

        result[surface] = {
            key: (
                round(float(median(values)), 6)
                if values
                else None
            )
            for key, values in samples.items()
        }
        result[surface]["sample_count"] = max(
            (len(values) for values in samples.values()),
            default=0,
        )

    return {
        "schema_version": "empire.media.algorithm_surface_baseline.v1",
        "surface_baselines": result,
        "method": "observed_median",
        "private_platform_weights_known": False,
        "execution_authority": "none",
    }


def detect_distribution_drift(
    *,
    current: Mapping[str, Any],
    baseline: Mapping[str, Any],
    material_delta: float = 0.20,
) -> dict[str, Any]:
    current_surfaces = current.get("surfaces") or {}
    baseline_surfaces = baseline.get("surface_baselines") or {}

    changes = []
    for surface in sorted(
        set(current_surfaces) | set(baseline_surfaces)
    ):
        now = (
            (current_surfaces.get(surface) or {}).get("metrics") or {}
        )
        before = baseline_surfaces.get(surface) or {}

        for metric in (
            "view_share",
            "impressions_ctr",
            "average_view_percentage",
            "subscriber_view_rate",
        ):
            current_value = _number(now.get(metric))
            baseline_value = _number(before.get(metric))
            if current_value is None or baseline_value is None:
                continue

            absolute_delta = current_value - baseline_value
            relative_delta = (
                absolute_delta / abs(baseline_value)
                if baseline_value != 0
                else None
            )
            material = (
                relative_delta is not None
                and abs(relative_delta) >= abs(float(material_delta))
            )

            if material:
                changes.append({
                    "surface": surface,
                    "metric": metric,
                    "baseline": baseline_value,
                    "current": current_value,
                    "absolute_delta": round(absolute_delta, 6),
                    "relative_delta": round(relative_delta, 6),
                    "material": True,
                })

    return {
        "schema_version": "empire.media.algorithm_drift.v1",
        "mode": "OBSERVE",
        "material_change_count": len(changes),
        "changes": changes,
        "state": (
            "DISTRIBUTION_SHIFT_CANDIDATE"
            if changes
            else "NO_MATERIAL_SHIFT_OBSERVED"
        ),
        "platform_algorithm_change_claimed": False,
        "causal_explanation_created": False,
        "experiment_review_required": bool(changes),
        "execution_authority": "none",
    }


def build_recommendation_chain_packet(
    observations: Iterable[DistributionObservation],
) -> dict[str, Any]:
    edges = []
    for observation in observations:
        row = observation.as_dict()
        if (
            row["surface"] != "SUGGESTED"
            or not row.get("source_video_id")
        ):
            continue
        edges.append({
            "source_video_id": row["source_video_id"],
            "target_video_id": row["video_id"],
            "views": row.get("views"),
            "engaged_views": row.get("engaged_views"),
            "watch_time_minutes": row.get("watch_time_minutes"),
            "evidence_refs": list(row["evidence_refs"]),
        })

    return {
        "schema_version": "empire.media.recommendation_chain.v1",
        "mode": "OBSERVE",
        "edge_count": len(edges),
        "edges": edges,
        "graph_owner": "intelligence_fabric",
        "observed_edges_only": True,
        "private_recommendation_graph_claimed": False,
        "execution_authority": "none",
    }


def build_algorithm_hypothesis_packet(
    *,
    video_id: str,
    distribution: Mapping[str, Any],
    retention_ref: str | None,
    creative_package_ref: str | None,
    audience_cluster_ref: str | None,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [str(x).strip() for x in evidence_refs if str(x).strip()]
    if not str(video_id or "").strip():
        raise ValueError("video_id is required")
    if not refs:
        raise ValueError("algorithm hypothesis evidence_refs are required")

    observed_surfaces = sorted(
        (distribution.get("surfaces") or {}).keys()
    )

    return {
        "schema_version": "empire.media.algorithm_hypothesis.v1",
        "mode": "OBSERVE",
        "video_id": video_id,
        "observed_surfaces": observed_surfaces,
        "retention_ref": retention_ref,
        "creative_package_ref": creative_package_ref,
        "audience_cluster_ref": audience_cluster_ref,
        "evidence_refs": refs,
        "hypothesis_dimensions": [
            "surface_fit",
            "audience_match",
            "creative_package_fit",
            "retention_shape",
            "session_continuation",
            "topic_cluster_strength",
        ],
        "ranking_probability": None,
        "private_algorithm_weights_known": False,
        "causal_claim_created": False,
        "review_owner": "experiment_intelligence",
        "portfolio_owner": "quant_brain",
        "public_action_authorized": False,
        "execution_authority": "none",
    }
