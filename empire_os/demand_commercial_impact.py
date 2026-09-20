"""Phase 12 evidence-only Demand Genesis commercial-impact review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.demand_freshness import DemandOutcomeEvidenceReview


@dataclass(frozen=True)
class DemandCommercialImpactEvidence:
    plan_id: str
    commercial_attribution_ref: str | None = None
    recognized_revenue_ref: str | None = None
    recognized_revenue_cents: int | None = None
    realized_gp_ref: str | None = None
    realized_gp_cents: int | None = None

    def validate(self) -> None:
        if not self.plan_id.strip():
            raise ValueError("plan_id required")
        for label, value in (
            ("recognized_revenue_cents", self.recognized_revenue_cents),
            ("realized_gp_cents", self.realized_gp_cents),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be nonnegative")


@dataclass(frozen=True)
class DemandCommercialImpactReview:
    plan_id: str
    commercial_impact_ready: bool
    recognized_revenue_cents: int | None
    realized_gp_cents: int | None
    revenue_on_cost: float | None
    gross_profit_on_cost: float | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    publishing_enabled: bool = False
    outbound_enabled: bool = False
    ad_spend_enabled: bool = False
    provider_activation_enabled: bool = False
    revenue_mutation: bool = False
    accounting_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_demand_commercial_impact(
    *,
    outcome: DemandOutcomeEvidenceReview,
    evidence: DemandCommercialImpactEvidence,
) -> DemandCommercialImpactReview:
    evidence.validate()
    if outcome.plan_id != evidence.plan_id:
        raise ValueError("demand outcome/commercial-impact plan mismatch")

    blockers = list(outcome.blockers)
    refs: list[str] = []

    if not outcome.review_ready:
        blockers.append("demand_outcome_not_review_ready")

    attribution_ref = str(evidence.commercial_attribution_ref or "").strip()
    if attribution_ref:
        refs.append(attribution_ref)
    else:
        blockers.append("commercial_attribution_evidence_missing")

    revenue_ref = str(evidence.recognized_revenue_ref or "").strip()
    if revenue_ref:
        refs.append(revenue_ref)
    else:
        blockers.append("recognized_revenue_evidence_missing")
    if evidence.recognized_revenue_cents is None:
        blockers.append("recognized_revenue_value_unknown")

    gp_ref = str(evidence.realized_gp_ref or "").strip()
    if gp_ref:
        refs.append(gp_ref)
    else:
        blockers.append("realized_gross_profit_evidence_missing")
    if evidence.realized_gp_cents is None:
        blockers.append("realized_gross_profit_value_unknown")

    revenue_on_cost = None
    gross_profit_on_cost = None
    if outcome.observed_cost_cents is not None and outcome.observed_cost_cents > 0:
        if evidence.recognized_revenue_cents is not None:
            revenue_on_cost = round(
                evidence.recognized_revenue_cents / outcome.observed_cost_cents,
                4,
            )
        if evidence.realized_gp_cents is not None:
            gross_profit_on_cost = round(
                evidence.realized_gp_cents / outcome.observed_cost_cents,
                4,
            )

    ordered = tuple(sorted(set(blockers)))
    return DemandCommercialImpactReview(
        plan_id=evidence.plan_id,
        commercial_impact_ready=not ordered,
        recognized_revenue_cents=evidence.recognized_revenue_cents,
        realized_gp_cents=evidence.realized_gp_cents,
        revenue_on_cost=revenue_on_cost,
        gross_profit_on_cost=gross_profit_on_cost,
        blockers=ordered,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )
