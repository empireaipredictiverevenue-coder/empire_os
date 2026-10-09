"""Generic immutable forecasts. No model execution, truth promotion or business authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from itertools import islice
import json
import math
import os
from pathlib import Path
import tempfile

from empire_os.real_world_event_intelligence import source_timestamp
from empire_os.real_world_exposure_graph import ObserveOnly, normalized, text, confidence
from empire_os.real_world_impact_intelligence import (
    ImpactAssessment, ImpactEvidence, EvidenceClass, ImpactTruth, assess_impact,
    replay_impact_snapshot, replay_impact_evidence, _hash, _sha,
)

SCHEMA_VERSION = "empire.real_world_future_state.v1"
MAX_FORECASTS = 100
MAX_DIAGNOSTICS = 32
MAX_HORIZON_SECONDS = 366 * 86400


class StandardHorizon(IntEnum):
    HOUR_1 = 3600
    HOURS_6 = 21600
    HOURS_24 = 86400
    HOURS_72 = 259200
    DAYS_7 = 604800


@dataclass(frozen=True)
class Horizon:
    seconds: int

    def __post_init__(self):
        if isinstance(self.seconds, bool) or not isinstance(self.seconds, int) or not 0 < self.seconds <= MAX_HORIZON_SECONDS:
            raise ValueError("invalid_horizon")
        object.__setattr__(self, "seconds", int(self.seconds))


CANONICAL_HORIZONS = tuple(Horizon(h) for h in StandardHorizon)


class Scenario(str, Enum):
    BASELINE = "BASELINE"
    IMPROVING = "IMPROVING"
    WORSENING = "WORSENING"
    PERSISTING = "PERSISTING"
    RESOLVED = "RESOLVED"
    ESCALATING = "ESCALATING"
    OTHER = "OTHER"


def _time(value):
    result = source_timestamp(value)
    if result is None:
        raise ValueError("timestamp_required")
    return result


def _strings(values, *, hashes=False, required=False, limit=100):
    if not isinstance(values, (list, tuple)) or len(values) > limit:
        raise ValueError("invalid_sequence")
    result = tuple(sorted(set((_sha if hashes else text)(v) for v in values)))
    if required and not result:
        raise ValueError("missing_inputs")
    return result


@dataclass(frozen=True)
class Uncertainty:
    """Optional probability interval; unknown is not zero uncertainty."""
    lower: float | None = None
    upper: float | None = None
    description: str = "unknown"

    def __post_init__(self):
        confidence(self.lower)
        confidence(self.upper)
        if (self.lower is None) != (self.upper is None) or (self.lower is not None and self.lower > self.upper):
            raise ValueError("invalid_uncertainty")
        for key in ("lower", "upper"):
            if getattr(self, key) is not None:
                object.__setattr__(self, key, float(getattr(self, key)))
        object.__setattr__(self, "description", text(self.description))


@dataclass(frozen=True)
class ScenarioBranch:
    scenario: Scenario
    predicted_state: str
    probability: float | None
    uncertainty: Uncertainty
    supporting_inputs: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "scenario", Scenario(self.scenario))
        object.__setattr__(self, "predicted_state", text(self.predicted_state))
        confidence(self.probability)
        if self.probability is not None:
            object.__setattr__(self, "probability", float(self.probability))
        if not isinstance(self.uncertainty, Uncertainty):
            raise ValueError("invalid_uncertainty")
        if self.probability is not None and self.uncertainty.lower is not None and not self.uncertainty.lower <= self.probability <= self.uncertainty.upper:
            raise ValueError("invalid_uncertainty")
        object.__setattr__(self, "supporting_inputs", _strings(self.supporting_inputs, hashes=True, required=True))
        object.__setattr__(self, "reason_codes", _strings(self.reason_codes, limit=MAX_DIAGNOSTICS))


@dataclass(frozen=True)
class FutureStateForecast(ObserveOnly):
    tenant_id: str
    event_id: str
    subject_id: str
    phenomenon: str
    effect: str
    domain: str
    forecast_origin_time: datetime
    horizon: Horizon
    forecast_method: str
    model_id: str | None
    method_configuration: tuple[tuple[str, str], ...]
    input_evidence_hashes: tuple[str, ...]
    input_assessment_hashes: tuple[str, ...]
    branches: tuple[ScenarioBranch, ...]
    valid_until: datetime
    generated_at: datetime
    provenance: tuple[str, ...]
    retrospective: bool = False
    calibration_status: str = "unknown"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        for name in ("tenant_id", "event_id", "subject_id", "phenomenon", "effect", "domain", "forecast_method"):
            object.__setattr__(self, name, text(getattr(self, name)))
        if self.domain not in ("exposure", "physical_effect", "impact", "damage"):
            raise ValueError("unsupported_truth_escalation")
        if self.model_id is not None:
            object.__setattr__(self, "model_id", text(self.model_id))
        if not isinstance(self.horizon, Horizon) or type(self.retrospective) is not bool:
            raise ValueError("invalid_metadata")
        for name in ("forecast_origin_time", "valid_until", "generated_at"):
            object.__setattr__(self, name, _time(getattr(self, name)))
        if not self.forecast_origin_time < self.valid_until <= self.target_time or self.generated_at < self.forecast_origin_time:
            raise ValueError("invalid_window")
        for name in ("input_evidence_hashes", "input_assessment_hashes"):
            object.__setattr__(self, name, _strings(getattr(self, name), hashes=True, required=True))
        object.__setattr__(self, "provenance", _strings(self.provenance, required=True, limit=16))
        if not isinstance(self.method_configuration, (tuple, list)) or len(self.method_configuration) > 32:
            raise ValueError("invalid_configuration")
        config = tuple(sorted((text(k), text(v)) for k, v in self.method_configuration))
        if len({k for k, _ in config}) != len(config):
            raise ValueError("invalid_configuration")
        object.__setattr__(self, "method_configuration", config)
        if not isinstance(self.branches, (tuple, list)) or not 1 <= len(self.branches) <= len(Scenario) or any(not isinstance(b, ScenarioBranch) for b in self.branches):
            raise ValueError("invalid_branches")
        branches = tuple(sorted(self.branches, key=lambda b: b.scenario.value))
        if len({b.scenario for b in branches}) != len(branches):
            raise ValueError("duplicate_scenario")
        # Branches are mutually exclusive alternatives; partial mass is allowed, excess is not.
        if sum(b.probability or 0 for b in branches) > 1 + 1e-12:
            raise ValueError("invalid_scenario_probabilities")
        if any(not set(b.supporting_inputs) <= set(self.input_evidence_hashes) for b in branches):
            raise ValueError("invalid_lineage")
        object.__setattr__(self, "branches", branches)
        if self.calibration_status != "unknown" or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported_calibration_or_schema")

    @property
    def scope(self):
        return (self.tenant_id, self.event_id, self.subject_id, self.phenomenon, self.effect, self.domain)

    @property
    def horizon_seconds(self):
        return self.horizon.seconds

    @property
    def target_time(self):
        return self.forecast_origin_time + timedelta(seconds=self.horizon.seconds)

    @property
    def forecast_hash(self):
        data = normalized(self)
        data.pop("generated_at")
        return _hash(data)

    @property
    def forecast_id(self):
        return self.forecast_hash

    def as_dict(self):
        return dict(normalized(self), forecast_id=self.forecast_id, forecast_hash=self.forecast_hash,
                    target_time=normalized(self.target_time), horizon_seconds=self.horizon_seconds)


def replay_forecast(row):
    data = dict(row)
    expected = {k: data.pop(k) for k in ("forecast_id", "forecast_hash", "target_time", "horizon_seconds")}
    data["horizon"] = Horizon(**data["horizon"])
    data["branches"] = tuple(ScenarioBranch(**dict(b, uncertainty=Uncertainty(**b["uncertainty"]))) for b in data["branches"])
    result = FutureStateForecast(**data)
    if any(result.as_dict()[k] != v for k, v in expected.items()):
        raise ValueError("tampered_forecast")
    return result


def _validate_assessment(assessment):
    if not isinstance(assessment, ImpactAssessment):
        raise ValueError("invalid_assessment")
    # Re-derive upstream assertions rather than trusting a constructed truth claim.
    now = max((e.processed_at for e in assessment.evidence), default=datetime.fromisoformat("1970-01-01T00:00:00+00:00"))
    rebuilt = assess_impact(assessment.evidence, tenant_id=assessment.tenant_id, now=now, policy=assessment.policy)
    if rebuilt.assertions != assessment.assertions or rebuilt.evidence != assessment.evidence:
        raise ValueError("tampered_assessment")


def validate_forecast(forecast, assessment):
    _validate_assessment(assessment)
    if forecast.tenant_id != assessment.tenant_id:
        raise ValueError("cross_tenant_mismatch")
    if forecast.input_assessment_hashes != (assessment.assessment_id,):
        raise ValueError("assessment_hash_mismatch")
    evidence = {e.evidence_hash: e for e in assessment.evidence}
    for ref in forecast.input_evidence_hashes:
        if ref not in evidence:
            raise ValueError("missing_evidence_lineage")
        item = evidence[ref]
        if item.scope[:6] != forecast.scope:
            raise ValueError("cross_scope_mismatch")
    # Full assessment is a declared input: no unselected future data may leak through it.
    if not forecast.retrospective and any(max(e.observed_at, e.processed_at, e.valid_from) > forecast.forecast_origin_time for e in assessment.evidence):
        raise ValueError("future_leakage")
    return forecast


@dataclass(frozen=True)
class Freshness(ObserveOnly):
    forecast_id: str
    state: str
    reason_codes: tuple[str, ...]


def forecast_freshness(forecast, *, as_of, newer_evidence=(), event_closed_at=None):
    as_of = _time(as_of)
    if as_of < forecast.forecast_origin_time:
        raise ValueError("evaluation_before_origin")
    state, reasons = "CURRENT", set()
    if as_of >= forecast.valid_until or as_of >= forecast.target_time:
        state = "STALE"
        reasons.add("forecast_stale")
    if event_closed_at is not None and _time(event_closed_at) <= as_of:
        state = "STALE"
        reasons.add("event_lifecycle_closed")
    rows = tuple(islice(iter(newer_evidence), MAX_FORECASTS + 1))
    if len(rows) > MAX_FORECASTS:
        raise ValueError("evidence_batch_limit")
    for e in rows:
        if not isinstance(e, ImpactEvidence) or e.scope[:6] != forecast.scope:
            raise ValueError("cross_scope_mismatch")
        if max(e.observed_at, e.processed_at) > as_of:
            raise ValueError("future_leakage")
        if e.observed_at > forecast.forecast_origin_time:
            state = "SUPERSEDED"
            reasons.add("newer_evidence_available")
    return Freshness(forecast.forecast_id, state, tuple(sorted(reasons)))


@dataclass(frozen=True)
class ForecastOriginPolicy:
    """Trusted configuration: method/model pairs map to independent model families."""
    origins: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self):
        if not isinstance(self.origins, (tuple, list)) or len(self.origins) > MAX_FORECASTS:
            raise ValueError("policy_limit")
        rows = tuple(sorted((text(a), text(b), text(c)) for a, b, c in self.origins))
        if len({(a, b) for a, b, _ in rows}) != len(rows):
            raise ValueError("ambiguous_origin")
        object.__setattr__(self, "origins", rows)


def convergence(forecasts, *, as_of, policy=ForecastOriginPolicy(), newer_evidence=()):
    rows = tuple(islice(iter(forecasts), MAX_FORECASTS + 1))
    if len(rows) > MAX_FORECASTS or not isinstance(policy, ForecastOriginPolicy):
        raise ValueError("invalid_convergence")
    rows = tuple({f.forecast_id: f for f in rows}.values())
    origins = {(m, model): origin for m, model, origin in policy.origins}
    groups = {}
    for f in rows:
        for b in f.branches:
            key = (*f.scope, normalized(f.forecast_origin_time), normalized(f.target_time), b.scenario.value)
            groups.setdefault(key, []).append((f, b))
    result = []
    for key, items in sorted(groups.items()):
        states = {b.predicted_state for _, b in items}
        intervals = [b.uncertainty for _, b in items if b.uncertainty.lower is not None]
        conflict = len(states) > 1 or (len(intervals) >= 2 and
            max(u.lower for u in intervals) > min(u.upper for u in intervals))
        current = [(f, b) for f, b in items if not f.retrospective and forecast_freshness(f, as_of=as_of, newer_evidence=tuple(e for e in newer_evidence if e.scope[:6] == f.scope)).state == "CURRENT"]
        independent = {origins[(f.forecast_method, f.model_id)] for f, _ in current if (f.forecast_method, f.model_id) in origins}
        justified = not conflict and len(independent) >= 2
        probabilities = [b.probability for _, b in current]
        result.append({"scope_origin_target_scenario": list(key), "forecast_count": len(items),
                       "independent_forecast_origin_count": len(independent),
                       "agreement_state": "CONFLICT" if conflict else "AGREE" if justified else "INSUFFICIENT",
                       "conflict_state": "CONFLICT" if conflict else "NONE",
                       "consensus_state": next(iter(states)) if justified else None,
                       "probability_range": [min(probabilities), max(probabilities)] if probabilities and None not in probabilities else None,
                       "forecast_ids": sorted(f.forecast_id for f, _ in items)})
    return result


def build_future_state_snapshot(forecasts=(), *, assessment, generated_at, policy=ForecastOriginPolicy(), newer_evidence=()):
    _validate_assessment(assessment)
    generated_at = _time(generated_at)
    rows = list(islice(iter(forecasts), MAX_FORECASTS + 1))
    rejected, retained = set(), {}
    if len(rows) > MAX_FORECASTS:
        rows = []
        rejected.add("forecast_batch_limit")
    for row in rows:
        try:
            f = row if isinstance(row, FutureStateForecast) else replay_forecast(row)
            validate_forecast(f, assessment)
            if f.generated_at > generated_at:
                raise ValueError("future_generation")
            old = retained.get(f.forecast_id)
            if old is None or f.generated_at < old.generated_at:
                retained[f.forecast_id] = f
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError):
            rejected.add("invalid_forecast_record")
    ordered = sorted(retained.values(), key=lambda f: (f.scope, f.forecast_origin_time, f.horizon_seconds, f.forecast_id))
    reasons = {"forecast_model_uncalibrated"} if ordered else {"insufficient_recent_observation"}
    if not assessment.assertions or any(a.impact_truth == ImpactTruth.UNKNOWN for a in assessment.assertions):
        reasons.add("impact_truth_unknown")
    if any(a.conflict_state == "CONFLICT" for a in assessment.assertions):
        reasons.add("conflicting_impact_evidence")
    if not any(a.physical_truth == ImpactTruth.VERIFIED or a.damage_truth == ImpactTruth.VERIFIED for a in assessment.assertions):
        reasons.add("physical_verification_missing")
    newer = tuple(islice(iter(newer_evidence), MAX_FORECASTS + 1))
    if len(newer) > MAX_FORECASTS:
        raise ValueError("evidence_batch_limit")
    newer = tuple(e if isinstance(e, ImpactEvidence) else replay_impact_evidence(e) for e in newer)
    scopes = {f.scope for f in ordered}
    if any(e.scope[:6] not in scopes or max(e.observed_at, e.processed_at) > generated_at for e in newer):
        raise ValueError("invalid_newer_evidence_scope_or_time")
    newer = tuple(sorted({e.evidence_hash: e for e in newer}.values(), key=lambda e: e.evidence_hash))
    freshness = [forecast_freshness(f, as_of=generated_at,
                 newer_evidence=tuple(e for e in newer if e.scope[:6] == f.scope)) for f in ordered]
    for f in ordered:
        if any(e.valid_until <= f.forecast_origin_time for e in assessment.evidence if e.evidence_hash in f.input_evidence_hashes):
            reasons.add("insufficient_recent_observation")
    for item in freshness:
        reasons.update(item.reason_codes)
    merged = convergence(ordered, as_of=generated_at, policy=policy, newer_evidence=newer)
    if any(g["conflict_state"] == "CONFLICT" for g in merged):
        reasons.add("forecast_conflict")
    trajectory = []
    groups = sorted({(f.scope, f.forecast_origin_time, f.retrospective) for f in ordered})
    for scope, origin, retrospective in groups:
        members = [f for f in ordered if f.scope == scope and f.forecast_origin_time == origin and f.retrospective == retrospective]
        points = [{"horizon_seconds": 0, "state": "KNOWN_AT_ORIGIN", "assessment_hash": assessment.assessment_id,
                   "input_evidence_hashes": sorted({e.evidence_hash for e in assessment.evidence
                       if e.scope[:6] == scope and max(e.observed_at, e.processed_at, e.valid_from) <= origin})}]
        for seconds in sorted({h.seconds for h in CANONICAL_HORIZONS} | {f.horizon_seconds for f in members}):
            ids = [f.forecast_id for f in members if f.horizon_seconds == seconds]
            points.append({"horizon_seconds": seconds, "target_time": normalized(origin + timedelta(seconds=seconds)),
                           "state": "FORECAST" if ids else "UNAVAILABLE", "forecast_ids": ids,
                           "reason_codes": [] if ids else ["horizon_not_supported"]})
            if not ids:
                reasons.add("horizon_not_supported")
        trajectory.append({"scope": list(scope), "forecast_origin_time": normalized(origin),
                           "retrospective": retrospective, "points": points})
    result = dict(normalized(ObserveOnly()), schema_version=SCHEMA_VERSION, generated_at=normalized(generated_at),
                  assessment=assessment.as_dict(), origin_policy=normalized(policy), forecast_count=len(ordered),
                  newer_evidence=[e.as_dict() for e in newer],
                  forecasts=[f.as_dict() for f in ordered], freshness=normalized(freshness), convergence=merged,
                  trajectories=trajectory, rejections=sorted(rejected)[:MAX_DIAGNOSTICS], reason_codes=sorted(reasons)[:MAX_DIAGNOSTICS])
    result["snapshot_hash"] = _hash(result)
    return result


def replay_future_state_snapshot(payload):
    data = dict(payload)
    expected = data.pop("snapshot_hash")
    if _hash(data) != expected or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("tampered_snapshot")
    upstream = dict(data["assessment"], generated_at=data["generated_at"])
    upstream["snapshot_hash"] = _hash(upstream)
    assessment = replay_impact_snapshot(upstream)
    result = build_future_state_snapshot(data["forecasts"], assessment=assessment, generated_at=data["generated_at"],
                                         policy=ForecastOriginPolicy(data["origin_policy"]["origins"]), newer_evidence=data["newer_evidence"])
    diagnostics = _strings(data["rejections"], limit=MAX_DIAGNOSTICS)
    if not set(diagnostics) <= {"invalid_forecast_record", "forecast_batch_limit"}:
        raise ValueError("invalid_diagnostics")
    result["rejections"] = list(diagnostics)
    result.pop("snapshot_hash")
    if result != data:
        raise ValueError("snapshot_replay_mismatch")
    return dict(data, snapshot_hash=expected)


def write_future_state_snapshot(path, snapshot):
    replay_future_state_snapshot(snapshot)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(encoded.encode()) > 2_000_000:
        raise ValueError("snapshot_size_limit")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".future-state-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


@dataclass(frozen=True)
class ForecastResolution(ObserveOnly):
    forecast: FutureStateForecast
    scenario: Scenario
    outcome: ImpactEvidence
    resolved_at: datetime
    calibration_bucket: str | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.forecast, FutureStateForecast) or not isinstance(self.outcome, ImpactEvidence):
            raise ValueError("invalid_resolution")
        object.__setattr__(self, "scenario", Scenario(self.scenario))
        object.__setattr__(self, "resolved_at", _time(self.resolved_at))
        if self.calibration_bucket is not None:
            object.__setattr__(self, "calibration_bucket", text(self.calibration_bucket))
        e, f = self.outcome, self.forecast
        if e.scope[:6] != f.scope or not e.valid_from <= f.target_time <= e.valid_until:
            raise ValueError("invalid_resolution_scope_or_target")
        if e.source_truth != "OBSERVED_SOURCE_RECORD" or e.evidence_class in (EvidenceClass.MODEL, EvidenceClass.OTHER) or e.physical_truth != ImpactTruth.SOURCE_REPORTED or e.finding == "unknown":
            raise ValueError("observed_outcome_required")
        if not f.target_time <= e.observed_at <= self.resolved_at or e.processed_at > self.resolved_at:
            raise ValueError("invalid_resolution_time")
        if self.branch.predicted_state not in ("present", "absent") or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported_resolution")

    @property
    def branch(self):
        for branch in self.forecast.branches:
            if branch.scenario == self.scenario:
                return branch
        raise ValueError("missing_scenario")

    def as_dict(self):
        p = self.branch.probability
        actual = int(self.outcome.finding == self.branch.predicted_state)
        result = dict(normalized(self), forecast_id=self.forecast.forecast_id,
                      outcome_reference=self.outcome.evidence_hash, target_time=normalized(self.forecast.target_time),
                      resolution_status="RESOLVED_SOURCE_REPORTED", predicted_probability=p, observed_binary_outcome=actual,
                      brier_score=None if p is None else (p - actual) ** 2,
                      log_loss=None if p is None or (p == 0 and actual) or (p == 1 and not actual) else -math.log(p if actual else 1 - p),
                      log_loss_status="unavailable" if p is None else "infinite" if (p == 0 and actual) or (p == 1 and not actual) else "finite",
                      forecast_error=int(not actual))
        result["resolution_hash"] = _hash(result)
        return result


def replay_forecast_resolution(row):
    """Resolution integrity and error metrics are independently re-derived."""
    data = dict(row)
    expected = data.pop("resolution_hash")
    if _hash(data) != expected:
        raise ValueError("tampered_resolution")
    fdata = data["forecast"]
    forecast = FutureStateForecast(**dict(fdata, horizon=Horizon(**fdata["horizon"]),
        branches=tuple(ScenarioBranch(**dict(b, uncertainty=Uncertainty(**b["uncertainty"]))) for b in fdata["branches"])))
    result = ForecastResolution(forecast, data["scenario"], ImpactEvidence(**data["outcome"]),
                                data["resolved_at"], data["calibration_bucket"], data["schema_version"])
    if result.as_dict() != row:
        raise ValueError("resolution_replay_mismatch")
    return result
