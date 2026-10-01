"""Replayable evidence-first Supply Quality Twin.

Keeps source availability, identity quality, buyer acceptance and realized
economics separate. It never turns those dimensions into execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class SupplyQualityObservation:
    observation_key: str
    supply_id: str
    source_keys: tuple[str, ...]
    product_key: str
    market_key: str
    evidence_refs: tuple[str, ...]
    attributed_source_key: str | None = None
    source_healthy: bool | None = None
    identity_accepted: bool | None = None
    delivered: bool | None = None
    buyer_accepted: bool | None = None
    recognized_revenue_cents: int | None = None
    observed_cost_cents: int | None = None

    def validate(self) -> None:
        for label, value in (
            ("observation_key", self.observation_key),
            ("supply_id", self.supply_id),
            ("product_key", self.product_key),
            ("market_key", self.market_key),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{label} required")
        if not self.source_keys:
            raise ValueError("source_keys required")
        if not self.evidence_refs:
            raise ValueError("evidence_refs required")
        if (
            self.attributed_source_key is not None
            and self.attributed_source_key not in self.source_keys
        ):
            raise ValueError(
                "attributed_source_key must be present in source_keys"
            )
        for label, value in (
            ("recognized_revenue_cents", self.recognized_revenue_cents),
            ("observed_cost_cents", self.observed_cost_cents),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be nonnegative")


@dataclass(frozen=True)
class SupplyQualityTwin:
    source_key: str
    product_key: str
    market_key: str
    unique_supply_count: int
    source_health_observed_count: int
    source_healthy_count: int
    identity_observed_count: int
    identity_accepted_count: int
    delivery_observed_count: int
    delivered_count: int
    buyer_outcome_observed_count: int
    buyer_accepted_count: int
    attributed_commercial_outcome_count: int
    attributed_recognized_revenue_cents: int
    attributed_observed_cost_cents: int | None
    attributed_realized_gp_cents: int | None
    unattributed_multi_source_count: int
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    replayable: bool = True
    commercial_quality_inferred: bool = False
    buyer_acceptance_probability_inferred: bool = False
    source_policy_mutation: bool = False
    canonical_writes: bool = False
    allocation_execution: bool = False
    revenue_recognition: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _credited_to_source(
    row: SupplyQualityObservation,
    source_key: str,
) -> bool:
    if source_key not in row.source_keys:
        return False
    if len(row.source_keys) == 1:
        return True
    return row.attributed_source_key == source_key


def build_supply_quality_twin(
    observations: Iterable[SupplyQualityObservation],
    *,
    source_key: str,
    product_key: str,
    market_key: str,
) -> SupplyQualityTwin:
    source = str(source_key or "").strip()
    product = str(product_key or "").strip()
    market = str(market_key or "").strip()
    if not source or not product or not market:
        raise ValueError("source_key, product_key and market_key required")

    rows: list[SupplyQualityObservation] = []
    seen: set[str] = set()
    for row in observations:
        row.validate()
        if row.observation_key in seen:
            continue
        seen.add(row.observation_key)
        if row.product_key != product or row.market_key != market:
            continue
        if source not in row.source_keys:
            continue
        rows.append(row)

    unique_supply = len({row.supply_id for row in rows})
    source_health_observed = sum(
        row.source_healthy is not None for row in rows
    )
    source_healthy = sum(row.source_healthy is True for row in rows)
    identity_observed = sum(
        row.identity_accepted is not None for row in rows
    )
    identity_accepted = sum(
        row.identity_accepted is True for row in rows
    )
    delivery_observed = sum(row.delivered is not None for row in rows)
    delivered = sum(row.delivered is True for row in rows)
    buyer_observed = sum(
        row.buyer_accepted is not None for row in rows
    )
    buyer_accepted = sum(
        row.buyer_accepted is True for row in rows
    )

    credited = [
        row
        for row in rows
        if _credited_to_source(row, source)
        and row.recognized_revenue_cents is not None
    ]
    revenue = sum(
        int(row.recognized_revenue_cents or 0)
        for row in credited
    )

    costs_complete = all(
        row.observed_cost_cents is not None
        for row in credited
    )
    cost: int | None
    gp: int | None
    if credited and costs_complete:
        cost = sum(int(row.observed_cost_cents or 0) for row in credited)
        gp = revenue - cost
    elif credited:
        cost = None
        gp = None
    else:
        cost = None
        gp = None

    unattributed_multi = sum(
        len(row.source_keys) > 1
        and row.attributed_source_key is None
        for row in rows
    )

    blockers: list[str] = []
    if not rows:
        blockers.append("supply_observations_missing")
    if buyer_observed == 0:
        blockers.append("buyer_outcomes_unobserved")
    if not credited:
        blockers.append("attributed_commercial_outcomes_unobserved")
    elif not costs_complete:
        blockers.append("observed_cost_evidence_incomplete")

    refs = tuple(dict.fromkeys(
        ref
        for row in rows
        for ref in row.evidence_refs
        if str(ref).strip()
    ))

    return SupplyQualityTwin(
        source_key=source,
        product_key=product,
        market_key=market,
        unique_supply_count=unique_supply,
        source_health_observed_count=source_health_observed,
        source_healthy_count=source_healthy,
        identity_observed_count=identity_observed,
        identity_accepted_count=identity_accepted,
        delivery_observed_count=delivery_observed,
        delivered_count=delivered,
        buyer_outcome_observed_count=buyer_observed,
        buyer_accepted_count=buyer_accepted,
        attributed_commercial_outcome_count=len(credited),
        attributed_recognized_revenue_cents=revenue,
        attributed_observed_cost_cents=cost,
        attributed_realized_gp_cents=gp,
        unattributed_multi_source_count=unattributed_multi,
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=refs,
    )
