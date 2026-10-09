# EMPIRE_WAVE_089
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable


CONTROL_NAMES = (
    "entity_classification",
    "canonical_identity",
    "duplicate_detection",
    "input_quality",
    "output_quality",
    "evidence_lineage",
    "conflict_detection",
    "freshness",
    "quarantine",
    "action_authority",
    "outcome_linkage",
)


@dataclass(frozen=True)
class DetectionEnvelope:
    lane: str
    entity_type: str
    canonical_id: str | None
    generation_id: str | None
    source_id: str | None
    detector: str
    code: str
    severity: str
    confidence: float
    reason: str
    action_allowed: bool
    evidence: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaneContract:
    lane: str
    description: str
    source_patterns: tuple[str, ...]
    runtime_patterns: tuple[str, ...]
    systemd_patterns: tuple[str, ...]
    required_controls: tuple[str, ...] = CONTROL_NAMES

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


LANES = (
    LaneContract(
        lane="buyer_network",
        description="Buyer discovery, verification, ranking and commercial readiness.",
        source_patterns=(
            "buyer",
            "lead_smart",
        ),
        runtime_patterns=(
            "buyer",
            "leadsmart",
        ),
        systemd_patterns=(
            "buyer",
        ),
    ),

    LaneContract(
        lane="leads",
        description="Lead, prospect and demand-signal acquisition.",
        source_patterns=(
            "lead_",
            "prospect",
            "permit",
            "intent",
            "community",
        ),
        runtime_patterns=(
            "lead",
            "prospect",
            "permit",
            "intent",
        ),
        systemd_patterns=(
            "lead",
            "permit",
            "intent",
        ),
    ),

    LaneContract(
        lane="people_contacts",
        description="People, contacts, companies and contactability.",
        source_patterns=(
            "contact",
            "person",
            "people",
            "enrichment",
        ),
        runtime_patterns=(
            "contact",
            "person",
            "enrichment",
        ),
        systemd_patterns=(
            "contact",
            "enrichment",
        ),
    ),

    LaneContract(
        lane="opportunities",
        description="Opportunity detection, prioritisation and allocation.",
        source_patterns=(
            "opportunity",
            "radar",
            "trigger",
            "demand",
        ),
        runtime_patterns=(
            "opportunity",
            "radar",
            "demand",
        ),
        systemd_patterns=(
            "opportunity",
            "radar",
        ),
    ),

    LaneContract(
        lane="conversations_replies",
        description="Inbound/outbound conversations, replies and threads.",
        source_patterns=(
            "reply",
            "conversation",
            "mailbox",
            "thread",
        ),
        runtime_patterns=(
            "reply",
            "conversation",
            "mailbox",
        ),
        systemd_patterns=(
            "reply",
            "mailbox",
        ),
    ),

    LaneContract(
        lane="campaigns",
        description="SEO, Lead Smart, acquisition and outbound campaign state.",
        source_patterns=(
            "campaign",
            "seo",
            "lead_smart",
            "outbound",
        ),
        runtime_patterns=(
            "campaign",
            "seo",
            "leadsmart",
            "outbound",
        ),
        systemd_patterns=(
            "campaign",
            "seo",
            "outbound",
        ),
    ),

    LaneContract(
        lane="agent_tasks",
        description="Agent work, task ownership, scheduling and completion.",
        source_patterns=(
            "agent",
            "task",
            "department_cycle",
            "dispatcher",
        ),
        runtime_patterns=(
            "agent",
            "task",
            "department",
            "dispatcher",
        ),
        systemd_patterns=(
            "agent",
            "department",
            "dispatcher",
        ),
    ),

    LaneContract(
        lane="products_offers",
        description="Product identity, versions, offers, pricing and fulfilment binding.",
        source_patterns=(
            "product",
            "offer",
            "catalog",
            "fulfil",
            "fulfill",
        ),
        runtime_patterns=(
            "product",
            "offer",
            "catalog",
            "fulfil",
            "fulfill",
        ),
        systemd_patterns=(
            "product",
            "offer",
            "fulfil",
            "fulfill",
        ),
    ),

    LaneContract(
        lane="consent_suppression",
        description="Consent, suppression, compliance and communication authority.",
        source_patterns=(
            "consent",
            "suppress",
            "compliance",
            "dnc",
            "do_not_call",
        ),
        runtime_patterns=(
            "consent",
            "suppress",
            "compliance",
        ),
        systemd_patterns=(
            "consent",
            "suppress",
            "compliance",
        ),
    ),

    LaneContract(
        lane="orders_payments_revenue",
        description="Order, payment, fulfilment and realised-revenue event chain.",
        source_patterns=(
            "payment",
            "order",
            "revenue",
            "fulfil",
            "fulfill",
        ),
        runtime_patterns=(
            "payment",
            "order",
            "revenue",
            "fulfil",
            "fulfill",
        ),
        systemd_patterns=(
            "payment",
            "order",
            "revenue",
            "fulfil",
            "fulfill",
        ),
    ),

    LaneContract(
        lane="economic_memory",
        description="Outcome learning and economic-memory attribution.",
        source_patterns=(
            "economic_memory",
            "economic",
            "memory",
        ),
        runtime_patterns=(
            "economic",
            "memory",
        ),
        systemd_patterns=(
            "economic",
            "memory",
        ),
    ),

    LaneContract(
        lane="predictive_revenue",
        description="Predictive Revenue, Predictive Cloud and forecasting.",
        source_patterns=(
            "predictive_revenue",
            "predictive_cloud",
            "forecast",
            "trend",
        ),
        runtime_patterns=(
            "predictive",
            "forecast",
            "trend",
        ),
        systemd_patterns=(
            "predictive",
            "forecast",
        ),
    ),
)


