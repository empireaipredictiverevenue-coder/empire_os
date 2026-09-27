"""Evidence-bounded media attribution for Empire Media OS.

Revenue Pulse remains the canonical revenue-truth owner. This module records
links only when source evidence exists; unknown attribution remains unknown.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class MediaAttributionLink:
    link_id: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    evidence_refs: tuple[str, ...]
    attribution_method: str
    confidence: float | None = None

    def validate(self) -> None:
        if not self.link_id.strip():
            raise ValueError("attribution link_id is required")
        if self.source_type not in {"VIDEO", "SHORT", "CHANNEL", "CAMPAIGN"}:
            raise ValueError("unsupported attribution source_type")
        if self.target_type not in {
            "SESSION",
            "LEAD",
            "OPPORTUNITY",
            "SALE",
            "REVENUE",
        }:
            raise ValueError("unsupported attribution target_type")
        if not self.source_id.strip() or not self.target_id.strip():
            raise ValueError("attribution endpoint ids are required")
        if not self.evidence_refs:
            raise ValueError("attribution evidence_refs are required")
        if self.confidence is not None and not (
            0.0 <= float(self.confidence) <= 1.0
        ):
            raise ValueError("attribution confidence must be within 0..1")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_media_attribution_packet(
    *,
    links: Iterable[MediaAttributionLink],
    recognized_revenue_cents: int | None = None,
    revenue_evidence_refs: Iterable[str] = (),
) -> dict[str, Any]:
    rows = [link.as_dict() for link in links]
    revenue_refs = [
        str(ref).strip()
        for ref in revenue_evidence_refs
        if str(ref).strip()
    ]

    if recognized_revenue_cents is not None:
        value = int(recognized_revenue_cents)
        if value < 0:
            raise ValueError("recognized revenue cannot be negative")
        if not revenue_refs:
            raise ValueError(
                "recognized revenue requires revenue_evidence_refs"
            )
    else:
        value = None

    has_revenue_link = any(
        row["target_type"] == "REVENUE"
        for row in rows
    )

    attributed_revenue_state = "UNKNOWN"
    if value is not None and has_revenue_link and revenue_refs:
        attributed_revenue_state = "OBSERVED_EVIDENCE_LINKED"
    elif value is not None:
        attributed_revenue_state = "REVENUE_OBSERVED_ATTRIBUTION_UNKNOWN"

    return {
        "schema_version": "empire.media.attribution.v1",
        "mode": "OBSERVE",
        "link_count": len(rows),
        "links": rows,
        "recognized_revenue_cents": value,
        "revenue_evidence_refs": revenue_refs,
        "attributed_revenue_state": attributed_revenue_state,
        "revenue_truth_owner": "revenue_pulse",
        "unknown_remains_unknown": True,
        "actual_revenue_claim_created_by_media_os": False,
        "execution_authority": "none",
    }


def content_value_feature_packet(
    *,
    views: float | None = None,
    watch_time_minutes: float | None = None,
    subscribers_gained: float | None = None,
    returning_viewers: float | None = None,
    search_longevity: float | None = None,
    leads: float | None = None,
    pipeline_cents: float | None = None,
    recognized_revenue_cents: float | None = None,
    product_adoption: float | None = None,
    authority_signal: float | None = None,
    production_cost_cents: float | None = None,
    evidence_refs: Iterable[str],
) -> dict[str, Any]:
    refs = [str(ref).strip() for ref in evidence_refs if str(ref).strip()]
    if not refs:
        raise ValueError("content value evidence_refs are required")

    values = {
        "views": views,
        "watch_time_minutes": watch_time_minutes,
        "subscribers_gained": subscribers_gained,
        "returning_viewers": returning_viewers,
        "search_longevity": search_longevity,
        "leads": leads,
        "pipeline_cents": pipeline_cents,
        "recognized_revenue_cents": recognized_revenue_cents,
        "product_adoption": product_adoption,
        "authority_signal": authority_signal,
        "production_cost_cents": production_cost_cents,
    }

    return {
        "schema_version": "empire.media.content_value_features.v1",
        "mode": "OBSERVE",
        "features": values,
        "evidence_refs": refs,
        "score": None,
        "score_owner": "quant_brain",
        "views_are_not_revenue": True,
        "subscriber_gain_is_not_revenue": True,
        "actual_revenue": False,
        "execution_authority": "none",
    }
