"""Canonical opportunity lifecycle for Predictive Cloud.

Early research opportunities may progress through DISCOVER/QUALIFY/VALIDATE
without being treated as commercially ready. Opportunity Factory readiness is
reserved for later experimentation/commercial progression.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


STAGES = (
    "DISCOVER",
    "QUALIFY",
    "VALIDATE",
    "EXPERIMENT",
    "PROVE",
    "SCALE",
    "DEFEND",
    "HARVEST",
    "RETIRED",
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _score_evidence(
    intake: Mapping[str, Any],
    key: str,
) -> Mapping[str, Any]:
    normalization = intake.get("normalization")
    normalization = (
        normalization if isinstance(normalization, Mapping) else {}
    )
    evidence = normalization.get("score_evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    row = evidence.get(key)
    return row if isinstance(row, Mapping) else {}


def _class_context_ready(candidate: Mapping[str, Any]) -> bool:
    klass = _clean(candidate.get("opportunity_class"))
    niche = _clean(candidate.get("niche"))
    metro = _clean(candidate.get("metro"))
    offer = _clean(candidate.get("offer_key"))

    if klass == "market_research":
        return bool(niche and metro)
    if klass == "competitive_research_gap":
        return bool(niche and metro)
    if klass == "community_pain":
        return bool(offer or candidate.get("products"))
    if klass in {"event_market", "storm_event", "physical_event"}:
        return bool(niche and _clean(candidate.get("trigger")))
    return bool(
        niche
        or metro
        or offer
        or _clean(candidate.get("title"))
    )


@dataclass(frozen=True)
class OpportunityLifecycle:
    opportunity_key: str
    opportunity_class: str
    current_stage: str
    next_stage: str | None
    stage_reason: str
    discovered: bool
    qualified: bool
    validated: bool
    experiment_ready: bool
    proved: bool
    scale_ready: bool
    commercial_validation_observed: bool
    factory_ready: bool
    next_evidence_targets: tuple[str, ...]
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_opportunity_lifecycle(
    candidate: Mapping[str, Any],
    intake: Mapping[str, Any],
) -> OpportunityLifecycle:
    key = _clean(candidate.get("opportunity_key"))
    klass = _clean(candidate.get("opportunity_class"))
    trigger = _clean(candidate.get("trigger"))
    evidence_count = int(intake.get("evidence_count") or 0)
    blockers = tuple(
        str(item)
        for item in (intake.get("blockers") or [])
        if str(item).strip()
    )

    discovered = bool(key and trigger and evidence_count >= 1)
    qualified = bool(
        discovered
        and evidence_count >= 2
        and _class_context_ready(candidate)
    )

    buyer_ev = _score_evidence(intake, "buyer_intent")
    demand_ev = _score_evidence(intake, "demand")
    commercial_validation_observed = any(
        row.get("semantic_class") == "observed_stage"
        and row.get("observed_truth") is True
        for row in (buyer_ev, demand_ev)
    )

    validated = bool(
        qualified
        and commercial_validation_observed
        and intake.get("offer_key")
    )
    factory_ready = intake.get("factory_ready") is True
    assessment = intake.get("assessment")
    assessment = assessment if isinstance(assessment, Mapping) else {}
    experiment_ready = bool(
        validated
        and factory_ready
        and assessment.get("decision")
        == "build_smallest_useful_mvp"
    )

    # These remain false until later real outcome contracts populate them.
    proved = bool(intake.get("verified_outcome") is True)
    scale_ready = bool(
        proved
        and intake.get("repeatable_economics_observed") is True
    )

    if scale_ready:
        stage = "SCALE"
        next_stage = "DEFEND"
        reason = "verified repeatable economics observed"
    elif proved:
        stage = "PROVE"
        next_stage = "SCALE"
        reason = "verified outcome exists"
    elif experiment_ready:
        stage = "EXPERIMENT"
        next_stage = "PROVE"
        reason = "commercial validation and Factory readiness are proven"
    elif validated:
        stage = "VALIDATE"
        next_stage = "EXPERIMENT"
        reason = "observed commercial validation exists; complete Factory readiness"
    elif qualified:
        stage = "QUALIFY"
        next_stage = "VALIDATE"
        reason = "independent evidence and class context exist"
    elif discovered:
        stage = "DISCOVER"
        next_stage = "QUALIFY"
        reason = "initial observed signal exists"
    else:
        stage = "DISCOVER"
        next_stage = "QUALIFY"
        reason = "discovery evidence incomplete"

    return OpportunityLifecycle(
        opportunity_key=key,
        opportunity_class=klass,
        current_stage=stage,
        next_stage=next_stage,
        stage_reason=reason,
        discovered=discovered,
        qualified=qualified,
        validated=validated,
        experiment_ready=experiment_ready,
        proved=proved,
        scale_ready=scale_ready,
        commercial_validation_observed=commercial_validation_observed,
        factory_ready=factory_ready,
        next_evidence_targets=blockers,
    )
