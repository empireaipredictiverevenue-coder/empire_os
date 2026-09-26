"""Empire build journal as trusted Media OS source material."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class BuildJournalEntry:
    entry_id: str
    system: str
    change: str
    problem: str
    solution: str
    evidence_refs: tuple[str, ...]
    before_refs: tuple[str, ...] = ()
    after_refs: tuple[str, ...] = ()
    screenshot_refs: tuple[str, ...] = ()
    metric_refs: tuple[str, ...] = ()
    business_relevance: str | None = None
    lessons: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("journal entry_id is required")
        if not self.system.strip():
            raise ValueError("journal system is required")
        if not self.change.strip():
            raise ValueError("journal change is required")
        if not self.problem.strip():
            raise ValueError("journal problem is required")
        if not self.solution.strip():
            raise ValueError("journal solution is required")
        if not self.evidence_refs:
            raise ValueError("journal evidence_refs are required")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def content_opportunity_from_build(
    entry: BuildJournalEntry,
    *,
    novelty_observed: bool,
    audience_relevance_observed: bool,
    demonstration_available: bool,
    commercial_relevance_observed: bool,
) -> dict[str, Any]:
    row = entry.as_dict()
    positive = sum((
        bool(novelty_observed),
        bool(audience_relevance_observed),
        bool(demonstration_available),
        bool(commercial_relevance_observed),
    ))
    if positive >= 3:
        state = "MEDIA_OPPORTUNITY_CANDIDATE"
    elif positive >= 1:
        state = "HOLD_FOR_MORE_EVIDENCE"
    else:
        state = "NO_CURRENT_MEDIA_CASE"

    return {
        "schema_version": "empire.media.build_journal_opportunity.v1",
        "mode": "OBSERVE",
        "journal_entry": row,
        "signals": {
            "novelty_observed": bool(novelty_observed),
            "audience_relevance_observed": bool(
                audience_relevance_observed
            ),
            "demonstration_available": bool(
                demonstration_available
            ),
            "commercial_relevance_observed": bool(
                commercial_relevance_observed
            ),
        },
        "state": state,
        "media_score_created": False,
        "ranking_owner": "quant_brain_and_opportunity_factory",
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def journal_to_source_refs(
    entries: Iterable[BuildJournalEntry],
) -> list[dict[str, Any]]:
    return [
        {
            "entry_id": row.entry_id,
            "source_type": "empire_build_journal",
            "evidence_refs": list(row.evidence_refs),
            "source_timestamp": row.created_at,
            "owned_source": True,
        }
        for row in entries
    ]
