"""Revenue-aware enrichment prioritisation for Empire Hunter."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EnrichmentPriority:
    entity_id: str
    priority_score: float
    depth: str
    reasons: tuple[str, ...]
    evidence_confidence: float
    omega_score: float | None
    omega_confidence: float | None
    buyer_demand_strength: float | None
    buyer_demand_confidence: float | None
    modeled_expected_gp_cents: int | None
    enrichment_cost_cents: int | None
    economics_is_forecast: bool
    actual_revenue_used: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bounded(value: Any, low: float, high: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(low, min(high, number))


def prioritize_enrichment(
    *,
    entity_id: str,
    evidence_confidence: float,
    omega_score: float | None = None,
    omega_confidence: float | None = None,
    buyer_demand_strength: float | None = None,
    buyer_demand_confidence: float | None = None,
    contact_ready: bool = False,
    modeled_expected_gp_cents: int | None = None,
    enrichment_cost_cents: int | None = None,
    evidence_refs: Iterable[str] = (),
) -> EnrichmentPriority:
    eid = str(entity_id or "").strip()
    if not eid:
        raise ValueError("entity_id required")

    refs = tuple(
        dict.fromkeys(
            str(ref).strip()
            for ref in evidence_refs
            if str(ref).strip()
        )
    )
    if not refs:
        raise ValueError("prioritization requires evidence refs")

    evidence = _bounded(evidence_confidence, 0.0, 1.0)
    if evidence is None:
        raise ValueError("evidence_confidence required")

    omega = _bounded(omega_score, 0.0, 100.0)
    omega_conf = _bounded(omega_confidence, 0.0, 1.0)
    demand = _bounded(buyer_demand_strength, 0.0, 1.0)
    demand_conf = _bounded(buyer_demand_confidence, 0.0, 1.0)

    reasons: list[str] = []
    score = 20.0 + evidence * 25.0

    if omega is not None:
        weighted_conf = omega_conf if omega_conf is not None else 0.5
        score += (omega / 100.0) * weighted_conf * 30.0
        reasons.append("omega_opportunity_evidence")

    if demand is not None:
        weighted_conf = (
            demand_conf if demand_conf is not None else 0.5
        )
        score += demand * weighted_conf * 25.0
        reasons.append("buyer_demand_evidence")

    if contact_ready:
        score -= 18.0
        reasons.append("contact_already_ready")
    else:
        score += 8.0
        reasons.append("contact_gap")

    gp = (
        int(modeled_expected_gp_cents)
        if modeled_expected_gp_cents is not None
        else None
    )
    cost = (
        int(enrichment_cost_cents)
        if enrichment_cost_cents is not None
        else None
    )
    economics_is_forecast = gp is not None

    if gp is not None and gp < 0:
        raise ValueError("modeled_expected_gp_cents must be nonnegative")
    if cost is not None and cost < 0:
        raise ValueError("enrichment_cost_cents must be nonnegative")

    if gp is not None and cost is not None:
        if gp == 0:
            score -= 25.0
            reasons.append("modeled_gp_zero")
        else:
            ratio = gp / max(cost, 1)
            if ratio >= 20:
                score += 12.0
                reasons.append("strong_modeled_enrichment_economics")
            elif ratio < 3:
                score -= 18.0
                reasons.append("weak_modeled_enrichment_economics")

    score = round(max(0.0, min(100.0, score)), 2)

    if contact_ready and score < 55:
        depth = "stop"
    elif score >= 80:
        depth = "deep"
    elif score >= 60:
        depth = "standard"
    elif score >= 40:
        depth = "shallow"
    else:
        depth = "stop"

    return EnrichmentPriority(
        entity_id=eid,
        priority_score=score,
        depth=depth,
        reasons=tuple(reasons),
        evidence_confidence=round(evidence, 4),
        omega_score=round(omega, 4) if omega is not None else None,
        omega_confidence=(
            round(omega_conf, 4)
            if omega_conf is not None
            else None
        ),
        buyer_demand_strength=(
            round(demand, 4) if demand is not None else None
        ),
        buyer_demand_confidence=(
            round(demand_conf, 4)
            if demand_conf is not None
            else None
        ),
        modeled_expected_gp_cents=gp,
        enrichment_cost_cents=cost,
        economics_is_forecast=economics_is_forecast,
    )


def rank_enrichment_candidates(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[EnrichmentPriority, ...]:
    priorities = []
    for row in rows:
        priorities.append(
            prioritize_enrichment(
                entity_id=str(row.get("entity_id") or ""),
                evidence_confidence=float(
                    row.get("evidence_confidence") or 0.0
                ),
                omega_score=row.get("omega_score"),
                omega_confidence=row.get("omega_confidence"),
                buyer_demand_strength=row.get(
                    "buyer_demand_strength"
                ),
                buyer_demand_confidence=row.get(
                    "buyer_demand_confidence"
                ),
                contact_ready=row.get("contact_ready") is True,
                modeled_expected_gp_cents=row.get(
                    "modeled_expected_gp_cents"
                ),
                enrichment_cost_cents=row.get(
                    "enrichment_cost_cents"
                ),
                evidence_refs=row.get("evidence_refs") or (),
            )
        )
    return tuple(
        sorted(
            priorities,
            key=lambda item: (
                item.priority_score,
                item.evidence_confidence,
            ),
            reverse=True,
        )
    )
