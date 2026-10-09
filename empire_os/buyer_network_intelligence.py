from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class CandidateAssessment:
    score: int
    readiness: str
    blockers: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class SupplyFit:
    score: int
    gate: str
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]


@dataclass(frozen=True)
class ReplyAssessment:
    intent: str
    requested_fields: tuple[str, ...]
    next_action: str
    confidence: float


@dataclass(frozen=True)
class LaneHealth:
    state: str
    concentration: str
    remaining_capacity: int | None
    observed_gap: int | None
    discovery_required: bool


@dataclass(frozen=True)
class BoundedTestPlan:
    gate: str
    units: int
    authority: str
    stop_conditions: tuple[str, ...]


def assess_candidate(
    *,
    vertical_match: bool,
    publisher_program_confidence: float = 0.0,
    active_demand_confidence: float = 0.0,
    inventory_fit_confidence: float = 0.0,
    integration_confidence: float = 0.0,
    economics_confidence: float = 0.0,
    compliance_confidence: float = 0.0,
    contactable: bool = False,
    negative_program_confidence: float = 0.0,
    evidence_count: int = 0,
) -> CandidateAssessment:

    score = round(
        (20 if vertical_match else 0)
        + 20 * publisher_program_confidence
        + 15 * active_demand_confidence
        + 10 * inventory_fit_confidence
        + 10 * integration_confidence
        + 10 * economics_confidence
        + 5 * compliance_confidence
        + (5 if contactable else 0)
        + min(5, evidence_count)
    )

    score = max(0, min(100, score))

    blockers: list[str] = []
    reasons: list[str] = []

    if vertical_match:
        reasons.append("vertical_match")

    if publisher_program_confidence >= 0.65:
        reasons.append("publisher_program")

    if active_demand_confidence >= 0.65:
        reasons.append("active_demand")

    if inventory_fit_confidence >= 0.65:
        reasons.append("inventory_fit")

    if negative_program_confidence >= 0.80:
        blockers.append("negative_program_evidence")

    relevance = (
        publisher_program_confidence >= 0.65
        or active_demand_confidence >= 0.65
    )

    if blockers:
        readiness = "REJECT"

    elif score >= 75 and evidence_count >= 2 and relevance:
        readiness = "READY_TO_APPROACH"

    elif score >= 50 and relevance:
        readiness = "VERIFY_REQUIREMENTS"

    else:
        readiness = "WATCH"

    return CandidateAssessment(
        score=score,
        readiness=readiness,
        blockers=tuple(blockers),
        reasons=tuple(reasons),
    )


def assess_supply_fit(
    *,
    buyer_verticals: Sequence[str],
    buyer_inventory_types: Sequence[str],
    buyer_geographies: Sequence[str],
    supply_vertical: str,
    supply_inventory_type: str,
    supply_geographies: Sequence[str],
    tracking_required: bool | None = None,
    tracking_ready: bool = False,
    subaffiliates_allowed: bool | None = None,
    uses_subaffiliates: bool = False,
) -> SupplyFit:

    blockers: list[str] = []
    unknowns: list[str] = []
    score = 100

    if buyer_verticals and supply_vertical not in buyer_verticals:
        blockers.append("vertical_mismatch")
        score -= 50

    if (
        buyer_inventory_types
        and supply_inventory_type not in buyer_inventory_types
    ):
        blockers.append("inventory_mismatch")
        score -= 50

    if (
        buyer_geographies
        and not set(buyer_geographies).intersection(supply_geographies)
    ):
        blockers.append("geography_mismatch")
        score -= 40

    if tracking_required is True and not tracking_ready:
        blockers.append("tracking_not_ready")
        score -= 35

    elif tracking_required is None:
        unknowns.append("tracking_requirement_unknown")

    if subaffiliates_allowed is False and uses_subaffiliates:
        blockers.append("subaffiliate_policy_mismatch")
        score -= 50

    score = max(0, min(100, score))

    if blockers:
        gate = "BLOCKED"

    elif score >= 80 and not unknowns:
        gate = "TEST_COMPATIBLE"

    else:
        gate = "VERIFY_REQUIREMENTS"

    return SupplyFit(
        score=score,
        gate=gate,
        blockers=tuple(blockers),
        unknowns=tuple(unknowns),
    )


_REPLY_FIELDS = {
    "traffic_origin": (
        r"\btraffic source\b",
        r"\bwhere .*?(?:traffic|demand|leads?).*?(?:originates?|comes?)\b",
    ),
    "inventory_type": (
        r"\bcalls? or forms?\b",
        r"\binventory type\b",
    ),
    "website": (
        r"\bwebsite\b",
        r"\bsite url\b",
        r"\bsite i can look at\b",
    ),
    "geography": (
        r"\bstates?\b",
        r"\bzips?\b",
        r"\bgeograph",
    ),
    "tracking": (
        r"\btracking\b",
        r"\brouting\b",
        r"\brtb\b",
        r"\bping[\s-]*post\b",
    ),
    "payout": (
        r"\bpayout\b",
        r"\brevshare\b",
        r"\brevenue share\b",
    ),
}


