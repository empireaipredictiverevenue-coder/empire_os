"""Canonical Conversion Intelligence specialist.

Measures evidence-backed conversion boundaries across the Empire revenue
system and proposes the next CRO investigation. It never mutates traffic,
creative, landing pages, outreach, pricing, payment, fulfilment or revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


CANONICAL_STAGES = (
    "visitor_to_lead",
    "lead_to_qualified",
    "qualified_to_buyer_review",
    "buyer_review_to_delivered_outreach",
    "delivered_outreach_to_reply",
    "reply_to_qualified_conversation",
    "conversation_to_terms",
    "terms_to_acceptance",
    "acceptance_to_payment",
    "payment_to_fulfilment",
    "fulfilment_to_positive_outcome",
    "outcome_to_repeat_purchase",
)


@dataclass(frozen=True)
class ConversionStageEvidence:
    stage: str
    entered: int | None
    converted: int | None
    evidence_ref: str | None
    observed_at: str | None = None
    recognized_revenue_cents: int | None = None
    realized_gp_cents: int | None = None

    def validate(self) -> None:
        if self.stage not in CANONICAL_STAGES:
            raise ValueError(f"unsupported conversion stage: {self.stage}")
        if self.entered is not None and self.entered < 0:
            raise ValueError("entered must be nonnegative")
        if self.converted is not None and self.converted < 0:
            raise ValueError("converted must be nonnegative")
        if (
            self.entered is not None
            and self.converted is not None
            and self.converted > self.entered
        ):
            raise ValueError("converted cannot exceed entered")


@dataclass(frozen=True)
class ConversionStageReview:
    stage: str
    conversion_rate: float | None
    dropoff_count: int | None
    dropoff_rate: float | None
    sample_size: int | None
    review_ready: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    recognized_revenue_cents: int | None
    realized_gp_cents: int | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversionSpecialistReview:
    stages: tuple[ConversionStageReview, ...]
    primary_bottleneck: str | None
    primary_bottleneck_rate: float | None
    experiment_candidate: dict[str, Any] | None
    unknown_stages: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    landing_page_mutation: bool = False
    traffic_mutation: bool = False
    outreach_mutation: bool = False
    pricing_mutation: bool = False
    payment_mutation: bool = False
    revenue_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def review_stage(evidence: ConversionStageEvidence) -> ConversionStageReview:
    evidence.validate()
    blockers: list[str] = []
    refs: list[str] = []

    ref = str(evidence.evidence_ref or "").strip()
    if ref:
        refs.append(ref)
    else:
        blockers.append("conversion_evidence_missing")

    if evidence.entered is None:
        blockers.append("entered_count_unknown")
    if evidence.converted is None:
        blockers.append("converted_count_unknown")

    rate = None
    dropoff_count = None
    dropoff_rate = None
    if evidence.entered is not None and evidence.converted is not None:
        dropoff_count = evidence.entered - evidence.converted
        if evidence.entered > 0:
            rate = evidence.converted / evidence.entered
            dropoff_rate = dropoff_count / evidence.entered
        else:
            blockers.append("conversion_rate_unavailable_without_entries")

    return ConversionStageReview(
        stage=evidence.stage,
        conversion_rate=round(rate, 4) if rate is not None else None,
        dropoff_count=dropoff_count,
        dropoff_rate=(
            round(dropoff_rate, 4)
            if dropoff_rate is not None
            else None
        ),
        sample_size=evidence.entered,
        review_ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
        evidence_refs=tuple(refs),
        recognized_revenue_cents=evidence.recognized_revenue_cents,
        realized_gp_cents=evidence.realized_gp_cents,
    )


def _experiment_for(stage: ConversionStageReview) -> dict[str, Any]:
    surface_by_stage = {
        "visitor_to_lead": "landing_page",
        "lead_to_qualified": "qualification",
        "qualified_to_buyer_review": "buyer_discovery",
        "buyer_review_to_delivered_outreach": "outbound",
        "delivered_outreach_to_reply": "outbound_message",
        "reply_to_qualified_conversation": "closer",
        "conversation_to_terms": "offer_terms",
        "terms_to_acceptance": "commercial_terms",
        "acceptance_to_payment": "payment_request",
        "payment_to_fulfilment": "fulfilment_handoff",
        "fulfilment_to_positive_outcome": "delivery_quality",
        "outcome_to_repeat_purchase": "retention_expansion",
    }
    return {
        "stage": stage.stage,
        "surface": surface_by_stage[stage.stage],
        "hypothesis_required": True,
        "primary_metric": f"{stage.stage}_conversion_rate",
        "baseline_rate": stage.conversion_rate,
        "baseline_sample_size": stage.sample_size,
        "minimum_sample_required": True,
        "experiment_authority": "proposal_only",
        "automatic_rollout": False,
    }


def review_conversion_system(
    evidence: Iterable[ConversionStageEvidence],
    *,
    min_sample_size: int = 20,
) -> ConversionSpecialistReview:
    if min_sample_size < 1:
        raise ValueError("min_sample_size must be positive")

    reviews = tuple(review_stage(item) for item in evidence)
    by_stage = {item.stage: item for item in reviews}

    unknown = tuple(
        stage
        for stage in CANONICAL_STAGES
        if stage not in by_stage
        or not by_stage[stage].review_ready
    )

    eligible = [
        item
        for item in reviews
        if item.review_ready
        and item.sample_size is not None
        and item.sample_size >= min_sample_size
        and item.conversion_rate is not None
    ]
    eligible.sort(
        key=lambda item: (
            item.conversion_rate,
            -(item.sample_size or 0),
            CANONICAL_STAGES.index(item.stage),
        )
    )

    primary = eligible[0] if eligible else None
    refs: list[str] = []
    for item in reviews:
        refs.extend(item.evidence_refs)

    return ConversionSpecialistReview(
        stages=reviews,
        primary_bottleneck=primary.stage if primary else None,
        primary_bottleneck_rate=(
            primary.conversion_rate if primary else None
        ),
        experiment_candidate=(
            _experiment_for(primary)
            if primary
            else None
        ),
        unknown_stages=unknown,
        evidence_refs=tuple(dict.fromkeys(refs)),
    )


# Original Conversion Intelligence: same-cohort homeowner call progression.
# This is an ADDITIVE CRO evaluator, not another scheduler or operator.
HOMEOWNER_CALL_STAGES = (
    "landing_sessions",
    "eligible_zip_interactions",
    "consented_call_choices",
    "provider_connected_calls",
    "buyer_accepted_payable_calls",
    "independently_settled_calls",
)


def review_homeowner_call_funnel(
    *,
    source_id: str,
    cohort_ref: str,
    counts: dict[str, int | None],
    evidence_refs: dict[str, str | None],
    source_lineage_verified: bool = False,
    min_sample_size: int = 20,
) -> dict[str, Any]:
    """Compare only admissible, same-cohort stages; UNKNOWN never means zero.

    A ref or a supplied count is NOT proof on its own. A source owner must
    separately confirm the lineage across session, call and cash records.
    This function cannot grant source, visitor, payout or experiment authority.
    """
    if (not isinstance(source_id, str) or not source_id
            or len(source_id) > 80 or not source_id.replace("_", "").isalnum()
            or not isinstance(cohort_ref, str) or not 6 <= len(cohort_ref) <= 200
            or type(min_sample_size) is not int or min_sample_size < 1):
        raise ValueError("invalid owned source, cohort or sample size")
    if (not isinstance(counts, dict) or set(counts) != set(HOMEOWNER_CALL_STAGES)
            or not isinstance(evidence_refs, dict)
            or set(evidence_refs) != set(HOMEOWNER_CALL_STAGES)):
        raise ValueError("all original call funnel boundaries required")
    if type(source_lineage_verified) is not bool:
        raise ValueError("trusted lineage status must be boolean")
    prepared = []
    prior_count = None
    prior_known = False
    for step in HOMEOWNER_CALL_STAGES:
        count = counts[step]
        ref = evidence_refs[step]
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("call stage count invalid")
        if ref is not None and (not isinstance(ref, str)
                                or not 6 <= len(ref) <= 240):
            raise ValueError("call stage receipt invalid")
        # Never compare disjoint populations, or silently treat unknown as 0.
        if count is not None and prior_known and count > prior_count:
            raise ValueError("same-cohort call stage exceeds previous stage")
        receipts_bound = count is not None and bool(ref)
        conversion = None
        dropout = None
        if (source_lineage_verified and prior_known and count is not None
                and prior_count > 0 and receipts_bound):
            conversion = round(count / prior_count, 4)
            dropout = prior_count - count
        prepared.append({
            "stage": step,
            "observed_count": count if receipts_bound else None,
            "evidence_ref": ref if receipts_bound else None,
            "same_source_cohort": cohort_ref,
            "stage_conversion_rate": conversion,
            "stage_dropoff_count": dropout,
            "rate_ready": conversion is not None and prior_count >= min_sample_size,
            "no_count_inference": True,
        })
        prior_count = count if receipts_bound else None
        prior_known = receipts_bound
    measured = [s for s in prepared if s["rate_ready"]]
    measured.sort(key=lambda s: (s["stage_conversion_rate"],
                                HOMEOWNER_CALL_STAGES.index(s["stage"])))
    return {
        "schema_version": "empire.conversion.homeowner_call_cohort_review.v1",
        "mode": "OBSERVE",
        "source_id": source_id,
        "cohort_ref": cohort_ref,
        "source_lineage_verified": source_lineage_verified,
        "stage_reviews": prepared,
        "measured_stage_count": len(measured),
        "first_reviewable_bottleneck": measured[0]["stage"] if measured else None,
        "bottleneck_rate": measured[0]["stage_conversion_rate"] if measured else None,
        "minimum_sample_size": min_sample_size,
        "recommended_next_step": (
            "REVIEW_ORIGINAL_OWNER_COHORT_EVIDENCE" if not measured
            else "PROPOSE_CONTROLLED_HYPOTHESIS_NO_AUTO_ROLLOUT"
        ),
        "experiment_proposal_only": True,
        "automatic_experiment_rollout": False,
        "revenue_verified_by_this_review": False,
        "execution_authority": "none",
    }
