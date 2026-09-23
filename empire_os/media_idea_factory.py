"""Video idea factory for Empire Media OS.

Idea Factory prepares evidence-linked candidates and delegates economics/ranking
to the existing Quant Brain and Opportunity Factory. It does not invent a media
score, buyer intent, revenue, or publishing authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from empire_os.media_os_foundation import (
    build_media_opportunity_feature_packet,
)


@dataclass(frozen=True)
class MediaIdeaCandidate:
    idea_id: str
    topic: str
    angle: str
    audience: str
    evidence_refs: tuple[str, ...]
    source_systems: tuple[str, ...]
    format_candidates: tuple[str, ...] = ()
    product_refs: tuple[str, ...] = ()
    opportunity_refs: tuple[str, ...] = ()
    content_franchise_candidate: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.idea_id.strip():
            raise ValueError("idea_id is required")
        if not self.topic.strip():
            raise ValueError("idea topic is required")
        if not self.angle.strip():
            raise ValueError("idea angle is required")
        if not self.audience.strip():
            raise ValueError("idea audience is required")
        if not self.evidence_refs:
            raise ValueError("idea evidence_refs are required")

    def as_dict(
        self,
        *,
        opportunity_features: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.validate()
        packet = build_media_opportunity_feature_packet(
            topic=self.topic,
            evidence_refs=self.evidence_refs,
            source_systems=self.source_systems,
            features=opportunity_features,
        )
        return {
            "schema_version": "empire.media.idea_candidate.v1",
            "mode": "OBSERVE",
            "idea_id": self.idea_id,
            "topic": self.topic,
            "angle": self.angle,
            "audience": self.audience,
            "evidence_refs": list(self.evidence_refs),
            "source_systems": list(self.source_systems),
            "format_candidates": list(self.format_candidates),
            "product_refs": list(self.product_refs),
            "opportunity_refs": list(self.opportunity_refs),
            "content_franchise_candidate": self.content_franchise_candidate,
            "created_at": self.created_at,
            "opportunity_features": packet,
            "decision": "PENDING_QUANT_REVIEW",
            "ranking_owner": "quant_brain_and_opportunity_factory",
            "public_publish_authorized": False,
            "actual_revenue": False,
            "execution_authority": "none",
        }


def build_idea_batch(
    candidates: Iterable[
        tuple[MediaIdeaCandidate, Mapping[str, Any]]
    ],
) -> dict[str, Any]:
    rows = [
        candidate.as_dict(opportunity_features=features)
        for candidate, features in candidates
    ]
    return {
        "schema_version": "empire.media.idea_batch.v1",
        "mode": "OBSERVE",
        "candidate_count": len(rows),
        "candidates": rows,
        "decision": "PENDING_QUANT_REVIEW",
        "automatic_build_authorized": False,
        "public_publish_authorized": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def apply_quant_review(
    idea: Mapping[str, Any],
    quant_packet: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach an existing Quant decision packet without re-scoring it."""
    idea_id = str(idea.get("idea_id") or "").strip()
    if not idea_id:
        raise ValueError("idea_id is required")
    if not quant_packet:
        raise ValueError("quant_packet is required")

    recommendation = str(
        quant_packet.get("recommendation")
        or quant_packet.get("decision")
        or ""
    ).strip().upper()

    if recommendation in {"BUILD", "PROCEED", "PRIORITIZE"}:
        decision = "BUILD_CANDIDATE"
    elif recommendation in {"REJECT", "STOP"}:
        decision = "REJECT"
    else:
        decision = "HOLD"

    return {
        **dict(idea),
        "quant_review_ref": (
            quant_packet.get("decision_id")
            or quant_packet.get("packet_id")
        ),
        "quant_recommendation": recommendation or "UNKNOWN",
        "decision": decision,
        "automatic_build_authorized": False,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }
