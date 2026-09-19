"""Phase 13 operator allocation-readiness review from reconciled market evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from empire_os.revenue_exchange import ExchangeSnapshot
from empire_os.revenue_exchange_reconciliation import ExchangeReconciliation


@dataclass(frozen=True)
class ExchangeAllocationReadiness:
    niche: str
    metro: str
    ready_for_operator_allocation_review: bool
    current_age_seconds: float
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    allocation_authority: str = "none"
    pricing_authority: str = "none"
    settlement_authority: str = "none"
    exclusivity_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse(value: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("exchange snapshot timestamp required")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("exchange snapshot timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("exchange snapshot timestamp must include timezone")
    return parsed.astimezone(timezone.utc)



def assess_exchange_allocation_readiness(
    *,
    snapshot: ExchangeSnapshot,
    reconciliation: ExchangeReconciliation,
    now: datetime,
    max_age_seconds: int = 21600,
) -> ExchangeAllocationReadiness:
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if (
        snapshot.niche != reconciliation.niche
        or snapshot.metro != reconciliation.metro
    ):
        raise ValueError("exchange reconciliation market identity mismatch")

    blockers = list(reconciliation.blockers)
    observed = _parse(snapshot.observed_at)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    if age < -60:
        blockers.append("current_snapshot_from_future")
    elif age > max_age_seconds:
        blockers.append("current_snapshot_stale")

    if snapshot.qualified_inventory_count <= 0:
        blockers.append("qualified_inventory_not_available")
    if snapshot.active_buyer_capacity <= 0:
        blockers.append("verified_buyer_capacity_not_available")
    if not snapshot.verified_price_per_lead_cents:
        blockers.append("verified_price_evidence_not_available")
    if not reconciliation.review_ready:
        blockers.append("canonical_reconciliation_not_ready")

    ordered = tuple(sorted(set(blockers)))
    return ExchangeAllocationReadiness(
        niche=snapshot.niche,
        metro=snapshot.metro,
        ready_for_operator_allocation_review=not ordered,
        current_age_seconds=round(age, 3),
        blockers=ordered,
        evidence_refs=reconciliation.evidence_refs,
    )
