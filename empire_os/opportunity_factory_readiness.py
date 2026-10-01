"""Strict evidence convergence for Opportunity Factory readiness."""
from __future__ import annotations

from typing import Any, Mapping

ECONOMICS_FACTORS = frozenset({"terms", "payment", "ltv_cents"})
DISTRIBUTION_FACTORS = frozenset({"buyer_match", "outreach", "conversion"})
FULFILMENT_FACTORS = frozenset({"fulfilment"})
QUALIFICATION_FACTORS = frozenset(
    {"demand", "quality", "enrichment", "omega_qualification"}
)


def evaluate_factory_readiness(candidate: Mapping[str, Any]) -> dict[str, Any]:
    inputs = candidate.get("predictive_revenue_inputs")
    refs = candidate.get("predictive_revenue_evidence_refs")
    inputs = dict(inputs) if isinstance(inputs, Mapping) else {}
    refs = dict(refs) if isinstance(refs, Mapping) else {}

    def evidenced(factor: str) -> bool:
        value_present = factor in inputs and inputs.get(factor) is not None
        evidence = refs.get(factor)
        return bool(
            value_present
            and isinstance(evidence, (list, tuple))
            and any(str(item).strip() for item in evidence)
        )

    blockers: list[str] = []
    if not str(candidate.get("offer_key") or "").strip():
        blockers.append("offer_required")

    if candidate.get("commercial_demand_observed") is not True:
        blockers.append("commercial_demand_observation_required")

    if not all(evidenced(name) for name in QUALIFICATION_FACTORS):
        blockers.append("qualification_evidence_required")

    if not all(evidenced(name) for name in ECONOMICS_FACTORS):
        blockers.append("normalized_economics_required")

    if not all(evidenced(name) for name in DISTRIBUTION_FACTORS):
        blockers.append("distribution_strength_evidence_required")

    if not all(evidenced(name) for name in FULFILMENT_FACTORS):
        blockers.append("fulfilment_readiness_evidence_required")

    return {
        "opportunity_factory_ready": not blockers,
        "factory_blockers": blockers,
        "readiness_source": "explicit_predictive_revenue_factor_evidence",
        "execution_authority": "none",
    }
