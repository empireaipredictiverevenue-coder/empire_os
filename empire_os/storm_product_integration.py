"""Storm / Weather Intelligence integration foundation (OBSERVE only).

Architecture delta / diagram:
    source event -> canonical entity exposure -> inferred score -> product match
Owner: Intelligence Fabric, natural_physical/property intelligence; commercial
consumers are product catalog, governed buyer allocation and Founder surfaces.
Existing storm_revenue_multiplier owns priority modeling; this module adds typed,
tenant-scoped provenance and readiness contracts, not a second acquisition path.
EmpireDB remains canonical. Callers must supply verified canonical identities and
source records; references are provenance, not independent verification of truth.
No persistence, network, scheduler, outbound, terms acceptance, funds, revenue
recognition or authority expansion occurs here. Astra may inspect; Needle may
route proposals. This deterministic worker owns only this module and its tests.
Synchronous, immutable, replayable evaluation has no retries or shared state.
Identity tuples permit consumer dedupe; consumers own bounded queues/timeouts.
Dependency loss fails closed with blockers; recovery requires fresh evidence.
Outputs expose evidence, evaluation time and blockers for Founder review. Costs
and economics remain unknown. Rollback is removal of this unused adapter.
Focused/adjacent tests verify contracts; live source, EmpireDB, shadow operation
and Founder surface verification remain required before production promotion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from math import isfinite

from empire_os.storm_revenue_multiplier import calculate_storm_multiplier


class TruthClass(str, Enum):
    OBSERVED = "OBSERVED"
    FORECAST = "FORECAST"
    INFERRED = "INFERRED"


class SubjectKind(str, Enum):
    PROPERTY = "property"
    BUSINESS = "business"


def _text(*values: str) -> None:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("nonempty identifiers and provenance required")


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")


def _unit(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("finite value in [0, 1] required")


@dataclass(frozen=True)
class Evidence:
    tenant_id: str
    ref: str
    source: str
    observed_at: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        _text(self.tenant_id, self.ref, self.source)
        _time(self.observed_at)
        _time(self.valid_until)
        if self.valid_until <= self.observed_at:
            raise ValueError("evidence validity must have positive duration")


def _evidence(items: tuple[Evidence, ...], tenant: str) -> None:
    if not isinstance(items, tuple) or not items:
        raise ValueError("nonempty immutable evidence required")
    if any(not isinstance(e, Evidence) or e.tenant_id != tenant for e in items):
        raise ValueError("evidence tenant mismatch")


@dataclass(frozen=True)
class StormEvent:
    tenant_id: str
    event_id: str
    event_type: str
    severity: str
    starts_at: datetime
    ends_at: datetime
    truth_class: TruthClass
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _text(self.tenant_id, self.event_id, self.event_type, self.severity)
        _time(self.starts_at)
        _time(self.ends_at)
        if self.ends_at < self.starts_at:
            raise ValueError("event interval reversed")
        if not isinstance(self.truth_class, TruthClass) or self.truth_class not in (TruthClass.OBSERVED, TruthClass.FORECAST):
            raise ValueError("event must be observed or forecast")
        _evidence(self.evidence, self.tenant_id)


@dataclass(frozen=True)
class AffectedSubject:
    """Evidenced exposure association, never a claim of verified damage."""

    tenant_id: str
    event_id: str
    canonical_id: str
    kind: SubjectKind
    niche: str
    territory_id: str
    confidence: float
    territory_overlap: float
    evidence: tuple[Evidence, ...]
    truth_class: TruthClass = field(default=TruthClass.INFERRED, init=False)

    def __post_init__(self) -> None:
        _text(self.tenant_id, self.event_id, self.canonical_id, self.niche, self.territory_id)
        if not isinstance(self.kind, SubjectKind):
            raise ValueError("property or business subject required")
        _unit(self.confidence)
        _unit(self.territory_overlap)
        _evidence(self.evidence, self.tenant_id)


@dataclass(frozen=True)
class BuyerProductMatch:
    """Supplied catalog/buyer fit evidence; does not allocate or deliver."""

    tenant_id: str
    buyer_id: str
    product_id: str
    niche: str
    territory_id: str
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        _text(self.tenant_id, self.buyer_id, self.product_id, self.niche, self.territory_id)
        _evidence(self.evidence, self.tenant_id)


class ReadinessGate(str, Enum):
    RECURRING_FEED = "recurring_feed"
    SOURCE_RIGHTS = "source_rights"
    ENRICHMENT = "enrichment"
    BUYER_APPROVAL = "buyer_approval"
    CAPACITY = "capacity"
    APPROVED_TERMS = "approved_terms"
    ENTITLEMENT = "entitlement"
    USAGE_METERING = "usage_metering"
    GOVERNED_DELIVERY = "governed_delivery"
    LIVE_CANONICAL_VERIFICATION = "live_canonical_verification"
    FOUNDER_SURFACE = "founder_surface"


@dataclass(frozen=True)
class ReadinessProof:
    """Evidence scoped to this exact event/entity/buyer/product proposal."""

    gate: ReadinessGate
    scope: tuple[str, str, str, str, str]
    evidence: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.gate, ReadinessGate):
            raise ValueError("unknown readiness gate")
        if not isinstance(self.scope, tuple) or len(self.scope) != 5:
            raise ValueError("tenant/event/subject/buyer/product scope required")
        _text(*self.scope)
        _evidence(self.evidence, self.scope[0])


@dataclass(frozen=True)
class StormScore:
    priority_boost: float
    multiplier: float
    evidence_refs: tuple[str, ...]
    truth_class: TruthClass = field(default=TruthClass.INFERRED, init=False)
    model_version: str = field(default="storm_revenue_multiplier:v1", init=False)


@dataclass(frozen=True)
class StormProductAssessment:
    scope: tuple[str, str, str, str, str]
    evaluated_at: datetime
    score: StormScore | None
    match: BuyerProductMatch | None
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = field(default="OBSERVE", init=False)
    commercial_ready: bool = field(default=False, init=False)
    economics: None = field(default=None, init=False)


def assess_storm_product(
    event: StormEvent,
    subject: AffectedSubject,
    candidate: BuyerProductMatch,
    *,
    now: datetime,
    proofs: tuple[ReadinessProof, ...] = (),
    max_event_age: timedelta = timedelta(days=7),
) -> StormProductAssessment:
    """Evaluate supplied evidence only; missing/stale inputs never create leads.

    A cleared evidence gate is not commercial permission. Founder approval remains
    a blocker even when all readiness proofs are supplied.
    """
    _time(now)
    if not timedelta(0) < max_event_age <= timedelta(days=7):
        raise ValueError("event freshness must be positive and at most seven days")
    if event.tenant_id != subject.tenant_id or event.tenant_id != candidate.tenant_id:
        raise ValueError("tenant mismatch")
    if subject.event_id != event.event_id:
        raise ValueError("event association mismatch")
    scope = (event.tenant_id, event.event_id, subject.canonical_id, candidate.buyer_id, candidate.product_id)
    if not isinstance(proofs, tuple) or any(p.scope != scope for p in proofs):
        raise ValueError("readiness scope mismatch")
    if len({p.gate for p in proofs}) != len(proofs):
        raise ValueError("duplicate readiness gate")

    def fresh(items: tuple[Evidence, ...]) -> bool:
        return all(e.observed_at <= now < e.valid_until for e in items)

    blockers = []
    evidence = event.evidence + subject.evidence + candidate.evidence
    refs = tuple(dict.fromkeys(e.ref for e in evidence))
    if not fresh(event.evidence + subject.evidence):
        blockers.append("event_or_subject_evidence_stale_or_future")
    if event.truth_class != TruthClass.OBSERVED or event.starts_at > now:
        blockers.append("observed_event_required")
    if now - event.ends_at > max_event_age:
        blockers.append("event_stale")
    if subject.confidence == 0 or subject.territory_overlap == 0:
        blockers.append("affected_subject_not_supported")
    score = None
    if not blockers:
        modeled = calculate_storm_multiplier(
            niche=subject.niche, event_type=event.event_type, severity=event.severity,
            evidence_confidence=subject.confidence,
            territory_match=subject.territory_overlap,
            age_hours=max(0.0, (now - event.ends_at).total_seconds() / 3600),
            evidence_refs=tuple(dict.fromkeys(e.ref for e in event.evidence + subject.evidence)),
        )
        if modeled.relevant and event.severity.lower().strip() in {"minor", "moderate", "severe", "extreme"}:
            score = StormScore(modeled.priority_boost, modeled.multiplier, modeled.evidence_refs)
        else:
            blockers.append("unsupported_event_niche_or_severity")
    match = None
    if not fresh(candidate.evidence):
        blockers.append("buyer_product_evidence_stale_or_future")
    elif candidate.niche != subject.niche or candidate.territory_id != subject.territory_id:
        blockers.append("buyer_product_fit_mismatch")
    elif score is not None:
        match = candidate
    by_gate = {p.gate: p for p in proofs}
    for gate in ReadinessGate:
        proof = by_gate.get(gate)
        if proof is None or not fresh(proof.evidence):
            blockers.append(f"{gate.value}_evidence_required")
    refs = tuple(dict.fromkeys((*refs, *(e.ref for p in proofs for e in p.evidence))))
    blockers.append("founder_commercial_authority_required")
    return StormProductAssessment(scope, now, score, match, tuple(blockers), refs)