CONTROL_TERMS = {
    "entity_classification": (
        "entity_type",
        "classify",
        "entity_classification",
    ),

    "canonical_identity": (
        "canonical_identity",
        "canonical_id",
        "identity_resolution",
        "canonical_person",
        "identity_fingerprint",
    ),

    "duplicate_detection": (
        "dedupe",
        "duplicate",
        "idempot",
        "fingerprint",
    ),

    "input_quality": (
        "input_quality",
        "validation",
        "validate_",
        "quality_gate",
    ),

    "output_quality": (
        "output_quality",
        "output_decision",
        "validate_output",
        "output_gate",
    ),

    "evidence_lineage": (
        "source_lineage",
        "provenance",
        "evidence",
        "trace_id",
    ),

    "conflict_detection": (
        "conflict",
        "contradiction",
        "reconcile",
        "reconciliation",
    ),

    "freshness": (
        "freshness",
        "stale",
        "generated_at",
        "updated_at",
    ),

    "quarantine": (
        "quarantine",
        "hold_for_verification",
        "held",
        "reject",
    ),

    "action_authority": (
        "authority",
        "governor",
        "founder_gate",
        "approved",
        "fail_close",
        "fail_closed",
    ),

    "outcome_linkage": (
        "outcome",
        "realised",
        "realized",
        "conversion",
        "economic_memory",
        "fulfilment",
        "fulfillment",
    ),
}


BUYER_RUNTIME_VERIFIED = {
    "entity_classification":
        "runtime/truth_quality_control/entity_type_latest.json",

    "canonical_identity":
        "runtime/identity_resolution/buyer_identity_latest.json",

    "duplicate_detection":
        "runtime/identity_resolution/buyer_identity_latest.json",

    "input_quality":
        "runtime/truth_quality_control/buyer_input_latest.json",

    "output_quality":
        "runtime/truth_quality_control/buyer_output_latest.json",

    "evidence_lineage":
        "runtime/buyer_network_intelligence/verification_latest.json",

    "conflict_detection":
        "runtime/control_plane/detection_fusion_latest.json",

    "freshness":
        "runtime/truth_quality_control/entity_type_latest.json",

    "quarantine":
        "runtime/truth_quality_control/entity_type_quarantine_latest.json",

    "action_authority":
        "runtime/control_plane/architecture_gap_latest.json",

    "outcome_linkage":
        None,
}


def stable_id(
    *parts: str,
) -> str:

    raw = "|".join(
        str(part or "").strip().lower()
        for part in parts
    )

    return sha256(
        raw.encode("utf-8")
    ).hexdigest()[:24]


def source_matches_lane(
    path: Path,
    lane: LaneContract,
) -> bool:

    value = str(path).lower()

    return any(
        token in value
        for token in lane.source_patterns
    )


def runtime_matches_lane(
    path: Path,
    lane: LaneContract,
) -> bool:

    value = str(path).lower()

    return any(
        token in value
        for token in lane.runtime_patterns
    )


def systemd_matches_lane(
    name: str,
    lane: LaneContract,
) -> bool:

    value = name.lower()

    return any(
        token in value
        for token in lane.systemd_patterns
    )


def control_hits(
    text: str,
) -> dict[str, list[str]]:

    lowered = text.lower()

    result = {}

    for control, terms in CONTROL_TERMS.items():

        hits = sorted(
            {
                term
                for term in terms
                if term in lowered
            }
        )

        if hits:
            result[control] = hits

    return result


def coverage_status(
    *,
    runtime_verified: bool,
    source_evidence: bool,
) -> str:

    if runtime_verified:
        return "VERIFIED_RUNTIME"

    if source_evidence:
        return "SOURCE_EVIDENCE_ONLY"

    return "MISSING_OR_UNVERIFIED"


def lane_risk(
    lane_status: str,
    control_statuses: Iterable[str],
) -> str:

    statuses = tuple(
        control_statuses
    )

    if lane_status == "NOT_DETECTED":
        return "INACTIVE_OR_UNKNOWN"

    verified = sum(
        status == "VERIFIED_RUNTIME"
        for status in statuses
    )

    source_only = sum(
        status == "SOURCE_EVIDENCE_ONLY"
        for status in statuses
    )

    missing = sum(
        status == "MISSING_OR_UNVERIFIED"
        for status in statuses
    )

    total = len(
        statuses
    )

    unverified = (
        source_only
        + missing
    )

    # CONTROLLED has one meaning:
    # every required control has runtime proof.
    if (
        total > 0
        and verified == total
    ):
        return "CONTROLLED"

    # An active runtime with mostly unverified
    # controls deserves the highest scrutiny.
    if lane_status == "ACTIVE_RUNTIME":

        if unverified >= 8:
            return "HIGH"

        if unverified >= 4:
            return "MEDIUM"

        return "LOW"

    # Source-present lanes are not live-runtime
    # controlled merely because code mentions
    # the right concepts.
    if lane_status == "SOURCE_PRESENT":

        if unverified >= 9:
            return "HIGH"

        if unverified >= 5:
            return "MEDIUM"

        return "LOW"

    return "HIGH"
