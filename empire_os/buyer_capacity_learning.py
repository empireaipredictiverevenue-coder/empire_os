"""OBSERVE-only learning projection for verified buyer capacity.

The learner consumes windowed observed outcomes and may recommend operator
review. It never mutates buyer capacity or grants allocation authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class BuyerCapacityOutcomeWindow:
    observation_key: str
    buyer_id: str
    product_key: str
    market_key: str
    offered_units: int
    accepted_units: int
    capacity_rejected_units: int
    quality_rejected_units: int
    unresolved_units: int
    observed_at: str
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        for label, value in (
            ("observation_key", self.observation_key),
            ("buyer_id", self.buyer_id),
            ("product_key", self.product_key),
            ("market_key", self.market_key),
            ("observed_at", self.observed_at),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")

        try:
            observed = datetime.fromisoformat(
                self.observed_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise ValueError("observed_at must be ISO-8601") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        counts = (
            self.offered_units,
            self.accepted_units,
            self.capacity_rejected_units,
            self.quality_rejected_units,
            self.unresolved_units,
        )
        if any(value < 0 for value in counts):
            raise ValueError("capacity outcome counts must be nonnegative")

        classified = (
            self.accepted_units
            + self.capacity_rejected_units
            + self.quality_rejected_units
            + self.unresolved_units
        )
        if classified > self.offered_units:
            raise ValueError(
                "classified outcome units cannot exceed offered units"
            )
        if not self.evidence_refs:
            raise ValueError("capacity outcome requires evidence refs")


@dataclass(frozen=True)
class BuyerCapacityLearningAssessment:
    buyer_id: str
    product_key: str
    market_key: str
    verified_capacity_limit: int | None
    unique_window_count: int
    resolved_unit_count: int
    accepted_unit_count: int
    capacity_rejected_unit_count: int
    quality_rejected_unit_count: int
    unresolved_unit_count: int
    observed_peak_accepted_units: int | None
    recommendation: str
    recommended_capacity_ceiling: int | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    buyer_capacity_mutation: bool = False
    allocation_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_buyer_capacity_learning(
    windows: Iterable[BuyerCapacityOutcomeWindow],
    *,
    verified_capacity_limit: int | None,
    capacity_evidence_ref: str | None,
    min_windows: int = 3,
    min_resolved_units: int = 10,
) -> BuyerCapacityLearningAssessment:
    rows: list[BuyerCapacityOutcomeWindow] = []
    seen: set[str] = set()

    for row in windows:
        row.validate()
        if row.observation_key in seen:
            continue
        seen.add(row.observation_key)
        rows.append(row)

    identities = {
        (row.buyer_id, row.product_key, row.market_key)
        for row in rows
    }
    if len(identities) > 1:
        raise ValueError(
            "capacity learning windows must share buyer/product/market identity"
        )

    if rows:
        buyer_id, product_key, market_key = next(iter(identities))
    else:
        buyer_id = product_key = market_key = ""

    blockers: list[str] = []
    if verified_capacity_limit is None:
        blockers.append("verified_capacity_limit_missing")
    elif verified_capacity_limit < 0:
        raise ValueError("verified_capacity_limit must be nonnegative")

    capacity_ref = str(capacity_evidence_ref or "").strip()
    if not capacity_ref:
        blockers.append("capacity_evidence_ref_missing")

    accepted = sum(row.accepted_units for row in rows)
    cap_rejected = sum(row.capacity_rejected_units for row in rows)
    quality_rejected = sum(row.quality_rejected_units for row in rows)
    unresolved = sum(row.unresolved_units for row in rows)
    resolved = accepted + cap_rejected + quality_rejected
    peak = max((row.accepted_units for row in rows), default=None)

    if len(rows) < min_windows:
        blockers.append("insufficient_unique_outcome_windows")
    if resolved < min_resolved_units:
        blockers.append("insufficient_resolved_units")

    refs = tuple(dict.fromkeys(
        [
            capacity_ref,
            *[
                ref
                for row in rows
                for ref in row.evidence_refs
            ],
        ]
    ))
    refs = tuple(ref for ref in refs if ref)

    if blockers:
        recommendation = "INSUFFICIENT_EVIDENCE"
        ceiling = None
    elif cap_rejected > 0:
        recommendation = "REVIEW_DOWNWARD"
        ceiling = min(
            int(verified_capacity_limit),
            int(peak or 0),
        )
    else:
        recommendation = "MAINTAIN_VERIFIED_LIMIT"
        ceiling = int(verified_capacity_limit)

    return BuyerCapacityLearningAssessment(
        buyer_id=buyer_id,
        product_key=product_key,
        market_key=market_key,
        verified_capacity_limit=verified_capacity_limit,
        unique_window_count=len(rows),
        resolved_unit_count=resolved,
        accepted_unit_count=accepted,
        capacity_rejected_unit_count=cap_rejected,
        quality_rejected_unit_count=quality_rejected,
        unresolved_unit_count=unresolved,
        observed_peak_accepted_units=peak,
        recommendation=recommendation,
        recommended_capacity_ceiling=ceiling,
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=refs,
    )
