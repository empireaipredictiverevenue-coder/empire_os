"""Cross-source trend fusion for Empire Media OS.

Trend Fusion consumes observations from existing Empire intelligence systems.
It does not crawl sources itself and does not convert attention into buyer
intent, revenue, or publishing authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Iterable


SUPPORTED_SIGNAL_FAMILIES = frozenset({
    "youtube",
    "search",
    "empire_serp",
    "community",
    "news",
    "competitor",
    "buyer_conversation",
    "crm",
    "website_traffic",
    "product_usage",
    "industry_signal",
})


def _bounded(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return max(-1.0, min(1.0, number))


@dataclass(frozen=True)
class MediaTrendSignal:
    topic: str
    source_family: str
    velocity: float | None
    evidence_refs: tuple[str, ...]
    observed_at: str | None = None
    source_component: str | None = None

    def validate(self) -> None:
        if not self.topic.strip():
            raise ValueError("trend signal topic is required")
        if self.source_family not in SUPPORTED_SIGNAL_FAMILIES:
            raise ValueError("unsupported trend source_family")
        if not self.evidence_refs:
            raise ValueError("trend signal evidence_refs are required")
        if self.velocity is not None and _bounded(self.velocity) is None:
            raise ValueError("trend signal velocity must be finite")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "topic": self.topic.strip(),
            "source_family": self.source_family,
            "velocity": _bounded(self.velocity),
            "evidence_refs": list(self.evidence_refs),
            "observed_at": self.observed_at,
            "source_component": self.source_component,
        }


def fuse_media_trend(
    topic: str,
    signals: Iterable[MediaTrendSignal],
) -> dict[str, Any]:
    """Fuse independent observed trend signals into a media research state.

    The returned strength is a descriptive multi-source heuristic, not a
    purchase probability, revenue forecast, or causal conclusion.
    """
    target = str(topic or "").strip()
    if not target:
        raise ValueError("trend topic is required")

    rows: list[dict[str, Any]] = []
    for signal in signals:
        signal.validate()
        if signal.topic.strip().lower() != target.lower():
            continue
        rows.append(signal.as_dict())

    families = sorted({
        str(row["source_family"])
        for row in rows
    })
    velocities = [
        float(row["velocity"])
        for row in rows
        if row.get("velocity") is not None
    ]
    positive_families = sorted({
        str(row["source_family"])
        for row in rows
        if row.get("velocity") is not None
        and float(row["velocity"]) > 0
    })
    accelerating_families = sorted({
        str(row["source_family"])
        for row in rows
        if row.get("velocity") is not None
        and float(row["velocity"]) >= 0.25
    })

    mean_velocity = (
        round(sum(velocities) / len(velocities), 4)
        if velocities
        else None
    )

    if len(accelerating_families) >= 3:
        state = "MULTISOURCE_ACCELERATION"
    elif len(accelerating_families) >= 2:
        state = "CROSS_SOURCE_ACCELERATION"
    elif len(positive_families) >= 1:
        state = "SINGLE_OR_WEAK_POSITIVE_SIGNAL"
    elif rows:
        state = "OBSERVED_NO_ACCELERATION"
    else:
        state = "UNKNOWN"

    evidence_refs = sorted({
        ref
        for row in rows
        for ref in row.get("evidence_refs") or []
        if ref
    })

    return {
        "schema_version": "empire.media.trend_fusion.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": target,
        "signal_count": len(rows),
        "source_family_count": len(families),
        "source_families": families,
        "positive_source_families": positive_families,
        "accelerating_source_families": accelerating_families,
        "mean_observed_velocity": mean_velocity,
        "trend_state": state,
        "classification": "DESCRIPTIVE_HEURISTIC",
        "evidence_refs": evidence_refs,
        "high_confidence_claim_created": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "revenue_inferred": False,
        "media_publish_authorized": False,
        "execution_authority": "none",
    }
