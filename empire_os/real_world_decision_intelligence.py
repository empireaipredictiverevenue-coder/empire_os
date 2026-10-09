"""Pure, non-economic decision recommendations; never execution permissions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from itertools import islice
import json
import os
from pathlib import Path
import tempfile

from empire_os.real_world_exposure_graph import ObserveOnly, normalized, text, confidence
from empire_os.real_world_impact_intelligence import (
    ImpactAssessment, ImpactTruth, EvidenceClass, _hash, _sha, replay_impact_snapshot,
)
from empire_os.real_world_future_state_intelligence import (
    FutureStateForecast, Scenario, _time, _strings, _validate_assessment,
    validate_forecast, replay_forecast, forecast_freshness,
)

SCHEMA_VERSION = "empire.real_world_decision.v1"
MAX_CANDIDATES = 32
MAX_DIAGNOSTICS = 16
MAX_SNAPSHOT_BYTES = 2_000_000


class CandidateType(str, Enum):
    OBSERVE = "OBSERVE"
    WAIT = "WAIT"
    GATHER_EVIDENCE = "GATHER_EVIDENCE"
    PREPARE = "PREPARE"
    REVIEW = "REVIEW"
    ESCALATE_FOR_REVIEW = "ESCALATE_FOR_REVIEW"
    NO_ACTION = "NO_ACTION"
    OTHER = "OTHER"


class DecisionState(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OBSERVE = "OBSERVE"
    WAIT = "WAIT"
    GATHER_EVIDENCE = "GATHER_EVIDENCE"
    RECOMMEND = "RECOMMEND"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_ACTION = "NO_ACTION"
    UNKNOWN = "UNKNOWN"


class WaitingRiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DecisionContext(ObserveOnly):
    tenant_id: str
    event_id: str
    subject_id: str | None
    assessment: ImpactAssessment
    forecasts: tuple[FutureStateForecast, ...]
    as_of: datetime
    objective: str
    constraints: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        for name in ("tenant_id", "event_id", "objective"):
            object.__setattr__(self, name, text(getattr(self, name)))
        if self.subject_id is not None:
            object.__setattr__(self, "subject_id", text(self.subject_id))
        object.__setattr__(self, "as_of", _time(self.as_of))
        object.__setattr__(self, "constraints", _strings(self.constraints, limit=32))
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid_schema")
        _validate_assessment(self.assessment)
        if self.assessment.tenant_id != self.tenant_id:
            raise ValueError("cross_tenant_mismatch")
        if any(not self.matches(e) for e in self.assessment.evidence):
            raise ValueError("cross_event_or_subject_mismatch")
        if any(max(e.observed_at, e.processed_at, e.valid_from) > self.as_of for e in self.assessment.evidence):
            raise ValueError("future_leakage")
        if not isinstance(self.forecasts, (tuple, list)) or len(self.forecasts) > MAX_CANDIDATES:
            raise ValueError("forecast_limit")
        retained = {}
        for f in self.forecasts:
            if not isinstance(f, FutureStateForecast) or not self.matches(f):
                raise ValueError("cross_forecast_scope")
            validate_forecast(f, self.assessment)
            if f.retrospective or max(f.forecast_origin_time, f.generated_at) > self.as_of:
                raise ValueError("future_or_backtest_forecast")
            old = retained.get(f.forecast_id)
            if old is None or f.generated_at < old.generated_at:
                retained[f.forecast_id] = f
        object.__setattr__(self, "forecasts", tuple(retained[k] for k in sorted(retained)))

    def matches(self, item):
        return (item.tenant_id == self.tenant_id and item.event_id == self.event_id
                and (self.subject_id is None or item.subject_id == self.subject_id))

    @property
    def evidence_hashes(self):
        return tuple(sorted(e.evidence_hash for e in self.assessment.evidence))

    @property
    def future_assessment_hash(self):
        return _hash(tuple(f.forecast_hash for f in self.forecasts))

    @property
    def forecast_origins(self):
        return tuple(sorted(set(f.forecast_origin_time for f in self.forecasts)))

    @property
    def context_id(self):
        return _hash(dict(tenant=self.tenant_id, event=self.event_id, subject=self.subject_id,
                          impact=self.assessment.assessment_id, future=self.future_assessment_hash,
                          evidence=self.evidence_hashes, origins=self.forecast_origins,
                          as_of=self.as_of, objective=self.objective, constraints=self.constraints,
                          schema_version=self.schema_version))

    def as_dict(self):
        return dict(normalized(self), assessment=self.assessment.as_dict(),
                    forecasts=[f.as_dict() for f in self.forecasts], context_id=self.context_id,
                    evidence_hashes=list(self.evidence_hashes),
                    impact_assessment_hash=self.assessment.assessment_id,
                    future_assessment_hash=self.future_assessment_hash,
                    forecast_origins=normalized(self.forecast_origins))


@dataclass(frozen=True)
class DecisionWindow(ObserveOnly):
    earliest_action_time: datetime | None = None
    latest_useful_action_time: datetime | None = None
    review_at: datetime | None = None
    expires_at: datetime | None = None
    supporting_forecasts: tuple[str, ...] = ()

    def __post_init__(self):
        super().__post_init__()
        for name in ("earliest_action_time", "latest_useful_action_time", "review_at", "expires_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _time(getattr(self, name)))
        object.__setattr__(self, "supporting_forecasts", _strings(self.supporting_forecasts, hashes=True))
        start, end = self.earliest_action_time, self.latest_useful_action_time
        if start and end and start > end:
            raise ValueError("invalid_window")
        if self.expires_at and any(t and t > self.expires_at for t in (start, end, self.review_at)):
            raise ValueError("invalid_window")

    def stale_at(self, as_of):
        now = _time(as_of)
        return any(t is not None and now >= t for t in (self.expires_at, self.latest_useful_action_time))


_DIMENSIONS = ("evidence_strength", "forecast_support", "uncertainty", "urgency", "reversibility",
               "optionality", "information_gap", "time_sensitivity", "downside_risk", "confidence")
_LOWER_BETTER = {"uncertainty", "information_gap", "downside_risk"}


@dataclass(frozen=True)
class QualityDimensions(ObserveOnly):
    """Explicit ordinal/unit dimensions; None is unknown, never a zero or economics."""
    evidence_strength: float | None = None
    forecast_support: float | None = None
    uncertainty: float | None = None
    urgency: float | None = None
    reversibility: float | None = None
    optionality: float | None = None
    information_gap: float | None = None
    time_sensitivity: float | None = None
    downside_risk: float | None = None
    confidence: float | None = None

    def __post_init__(self):
        super().__post_init__()
        for name in _DIMENSIONS:
            value = confidence(getattr(self, name))
            if value is not None:
                object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class InformationRequest(ObserveOnly):
    missing_evidence: tuple[str, ...]
    decision_sensitive_uncertainty: str
    recommended_evidence_class: EvidenceClass
    reason: str
    expected_decision_effect: str
    priority: str = "REVIEW"
    could_change_recommendation: bool | None = None

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "missing_evidence", _strings(self.missing_evidence, required=True, limit=16))
        object.__setattr__(self, "recommended_evidence_class", EvidenceClass(self.recommended_evidence_class))
        for name in ("decision_sensitive_uncertainty", "reason", "expected_decision_effect"):
            object.__setattr__(self, name, text(getattr(self, name)))
        if self.priority not in ("HIGH", "REVIEW", "LOW", "UNKNOWN") or self.could_change_recommendation not in (True, False, None):
            raise ValueError("invalid_information_request")
        if self.could_change_recommendation is not None and type(self.could_change_recommendation) is not bool:
            raise ValueError("invalid_information_request")


@dataclass(frozen=True)
class CounterfactualReference(ObserveOnly):
    forecast_id: str
    scenario: Scenario
    hypothetical: bool = True
    causal_effect: str = "unknown"

    def __post_init__(self):
        super().__post_init__()
        _sha(self.forecast_id)
        object.__setattr__(self, "scenario", Scenario(self.scenario))
        if self.hypothetical is not True or self.causal_effect != "unknown":
            raise ValueError("causal_simulation_forbidden")


@dataclass(frozen=True)
class DecisionCandidate(ObserveOnly):
    context_id: str
    action_class: CandidateType
    why_considered: str
    supporting_evidence: tuple[str, ...] = ()
    supporting_forecasts: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    uncertainties: tuple[str, ...] = ()
    reversibility: str = "UNKNOWN"
    reason_codes: tuple[str, ...] = ()
    dimensions: QualityDimensions = QualityDimensions()
    information_requests: tuple[InformationRequest, ...] = ()
    counterfactuals: tuple[CounterfactualReference, ...] = ()
    window: DecisionWindow = DecisionWindow()

    def __post_init__(self):
        super().__post_init__()
        _sha(self.context_id)
        object.__setattr__(self, "action_class", CandidateType(self.action_class))
        object.__setattr__(self, "why_considered", text(self.why_considered))
        for name in ("supporting_evidence", "supporting_forecasts", "assumptions", "constraints", "uncertainties", "reason_codes"):
            object.__setattr__(self, name, _strings(getattr(self, name), hashes=name.startswith("supporting"), limit=32))
        if not self.reason_codes or self.reversibility not in ("REVERSIBLE", "PARTIAL", "IRREVERSIBLE", "UNKNOWN"):
            raise ValueError("invalid_candidate_explanation")
        if not isinstance(self.dimensions, QualityDimensions) or not isinstance(self.window, DecisionWindow):
            raise ValueError("invalid_candidate_metadata")
        for name, cls in (("information_requests", InformationRequest), ("counterfactuals", CounterfactualReference)):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or len(values) > 16 or any(not isinstance(v, cls) for v in values):
                raise ValueError("invalid_candidate_metadata")
            object.__setattr__(self, name, tuple(sorted(set(values), key=_hash)))

    @property
    def candidate_id(self):
        return _hash(self)

    def as_dict(self):
        return dict(normalized(self), candidate_id=self.candidate_id)


def replay_candidate(row):
    data = dict(row)
    identity = data.pop("candidate_id")
    data["dimensions"] = QualityDimensions(**data["dimensions"])
    data["window"] = DecisionWindow(**data["window"])
    data["information_requests"] = tuple(InformationRequest(**r) for r in data["information_requests"])
    data["counterfactuals"] = tuple(CounterfactualReference(**r) for r in data["counterfactuals"])
    result = DecisionCandidate(**data)
    if result.candidate_id != identity:
        raise ValueError("tampered_candidate")
    return result


def next_best_evidence(context):
    """Translate the upstream physical-verification gap into decision information."""
    current = [a for a in context.assessment.assertions if a.valid_from <= context.as_of < a.valid_until]
    verified = any(a.finding == "present" and ImpactTruth.VERIFIED in
                   (a.impact_truth, a.physical_truth, a.damage_truth) for a in current)
    if not verified:
        return (InformationRequest(("physical_verification_missing",), "impact_presence_unresolved",
                EvidenceClass.FIELD, "physical_verification_missing",
                "Verification may change observe/gather to prepare or review; never authorize execution.",
                "REVIEW", True),)
    return (InformationRequest(("future_outcome_unobserved",), "forecast_outcome_uncertain",
            EvidenceClass.FIRST_PARTY, "forecast_is_not_outcome",
            "A later observation may confirm or contradict the forecast and change review priority.",
            "REVIEW", None),)


def evaluate_dimensions(context, action):
    """Only source confidence and explicit evidence gaps have numeric support in V1."""
    assertions = [a for a in context.assessment.assertions if a.valid_from <= context.as_of < a.valid_until]
    values = [a.confidence for a in assertions]
    strength = min(values) if values and all(v is not None for v in values) else None
    # Confidence describes input support, not probability the recommendation is optimal.
    return QualityDimensions(evidence_strength=strength, confidence=strength,
        information_gap=1.0 if next_best_evidence(context)[0].could_change_recommendation is True else None)


def validate_candidate(candidate, context):
    if candidate.context_id != context.context_id:
        raise ValueError("cross_context_candidate")
    if candidate.supporting_evidence != context.evidence_hashes:
        raise ValueError("invalid_evidence_lineage")
    forecasts = {f.forecast_id: f for f in context.forecasts}
    if candidate.supporting_forecasts != tuple(sorted(forecasts)):
        raise ValueError("invalid_forecast_lineage")
    if not set(context.constraints) <= set(candidate.constraints):
        raise ValueError("missing_context_constraints")
    if candidate.dimensions != evaluate_dimensions(context, candidate.action_class):
        raise ValueError("unsupported_quality_dimensions")
    if candidate.information_requests != next_best_evidence(context):
        raise ValueError("unsupported_information_claim")
    for ref in candidate.counterfactuals:
        if ref.forecast_id not in candidate.supporting_forecasts or ref.scenario not in {
                b.scenario for b in forecasts[ref.forecast_id].branches}:
            raise ValueError("invalid_counterfactual_lineage")
    window = candidate.window
    if not set(window.supporting_forecasts) <= set(candidate.supporting_forecasts):
        raise ValueError("unsupported_window")
    supported_times = {t for fid in window.supporting_forecasts for t in
                       (forecasts[fid].forecast_origin_time, forecasts[fid].valid_until, forecasts[fid].target_time)}
    for name in ("earliest_action_time", "latest_useful_action_time", "review_at", "expires_at"):
        if getattr(window, name) is not None and getattr(window, name) not in supported_times:
            raise ValueError("unsupported_deadline")
    if candidate.action_class in (CandidateType.PREPARE, CandidateType.REVIEW):
        if not _verified_worsening(context):
            raise ValueError("unsupported_preparation")
    return candidate


def _verified_worsening(context):
    verified_scopes = {(a.tenant_id, a.event_id, a.subject_id, a.phenomenon, a.effect_category, a.domain)
                       for a in context.assessment.assertions
                       if a.finding == "present" and a.valid_from <= context.as_of < a.valid_until
                       and ImpactTruth.VERIFIED in (a.physical_truth, a.impact_truth, a.damage_truth)}
    return any(f.scope in verified_scopes and forecast_freshness(f, as_of=context.as_of).state == "CURRENT"
               and any(b.scenario in (Scenario.WORSENING, Scenario.ESCALATING) and b.probability is not None
                       and b.probability > 0 for b in f.branches) for f in context.forecasts)


def make_candidate(context, action, *, why="Evidence-backed consideration", reason_codes=("candidate_considered",),
                   window=None, counterfactuals=(), assumptions=(), uncertainties=()):
    action = CandidateType(action)
    return DecisionCandidate(context.context_id, action, why, context.evidence_hashes,
        tuple(f.forecast_id for f in context.forecasts), assumptions, context.constraints,
        uncertainties, "UNKNOWN", reason_codes, evaluate_dimensions(context, action),
        next_best_evidence(context), counterfactuals, window or DecisionWindow())


def dominates(a, b):
    """Strict Pareto dominance. Missing dimensions prevent ordering, including equal unknowns.

    Urgency/time sensitivity are context facts, not utility: they must be equal.
    Comparison is meaningful only for the same scope, constraints and evidence.
    """
    if (a.context_id, a.constraints, a.supporting_evidence, a.supporting_forecasts) != (
            b.context_id, b.constraints, b.supporting_evidence, b.supporting_forecasts):
        return False
    better = False
    for name in _DIMENSIONS:
        x, y = getattr(a.dimensions, name), getattr(b.dimensions, name)
        if x is None or y is None:
            return False
        if name in ("urgency", "time_sensitivity"):
            if x != y:
                return False
            continue
        if name in _LOWER_BETTER:
            x, y = -x, -y
        if x < y:
            return False
        better |= x > y
    return better


@dataclass(frozen=True)
class WaitingRisk(ObserveOnly):
    level: WaitingRiskLevel
    reason_codes: tuple[str, ...]
    supporting_forecasts: tuple[str, ...] = ()

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self, "level", WaitingRiskLevel(self.level))
        object.__setattr__(self, "reason_codes", _strings(self.reason_codes, required=True, limit=16))
        object.__setattr__(self, "supporting_forecasts", _strings(self.supporting_forecasts, hashes=True))


def waiting_risk(context):
    current = [f for f in context.forecasts if forecast_freshness(f, as_of=context.as_of).state == "CURRENT"]
    worsening = [f for f in current if any(b.scenario in (Scenario.WORSENING, Scenario.ESCALATING)
                 and b.probability is not None and b.probability > 0 for b in f.branches)]
    near = [f for f in worsening if (f.valid_until - context.as_of).total_seconds() <= 3600]
    if near:
        return WaitingRisk(WaitingRiskLevel.HIGH, ("supported_deterioration", "forecast_window_within_one_hour"),
                           tuple(f.forecast_id for f in near))
    if worsening:
        return WaitingRisk(WaitingRiskLevel.MODERATE, ("supported_deterioration",), tuple(f.forecast_id for f in worsening))
    return WaitingRisk(WaitingRiskLevel.UNKNOWN, ("waiting_risk_unsupported",))


@dataclass(frozen=True)
class DecisionRegret(ObserveOnly):
    decision_id: str
    recommended_candidate: str | None
    alternatives: tuple[str, ...]
    decision_time: datetime
    future_outcome_reference: str | None = None
    regret_classification: str = "UNRESOLVED"
    resolved_at: datetime | None = None

    def __post_init__(self):
        super().__post_init__()
        _sha(self.decision_id)
        if self.recommended_candidate is not None:
            _sha(self.recommended_candidate)
        object.__setattr__(self, "alternatives", _strings(self.alternatives, hashes=True, limit=32))
        object.__setattr__(self, "decision_time", _time(self.decision_time))
        if self.future_outcome_reference is not None or self.resolved_at is not None or self.regret_classification != "UNRESOLVED":
            raise ValueError("outcome_resolution_deferred")


@dataclass(frozen=True)
class DecisionRecommendation(ObserveOnly):
    context: DecisionContext
    candidates: tuple[DecisionCandidate, ...]
    state: DecisionState
    recommended_candidate: str | None
    alternatives: tuple[str, ...]
    reason_codes: tuple[str, ...]
    diagnostics: tuple[str, ...]
    waiting_risk: WaitingRisk
    ambiguous: bool = False
    economics: str = "unknown"

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.context, DecisionContext) or self.economics != "unknown":
            raise ValueError("invalid_recommendation")
        object.__setattr__(self, "state", DecisionState(self.state))
        if not isinstance(self.candidates, (list, tuple)) or len(self.candidates) > MAX_CANDIDATES:
            raise ValueError("candidate_limit")
        candidates = tuple(sorted(self.candidates, key=lambda c: c.candidate_id))
        for c in candidates:
            validate_candidate(c, self.context)
        object.__setattr__(self, "candidates", candidates)
        for name in ("alternatives", "reason_codes", "diagnostics"):
            object.__setattr__(self, name, _strings(getattr(self, name), hashes=name == "alternatives", limit=32))
        expected = _selection(self.context, candidates)
        if (self.state, self.recommended_candidate, self.alternatives, self.reason_codes, self.ambiguous) != expected:
            raise ValueError("invalid_recommendation_selection")
        if self.waiting_risk != waiting_risk(self.context) or not set(self.diagnostics) <= {"invalid_candidate", "candidate_batch_limit"}:
            raise ValueError("invalid_recommendation_metadata")

    @property
    def decision_id(self):
        return _hash(dict(schema_version=SCHEMA_VERSION, context=self.context.context_id,
            candidates=[c.candidate_id for c in self.candidates], state=self.state,
            recommended=self.recommended_candidate, alternatives=self.alternatives,
            reasons=self.reason_codes, diagnostics=self.diagnostics, waiting_risk=self.waiting_risk))

    @property
    def regret(self):
        return DecisionRegret(self.decision_id, self.recommended_candidate, self.alternatives, self.context.as_of)

    def freshness_at(self, as_of):
        now = _time(as_of)
        if now < self.context.as_of:
            raise ValueError("evaluation_before_decision")
        if any(c.window.stale_at(now) for c in self.candidates):
            return "STALE"
        if any(now >= e.valid_until for e in self.context.assessment.evidence):
            return "STALE"
        if any(forecast_freshness(f, as_of=now).state != "CURRENT" for f in self.context.forecasts):
            return "STALE"
        return "CURRENT"

    def as_dict(self):
        return dict(normalized(self), context=self.context.as_dict(),
                    candidates=[c.as_dict() for c in self.candidates], decision_id=self.decision_id,
                    decision_hash=self.decision_id, regret=normalized(self.regret), schema_version=SCHEMA_VERSION)


def _selection(context, candidates):
    if not candidates:
        return (DecisionState.INSUFFICIENT_EVIDENCE, None, (), ("no_supported_candidate",), False)
    frontier = tuple(c for c in candidates if not any(dominates(other, c) for other in candidates))
    ids = tuple(sorted(c.candidate_id for c in frontier))
    if len(frontier) != 1:
        return DecisionState.REVIEW_REQUIRED, None, ids, ("ambiguous_candidates",), True
    c = frontier[0]
    reasons = set(c.reason_codes)
    if c.window.stale_at(context.as_of):
        return DecisionState.REVIEW_REQUIRED, None, ids, tuple(sorted(reasons | {"recommendation_stale"})), False
    state = {CandidateType.OBSERVE: DecisionState.OBSERVE, CandidateType.WAIT: DecisionState.WAIT,
             CandidateType.GATHER_EVIDENCE: DecisionState.GATHER_EVIDENCE,
             CandidateType.NO_ACTION: DecisionState.NO_ACTION, CandidateType.OTHER: DecisionState.UNKNOWN,
             CandidateType.REVIEW: DecisionState.REVIEW_REQUIRED,
             CandidateType.ESCALATE_FOR_REVIEW: DecisionState.REVIEW_REQUIRED,
             CandidateType.PREPARE: DecisionState.RECOMMEND}[c.action_class]
    return state, c.candidate_id, tuple(sorted(x.candidate_id for x in candidates if x != c)), tuple(sorted(reasons)), False


def recommend(context, candidates=None):
    if not isinstance(context, DecisionContext):
        raise ValueError("invalid_context")
    # Reconstruct to validate even a maliciously modified frozen input.
    context = replay_context(context.as_dict())
    if candidates is None:
        if any(a.conflict_state == "CONFLICT" for a in context.assessment.assertions):
            candidates = (make_candidate(context, CandidateType.ESCALATE_FOR_REVIEW,
                why="Conflicting observed impact evidence requires review.",
                reason_codes=("conflicting_impact_evidence",)),)
        elif _verified_worsening(context):
            candidates = (make_candidate(context, CandidateType.PREPARE,
                why="Verified impact and a current worsening branch support internal preparation for review.",
                reason_codes=("verified_impact_worsening_forecast",)),)
        elif next_best_evidence(context)[0].could_change_recommendation is not True:
            candidates = (make_candidate(context, CandidateType.OBSERVE,
                why="Verified impact without supported deterioration; observe for new evidence.",
                reason_codes=("no_supported_deterioration",)),)
        elif context.assessment.evidence or context.assessment.exposure_refs:
            candidates = (make_candidate(context, CandidateType.GATHER_EVIDENCE,
                why="Resolve physical impact uncertainty before further recommendations.",
                reason_codes=("physical_verification_missing",)),)
        else:
            candidates = ()
    rows = list(islice(iter(candidates), MAX_CANDIDATES + 1))
    retained, diagnostics = {}, set()
    if len(rows) > MAX_CANDIDATES:
        rows = []
        diagnostics.add("candidate_batch_limit")
    for row in rows:
        try:
            c = replay_candidate(row.as_dict() if isinstance(row, DecisionCandidate) else row)
            validate_candidate(c, context)
            retained[c.candidate_id] = c
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            diagnostics.add("invalid_candidate")
    ordered = tuple(retained[k] for k in sorted(retained))
    state, chosen, alternatives, reasons, ambiguous = _selection(context, ordered)
    return DecisionRecommendation(context, ordered, state, chosen, alternatives, reasons,
                                  tuple(sorted(diagnostics)), waiting_risk(context), ambiguous)


def replay_context(row):
    data = dict(row)
    derived = {k: data.pop(k) for k in ("context_id", "evidence_hashes", "impact_assessment_hash",
                                       "future_assessment_hash", "forecast_origins")}
    upstream = dict(data["assessment"], generated_at=data["as_of"])
    upstream["snapshot_hash"] = _hash(upstream)
    data["assessment"] = replay_impact_snapshot(upstream)
    data["forecasts"] = tuple(replay_forecast(f) for f in data["forecasts"])
    result = DecisionContext(**data)
    if any(result.as_dict()[k] != v for k, v in derived.items()):
        raise ValueError("tampered_context")
    return result


def build_decision_snapshot(decision, *, generated_at):
    generated_at = _time(generated_at)
    if generated_at < decision.context.as_of:
        raise ValueError("generation_before_decision")
    result = dict(normalized(ObserveOnly()), schema_version=SCHEMA_VERSION,
                  generated_at=normalized(generated_at), decision=decision.as_dict(),
                  freshness=decision.freshness_at(generated_at))
    result["snapshot_hash"] = _hash(result)
    _bounded_json(result)
    return result


def _bounded_json(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(encoded.encode()) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot_size_limit")
    return encoded


def replay_decision_snapshot(payload):
    _bounded_json(payload)
    data = dict(payload)
    expected = data.pop("snapshot_hash")
    if _hash(data) != expected:
        raise ValueError("tampered_snapshot")
    row = data["decision"]
    context = replay_context(row["context"])
    result = recommend(context, row["candidates"])
    # Rejections are bounded diagnostics, never recommendation evidence.
    from dataclasses import replace
    result = replace(result, diagnostics=tuple(row["diagnostics"]))
    rebuilt = build_decision_snapshot(result, generated_at=data["generated_at"])
    if rebuilt != payload:
        raise ValueError("snapshot_replay_mismatch")
    return result


def write_decision_snapshot(path, snapshot):
    replay_decision_snapshot(snapshot)
    encoded = _bounded_json(snapshot)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".decision-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def build_storm_decision_surface(future_snapshots, canonical_event_keys, *, as_of):
    """Read-only adapter. Scope assessments per event; never rebind forecast lineage."""
    from empire_os.real_world_future_state_intelligence import replay_future_state_snapshot
    from empire_os.real_world_impact_intelligence import assess_impact
    as_of = _time(as_of)
    keys = tuple(sorted(set(canonical_event_keys)))
    if len(keys) > MAX_CANDIDATES:
        return dict(normalized(ObserveOnly()), schema_version=SCHEMA_VERSION, decisions=[],
                    diagnostics=["event_batch_limit"])
    sources = {}
    diagnostics = set()
    rows = list(islice(iter(future_snapshots), MAX_CANDIDATES + 1))
    if len(rows) > MAX_CANDIDATES:
        rows = []
        diagnostics.add("future_batch_limit")
    for row in rows:
        try:
            replay_future_state_snapshot(row)
            if _time(row["generated_at"]) > as_of:
                raise ValueError("future_assessment_leakage")
            tenant = row["assessment"]["tenant_id"]
            if tenant in sources:
                # Multiple versions must be explicitly resolved upstream.
                sources[tenant] = None
                diagnostics.add("ambiguous_future_assessment")
            else:
                sources[tenant] = row
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            diagnostics.add("invalid_future_assessment")
    decisions = []
    for tenant, event in keys:
        try:
            source = sources.get(tenant)
            if source is None:
                continue
            upstream = dict(source["assessment"], generated_at=source["generated_at"])
            upstream["snapshot_hash"] = _hash(upstream)
            original = replay_impact_snapshot(upstream)
            scoped = original if all(e.event_id == event for e in original.evidence) else assess_impact(
                tuple(e for e in original.evidence if e.event_id == event), tenant_id=tenant,
                now=as_of, policy=original.policy)
            forecasts = []
            freshness = {item["forecast_id"]: item["state"] for item in source["freshness"]}
            for row in source["forecasts"]:
                if row["event_id"] != event:
                    continue
                f = replay_forecast(row)
                if freshness[f.forecast_id] != "CURRENT":
                    diagnostics.add("forecast_not_current")
                    continue
                if f.input_assessment_hashes != (scoped.assessment_id,):
                    diagnostics.add("forecast_requires_scoped_assessment")
                    continue
                forecasts.append(f)
            context = DecisionContext(tenant, event, None, scoped, tuple(forecasts), as_of,
                                      "Assess storm evidence and internal review needs")
            # A canonical warning with no physical evidence supports observation only.
            candidates = None if scoped.evidence else (make_candidate(context, CandidateType.OBSERVE,
                why="Canonical storm event; physical impact remains unknown.",
                reason_codes=("storm_exposure_is_not_impact",)),)
            decisions.append(build_decision_snapshot(recommend(context, candidates), generated_at=as_of))
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            diagnostics.add("invalid_decision_context")
    return dict(normalized(ObserveOnly()), schema_version=SCHEMA_VERSION, decisions=decisions,
                diagnostics=sorted(diagnostics)[:MAX_DIAGNOSTICS])
