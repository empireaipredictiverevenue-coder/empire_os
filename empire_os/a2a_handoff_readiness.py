"""Phase 6 A2A manual-handoff evidence chronology/freshness review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.a2a_handoff import (
    A2AManualHandoffEvidence,
    A2AManualHandoffReview,
    review_manual_handoff,
)


@dataclass(frozen=True)
class A2AHandoffTimingEvidence:
    negotiation_observed_at: str
    human_approval_observed_at: str | None
    counterparty_observed_at: str | None
    handoff_observed_at: str | None


@dataclass(frozen=True)
class A2AHandoffReadiness:
    negotiation_id: str
    ready_for_operator_handoff: bool
    base_review: A2AManualHandoffReview
    blockers: tuple[str, ...]
    handoff_age_seconds: float | None
    human_approval_required: bool = True
    execution_authority: str = "none"
    payment_authority: bool = False
    allocation_authority: bool = False
    task_execution: bool = False
    autonomous_handoff_execution: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["base_review"] = self.base_review.as_dict()
        return data


def _parse(value: str | None, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError(f"{label} required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def review_manual_handoff_readiness(
    *,
    evidence: A2AManualHandoffEvidence,
    timing: A2AHandoffTimingEvidence,
    now: datetime,
    max_age_seconds: int = 21600,
) -> A2AHandoffReadiness:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    base = review_manual_handoff(evidence)
    blockers = list(base.blockers)
    current = now.astimezone(timezone.utc)
    negotiation_time = _parse(
        timing.negotiation_observed_at,
        label="negotiation_observed_at",
    )

    checks = (
        ("human_approval", timing.human_approval_observed_at),
        ("counterparty", timing.counterparty_observed_at),
        ("handoff", timing.handoff_observed_at),
    )
    parsed: dict[str, datetime] = {}
    for label, value in checks:
        try:
            stamp = _parse(value, label=f"{label}_observed_at")
        except ValueError:
            blockers.append(f"{label}_timestamp_missing")
            continue
        parsed[label] = stamp
        if stamp < negotiation_time:
            blockers.append(f"{label}_before_negotiation")
        age = (current - stamp).total_seconds()
        if age < -60:
            blockers.append(f"{label}_evidence_from_future")
        elif age > max_age_seconds:
            blockers.append(f"{label}_evidence_stale")

    if "human_approval" in parsed and "counterparty" in parsed:
        if parsed["counterparty"] < parsed["human_approval"]:
            blockers.append("counterparty_acknowledgement_before_human_approval")
    if "handoff" in parsed:
        latest_required = max(
            [negotiation_time, *parsed.values()]
        )
        if parsed["handoff"] < latest_required:
            blockers.append("manual_handoff_before_required_evidence")

    handoff_age = None
    if "handoff" in parsed:
        handoff_age = round(
            (current - parsed["handoff"]).total_seconds(),
            3,
        )

    ordered = tuple(sorted(set(blockers)))
    return A2AHandoffReadiness(
        negotiation_id=evidence.negotiation_id,
        ready_for_operator_handoff=not ordered,
        base_review=base,
        blockers=ordered,
        handoff_age_seconds=handoff_age,
    )
