"""Phase 8 freshness/chronology gate for retention and expansion evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_crm_retention import (
    RevenueCrmRetentionEvidence,
    RevenueCrmRetentionExpansionReadiness,
    assess_retention_expansion_readiness,
)


@dataclass(frozen=True)
class RevenueCrmRetentionTiming:
    buyer_observed_at: str
    payment_observed_at: str | None
    fulfilment_observed_at: str | None
    outcome_observed_at: str | None
    capacity_observed_at: str | None


@dataclass(frozen=True)
class RevenueCrmRetentionFreshness:
    buyer_id: str
    retention_fresh_for_review: bool
    expansion_fresh_for_review: bool
    base_readiness: RevenueCrmRetentionExpansionReadiness
    blockers: tuple[str, ...]
    ages_seconds: dict[str, float]
    execution_authority: str = "none"
    follow_up_execution: bool = False
    payment_execution: bool = False
    crm_mutation: bool = False
    offer_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["base_readiness"] = self.base_readiness.as_dict()
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


def assess_retention_expansion_freshness(
    *,
    evidence: RevenueCrmRetentionEvidence,
    timing: RevenueCrmRetentionTiming,
    now: datetime,
    max_age_seconds: int = 86400,
) -> RevenueCrmRetentionFreshness:
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if now.tzinfo is None:
        raise ValueError("now must include timezone")

    base = assess_retention_expansion_readiness(evidence)
    blockers = list(base.retention_blockers)
    blockers.extend(base.expansion_blockers)
    current = now.astimezone(timezone.utc)
    ages: dict[str, float] = {}

    buyer_time = _parse(timing.buyer_observed_at, label="buyer_observed_at")
    ordered_times: list[tuple[str, datetime]] = [("buyer", buyer_time)]
    for label, raw in (
        ("payment", timing.payment_observed_at),
        ("fulfilment", timing.fulfilment_observed_at),
        ("outcome", timing.outcome_observed_at),
        ("capacity", timing.capacity_observed_at),
    ):
        try:
            stamp = _parse(raw, label=f"{label}_observed_at")
        except ValueError:
            blockers.append(f"{label}_timestamp_missing")
            continue
        ordered_times.append((label, stamp))
        age = (current - stamp).total_seconds()
        ages[label] = round(age, 3)
        if age < -60:
            blockers.append(f"{label}_evidence_from_future")
        elif age > max_age_seconds:
            blockers.append(f"{label}_evidence_stale")

    ages["buyer"] = round((current - buyer_time).total_seconds(), 3)
    if ages["buyer"] < -60:
        blockers.append("buyer_evidence_from_future")
    elif ages["buyer"] > max_age_seconds:
        blockers.append("buyer_evidence_stale")

    stamps = dict(ordered_times)
    chain = ("buyer", "payment", "fulfilment", "outcome")
    for earlier, later in zip(chain, chain[1:]):
        if earlier in stamps and later in stamps:
            if stamps[later] < stamps[earlier]:
                blockers.append(f"{later}_before_{earlier}")

    ordered = tuple(sorted(set(blockers)))
    retention_blocking = any(
        b for b in ordered
        if not b.startswith("capacity_")
        and b not in {"verified_buyer_capacity_missing", "buyer_capacity_not_available"}
        and b not in {"successful_outcome_unknown", "successful_outcome_not_verified"}
    )
    return RevenueCrmRetentionFreshness(
        buyer_id=evidence.buyer_id,
        retention_fresh_for_review=(
            base.retention_review_ready and not retention_blocking
        ),
        expansion_fresh_for_review=(
            base.expansion_review_ready and not ordered
        ),
        base_readiness=base,
        blockers=ordered,
        ages_seconds=ages,
    )