def interpret_reply(text: str) -> ReplyAssessment:

    text = re.sub(r"\s+", " ", text or "").strip()

    requested = tuple(
        sorted(
            name
            for name, patterns in _REPLY_FIELDS.items()
            if any(re.search(p, text, re.I) for p in patterns)
        )
    )

    if re.search(
        r"\bnot interested\b|\bnot a fit\b|\bdo not contact\b",
        text,
        re.I,
    ):
        return ReplyAssessment(
            "REJECTED",
            requested,
            "SUPPRESS_OR_CLOSE",
            0.98,
        )

    if re.search(
        r"\bnot currently accepting\b|\bprogram paused\b|\bno capacity\b",
        text,
        re.I,
    ):
        return ReplyAssessment(
            "PAUSED",
            requested,
            "REVERIFY_LATER",
            0.90,
        )

    meeting = bool(
        re.search(
            r"\bbook\b.*\b(?:call|meeting)\b|\bcalendly\b|\bmeeting time\b",
            text,
            re.I,
        )
    )

    if meeting and requested:
        return ReplyAssessment(
            "MEETING_AND_INFORMATION_REQUEST",
            requested,
            "ANSWER_OPEN_FIELDS_THEN_MEETING",
            0.90,
        )

    if meeting:
        return ReplyAssessment(
            "MEETING_REQUEST",
            (),
            "PREPARE_MEETING",
            0.88,
        )

    if requested:
        return ReplyAssessment(
            "INFORMATION_REQUEST",
            requested,
            "ANSWER_REQUESTED_FIELDS",
            0.85,
        )

    return ReplyAssessment(
        "UNKNOWN",
        (),
        "HUMAN_REVIEW",
        0.40,
    )


def observed_unit_economics(
    events: Iterable[Mapping[str, object]],
) -> dict[str, object]:

    submitted = accepted = rejected = 0

    revenue = Decimal("0")
    cost = Decimal("0")

    revenue_seen = False
    cost_seen = False

    for event in events:

        event_type = str(event.get("event_type") or "")
        units = max(0, int(event.get("units") or 1))

        if event_type == "SUBMITTED":
            submitted += units

        elif event_type == "LEAD_ACCEPTED":
            accepted += units

        elif event_type == "LEAD_REJECTED":
            rejected += units

        elif (
            event_type == "REALISED_REVENUE"
            and event.get("value") is not None
        ):
            revenue += Decimal(str(event["value"]))
            revenue_seen = True

        elif (
            event_type == "OBSERVED_COST"
            and event.get("value") is not None
        ):
            cost += Decimal(str(event["value"]))
            cost_seen = True

    if submitted == 0 and accepted + rejected:
        submitted = accepted + rejected

    return {
        "submitted": submitted,
        "accepted": accepted,
        "rejected": rejected,

        "acceptance_rate":
            accepted / submitted
            if submitted
            else None,

        "realised_revenue":
            revenue
            if revenue_seen
            else None,

        "observed_cost":
            cost
            if cost_seen
            else None,

        "realised_margin":
            revenue - cost
            if revenue_seen and cost_seen
            else None,

        "revenue_per_accepted":
            revenue / accepted
            if revenue_seen and accepted
            else None,
    }


def assess_lane_health(
    *,
    active_buyers: int,
    observed_supply_volume: int | None,
    buyer_caps: Sequence[int | None],
    accepted_today: Sequence[int | None] = (),
) -> LaneHealth:

    remaining_values: list[int] = []
    unknown_caps = 0

    for index, cap in enumerate(buyer_caps):

        if cap is None:
            unknown_caps += 1
            continue

        used = (
            int(accepted_today[index] or 0)
            if index < len(accepted_today)
            else 0
        )

        remaining_values.append(
            max(0, int(cap) - used)
        )

    remaining = (
        sum(remaining_values)
        if remaining_values
        else None
    )

    gap = None

    if (
        observed_supply_volume is not None
        and remaining is not None
    ):
        gap = max(
            0,
            int(observed_supply_volume) - remaining,
        )

    if active_buyers <= 0:
        state = "CRITICAL"
        concentration = "NO_ACTIVE_BUYER"

    elif active_buyers == 1:
        state = (
            "SHORT_CAPACITY"
            if gap
            else "THIN"
        )
        concentration = "SINGLE_BUYER_RISK"

    else:
        state = (
            "SHORT_CAPACITY"
            if gap
            else "COVERED"
        )
        concentration = "REDUNDANT"

    if unknown_caps and state == "COVERED":
        state = "PARTIAL_VISIBILITY"

    discovery_required = (
        active_buyers < 2
        or bool(gap)
    )

    return LaneHealth(
        state=state,
        concentration=concentration,
        remaining_capacity=remaining,
        observed_gap=gap,
        discovery_required=discovery_required,
    )


def bounded_test_plan(
    *,
    requested_units: int,
    safety_max_units: int,
    buyer_remaining_cap: int | None = None,
    verified_supply_available: int | None = None,
) -> BoundedTestPlan:

    limits = [
        requested_units,
        safety_max_units,
    ]

    if buyer_remaining_cap is not None:
        limits.append(
            max(0, buyer_remaining_cap)
        )

    if verified_supply_available is not None:
        limits.append(
            max(0, verified_supply_available)
        )

    units = min(limits)

    if units <= 0:

        return BoundedTestPlan(
            gate="BLOCKED",
            units=0,
            authority="PROPOSAL_ONLY",
            stop_conditions=("do_not_start",),
        )

    return BoundedTestPlan(
        gate="PROPOSED",
        units=units,
        authority="PROPOSAL_ONLY",
        stop_conditions=(
            "buyer_cap_reached",
            "tracking_failure",
            "source_mismatch",
            "compliance_mismatch",
        ),
    )
