"""Media research/evidence packs and fact-freshness review.

The pack references canonical Empire evidence. It is not a parallel evidence
store and does not convert sources into verified facts automatically.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


FRESHNESS_WINDOWS_DAYS = {
    "REALTIME": 1,
    "FAST_MOVING": 7,
    "CURRENT": 30,
    "SLOW_MOVING": 180,
    "EVERGREEN": 3650,
}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class MediaResearchSource:
    source_ref: str
    source_type: str
    observed_at: str | None
    lineage_ref: str | None = None
    rights_state: str = "UNKNOWN"

    def validate(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("research source_ref is required")
        if not self.source_type.strip():
            raise ValueError("research source_type is required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class MediaResearchClaim:
    claim_id: str
    text: str
    evidence_refs: tuple[str, ...]
    freshness_class: str = "CURRENT"
    source_timestamp: str | None = None
    uncertainty: str | None = None
    counterargument_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.claim_id.strip():
            raise ValueError("claim_id is required")
        if not self.text.strip():
            raise ValueError("claim text is required")
        if not self.evidence_refs:
            raise ValueError("research claims require evidence_refs")
        if self.freshness_class not in FRESHNESS_WINDOWS_DAYS:
            raise ValueError("unsupported freshness_class")

    def as_dict(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.validate()
        now = now or datetime.now(timezone.utc)
        observed = _parse_time(self.source_timestamp)
        window = FRESHNESS_WINDOWS_DAYS[self.freshness_class]

        stale = None
        age_days = None
        if observed is not None:
            delta = now - observed
            age_days = max(0.0, delta.total_seconds() / 86400)
            stale = delta > timedelta(days=window)

        return {
            **asdict(self),
            "freshness_window_days": window,
            "age_days": (
                round(age_days, 2)
                if age_days is not None
                else None
            ),
            "stale": stale,
            "refresh_required": stale is True,
        }


@dataclass(frozen=True)
class MediaResearchPack:
    research_id: str
    topic: str
    thesis: str
    audience: str
    sources: tuple[MediaResearchSource, ...]
    claims: tuple[MediaResearchClaim, ...]
    examples: tuple[str, ...] = ()
    counterarguments: tuple[str, ...] = ()
    screenshot_refs: tuple[str, ...] = ()
    product_evidence_refs: tuple[str, ...] = ()
    empire_data_refs: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.research_id.strip():
            raise ValueError("research_id is required")
        if not self.topic.strip():
            raise ValueError("research topic is required")
        if not self.thesis.strip():
            raise ValueError("research thesis is required")
        if not self.audience.strip():
            raise ValueError("research audience is required")
        if not self.sources:
            raise ValueError("research sources are required")
        for source in self.sources:
            source.validate()
        for claim in self.claims:
            claim.validate()

        source_refs = {row.source_ref for row in self.sources}
        dangling = sorted({
            ref
            for claim in self.claims
            for ref in claim.evidence_refs
            if ref not in source_refs
        })
        if dangling:
            raise ValueError(
                "claim evidence_refs missing from research sources: "
                + ",".join(dangling)
            )

    def as_dict(
        self,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.validate()
        claim_rows = [
            claim.as_dict(now=now)
            for claim in self.claims
        ]
        stale_claims = [
            row["claim_id"]
            for row in claim_rows
            if row["stale"] is True
        ]
        return {
            "schema_version": "empire.media.research_pack.v1",
            "mode": "OBSERVE",
            "research_id": self.research_id,
            "topic": self.topic,
            "thesis": self.thesis,
            "audience": self.audience,
            "sources": [
                source.as_dict()
                for source in self.sources
            ],
            "claims": claim_rows,
            "examples": list(self.examples),
            "counterarguments": list(self.counterarguments),
            "screenshot_refs": list(self.screenshot_refs),
            "product_evidence_refs": list(self.product_evidence_refs),
            "empire_data_refs": list(self.empire_data_refs),
            "uncertainty": list(self.uncertainty),
            "generated_at": self.generated_at,
            "stale_claim_ids": stale_claims,
            "refresh_required": bool(stale_claims),
            "unknown_is_unknown": True,
            "public_publish_authorized": False,
            "actual_revenue": False,
            "execution_authority": "none",
        }


def fact_refresh_actions(
    pack: MediaResearchPack,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    row = pack.as_dict(now=now)
    stale = row["stale_claim_ids"]
    actions = []
    if stale:
        actions.extend([
            "refresh_description_candidate",
            "pinned_correction_candidate",
            "new_edition_candidate",
            "replacement_content_candidate",
        ])
    return {
        "schema_version": "empire.media.fact_refresh_actions.v1",
        "research_id": pack.research_id,
        "stale_claim_ids": stale,
        "candidate_actions": actions,
        "automatic_public_mutation": False,
        "execution_authority": "none",
    }
