"""Bounded, replayable OBSERVE-only impact intelligence; no provider or action authority."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from itertools import islice
import json
import os
from pathlib import Path
import tempfile

from empire_os.real_world_event_intelligence import canonical_evidence_hash, source_timestamp
from empire_os.real_world_exposure_graph import ObserveOnly, normalized, text, confidence

SCHEMA_VERSION = "empire.real_world_impact.v1"
MAX_EVIDENCE = 100
MAX_DIAGNOSTICS = 32
CLOCK_SKEW = timedelta(minutes=5)


class ImpactTruth(str, Enum):
    UNKNOWN = "UNKNOWN"
    INFERRED = "INFERRED"
    SOURCE_REPORTED = "SOURCE_REPORTED"
    CORROBORATED = "CORROBORATED"
    VERIFIED = "VERIFIED"


class TruthDomain(str, Enum):
    EXPOSURE = "exposure"
    PHYSICAL_EFFECT = "physical_effect"
    IMPACT = "impact"
    DAMAGE = "damage"
    ECONOMIC_CONSEQUENCE = "economic_consequence"


class EvidenceClass(str, Enum):
    SENSOR = "sensor_observation"
    SATELLITE = "satellite_observation"
    RADAR = "radar_observation"
    OFFICIAL = "official_report"
    INFRASTRUCTURE = "infrastructure_status"
    FIELD = "field_report"
    FIRST_PARTY = "first_party_observation"
    MODEL = "model_inference"
    OTHER = "other"


class EffectCategory(str, Enum):
    STRUCTURAL = "structural"
    FLOODING = "flooding"
    WIND = "wind"
    HAIL = "hail"
    POWER = "power"
    TRANSPORT = "transport"
    ACCESS = "access"
    UTILITY = "utility"
    OPERATIONAL = "operational"
    ENVIRONMENTAL = "environmental"
    OTHER = "other"


def _hash(value):
    return canonical_evidence_hash(normalized(value))


def _assessment_hash(value):
    data = dict(value)
    data["evidence"] = [{k: v for k, v in row.items() if k != "processed_at"}
                        for row in data["evidence"]]
    return _hash(data)


def _sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid_hash")
    return value


@dataclass(frozen=True)
class ImpactEvidence(ObserveOnly):
    tenant_id: str
    event_id: str
    subject_id: str
    source: str
    source_record_id: str
    evidence_class: EvidenceClass
    phenomenon: str
    effect_category: EffectCategory
    domain: TruthDomain
    finding: str  # present / absent / unknown, never a numeric proxy for truth
    observed_at: datetime
    processed_at: datetime
    valid_from: datetime
    valid_until: datetime
    source_truth: str
    physical_truth: ImpactTruth
    confidence: float | None
    raw_evidence_hash: str
    provenance: tuple[str, ...]
    parent_evidence_ids: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        for name in ("tenant_id", "event_id", "subject_id", "source", "source_record_id", "phenomenon"):
            object.__setattr__(self, name, text(getattr(self, name)))
        object.__setattr__(self, "source", self.source.casefold())
        for name, cls in (("evidence_class", EvidenceClass), ("effect_category", EffectCategory),
                          ("domain", TruthDomain), ("physical_truth", ImpactTruth)):
            object.__setattr__(self, name, cls(getattr(self, name)))
        for name in ("observed_at", "processed_at", "valid_from", "valid_until"):
            value = source_timestamp(getattr(self, name))
            if value is None:
                raise ValueError("timestamp_required")
            object.__setattr__(self, name, value)
        if self.valid_until < self.valid_from:
            raise ValueError("invalid_window")
        if self.observed_at > self.processed_at + CLOCK_SKEW:
            raise ValueError("future_observation")
        if self.finding not in ("present", "absent", "unknown"):
            raise ValueError("invalid_finding")
        if self.source_truth not in ("OBSERVED_SOURCE_RECORD", "MODEL_INFERENCE", "SOURCE_FORECAST"):
            raise ValueError("invalid_source_truth")
        confidence(self.confidence)
        if self.confidence is not None:
            object.__setattr__(self, "confidence", float(self.confidence))
        _sha(self.raw_evidence_hash)
        for name in ("provenance", "parent_evidence_ids"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or len(values) > 16:
                raise ValueError("invalid_lineage")
            object.__setattr__(self, name, tuple(sorted(set(text(v) for v in values))))
        if not self.provenance or self.schema_version != SCHEMA_VERSION:
            raise ValueError("invalid_metadata")
        for parent in self.parent_evidence_ids:
            _sha(parent)
        inferred = self.evidence_class == EvidenceClass.MODEL or self.source_truth != "OBSERVED_SOURCE_RECORD"
        allowed = {ImpactTruth.UNKNOWN, ImpactTruth.INFERRED} if inferred else {
            ImpactTruth.UNKNOWN, ImpactTruth.INFERRED, ImpactTruth.SOURCE_REPORTED}
        if self.domain == TruthDomain.EXPOSURE or self.source in ("nws", "nws_alert"):
            allowed = {ImpactTruth.UNKNOWN}
        if self.domain == TruthDomain.ECONOMIC_CONSEQUENCE:
            raise ValueError("economic_intelligence_deferred")
        if self.physical_truth not in allowed:
            raise ValueError("unsupported_truth_escalation")
        if self.finding == "unknown" and self.physical_truth != ImpactTruth.UNKNOWN:
            raise ValueError("unsupported_truth_escalation")

    @property
    def evidence_id(self):
        return _hash({"scope": self.scope, "source": self.source, "record": self.source_record_id})

    @property
    def scope(self):
        return (self.tenant_id, self.event_id, self.subject_id, self.phenomenon,
                self.effect_category.value, self.domain.value, self.valid_from, self.valid_until)

    @property
    def evidence_hash(self):
        data = normalized(self)
        data.pop("processed_at")  # Re-fetching cannot change canonical evidence.
        return _hash(data)

    def as_dict(self):
        return dict(normalized(self), evidence_id=self.evidence_id, evidence_hash=self.evidence_hash)


def replay_impact_evidence(row):
    data = dict(row)
    expected_id = data.pop("evidence_id")
    expected_hash = data.pop("evidence_hash")
    evidence = ImpactEvidence(**data)
    if evidence.evidence_id != expected_id or evidence.evidence_hash != expected_hash:
        raise ValueError("tampered_evidence")
    return evidence


@dataclass(frozen=True)
class QualifiedVerification:
    """Trusted integration input, never accepted from an evidence payload."""
    evidence_hash: str
    verifier_id: str
    verification_ref: str

    def __post_init__(self):
        _sha(self.evidence_hash)
        text(self.verifier_id)
        text(self.verification_ref)


@dataclass(frozen=True)
class ConvergencePolicy:
    independent_origins: tuple[tuple[str, str], ...] = ()
    verifications: tuple[QualifiedVerification, ...] = ()

    def __post_init__(self):
        if len(self.independent_origins) > MAX_EVIDENCE or len(self.verifications) > MAX_EVIDENCE:
            raise ValueError("policy_limit")
        pairs = tuple(sorted((text(s).casefold(), text(o)) for s, o in self.independent_origins))
        if len({s for s, _ in pairs}) != len(pairs):
            raise ValueError("ambiguous_origin")
        if any(not isinstance(v, QualifiedVerification) for v in self.verifications):
            raise ValueError("invalid_verification")
        object.__setattr__(self, "independent_origins", pairs)
        object.__setattr__(self, "verifications", tuple(sorted(set(self.verifications), key=lambda v: (v.evidence_hash, v.verifier_id, v.verification_ref))))


@dataclass(frozen=True)
class ImpactAssertion(ObserveOnly):
    tenant_id: str
    event_id: str
    subject_id: str
    phenomenon: str
    effect_category: str
    domain: str
    valid_from: datetime
    valid_until: datetime
    evidence_hashes: tuple[str, ...]
    source_count: int
    independent_source_count: int
    agreement_state: str
    conflict_state: str
    finding: str
    physical_truth: ImpactTruth
    impact_truth: ImpactTruth
    damage_truth: ImpactTruth
    economic_truth: ImpactTruth
    confidence: float | None
    observed_at: tuple[datetime, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self):
        super().__post_init__()
        for name in ("tenant_id", "event_id", "subject_id", "phenomenon"):
            object.__setattr__(self, name, text(getattr(self, name)))
        EffectCategory(self.effect_category)
        TruthDomain(self.domain)
        for name in ("physical_truth", "impact_truth", "damage_truth", "economic_truth"):
            object.__setattr__(self, name, ImpactTruth(getattr(self, name)))
        if self.economic_truth != ImpactTruth.UNKNOWN:
            raise ValueError("economic_intelligence_deferred")
        for name in ("valid_from", "valid_until"):
            object.__setattr__(self, name, source_timestamp(getattr(self, name)))
        if self.valid_until < self.valid_from:
            raise ValueError("invalid_window")
        if (type(self.source_count) is not int or type(self.independent_source_count) is not int
                or not 0 <= self.independent_source_count <= self.source_count <= MAX_EVIDENCE):
            raise ValueError("invalid_source_counts")
        if (self.agreement_state not in ("AGREE", "CONFLICT", "INSUFFICIENT")
                or self.conflict_state not in ("CONFLICT", "NONE")
                or self.finding not in ("present", "absent", "unknown")):
            raise ValueError("invalid_convergence_state")
        confidence(self.confidence)
        for name, validator, limit in (("evidence_hashes", _sha, MAX_EVIDENCE),
                                       ("reason_codes", text, MAX_DIAGNOSTICS),
                                       ("observed_at", source_timestamp, MAX_EVIDENCE)):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or len(values) > limit:
                raise ValueError("assertion_limit")
            object.__setattr__(self, name, tuple(sorted(set(validator(v) for v in values))))

    @property
    def assertion_id(self):
        return _hash(self)


@dataclass(frozen=True)
class ImpactAssessment(ObserveOnly):
    tenant_id: str
    evidence: tuple[ImpactEvidence, ...]
    assertions: tuple[ImpactAssertion, ...]
    rejections: tuple[str, ...]
    reason_codes: tuple[str, ...]
    exposure_refs: tuple[str, ...]
    policy: ConvergencePolicy
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        super().__post_init__()
        text(self.tenant_id)
        if self.schema_version != SCHEMA_VERSION or not isinstance(self.policy, ConvergencePolicy):
            raise ValueError("invalid_assessment_metadata")
        for name, cls, limit in (("evidence", ImpactEvidence, MAX_EVIDENCE),
                                 ("assertions", ImpactAssertion, MAX_EVIDENCE),
                                 ("rejections", str, MAX_DIAGNOSTICS),
                                 ("reason_codes", str, MAX_DIAGNOSTICS),
                                 ("exposure_refs", str, MAX_EVIDENCE)):
            values = tuple(getattr(self, name))
            if len(values) > limit or any(not isinstance(v, cls) for v in values):
                raise ValueError("invalid_assessment_records")
            object.__setattr__(self, name, values)
        if any(e.tenant_id != self.tenant_id for e in (*self.evidence, *self.assertions)):
            raise ValueError("cross_tenant_mismatch")
        for code in (*self.rejections, *self.reason_codes):
            text(code)
        for ref in self.exposure_refs:
            _sha(ref)

    @property
    def impact_evidence_count(self):
        return sum(e.domain != TruthDomain.EXPOSURE and e.physical_truth != ImpactTruth.UNKNOWN for e in self.evidence)

    @property
    def assessment_id(self):
        return self.as_dict()["assessment_hash"]

    def as_dict(self):
        result = normalized(self)
        result["evidence"] = [e.as_dict() for e in self.evidence]
        result["impact_evidence_count"] = self.impact_evidence_count
        result["assessment_hash"] = _assessment_hash(result)
        return result


def assess_impact(evidence=(), *, tenant_id, now, policy=None, exposures=()):
    """Exact-window convergence; invalid items isolated, conflicts never majority-voted away."""
    tenant_id = text(tenant_id)
    now = source_timestamp(now)
    policy = policy or ConvergencePolicy()
    if not isinstance(policy, ConvergencePolicy):
        raise ValueError("invalid_policy")
    rejections = set()
    rows = list(islice(iter(evidence), MAX_EVIDENCE + 1))
    if len(rows) > MAX_EVIDENCE:
        rows = []
        rejections.add("evidence_batch_limit")
    found = {}
    for row in rows:
        try:
            item = row if isinstance(row, ImpactEvidence) else replay_impact_evidence(row)
            if item.tenant_id != tenant_id:
                raise ValueError("cross_tenant_mismatch")
            if item.observed_at > now + CLOCK_SKEW or item.processed_at > now + CLOCK_SKEW:
                raise ValueError("future_timestamp")
            old = found.get(item.evidence_hash)
            if old is None or item.processed_at < old.processed_at:
                found[item.evidence_hash] = item
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            rejections.add("invalid_evidence_record")
    # Parent identity is scoped to tenant/event/subject; cycles and dangling references fail closed.
    by_id = {}
    for item in found.values():
        by_id.setdefault(item.evidence_id, []).append(item)
    lineage_status = {}
    def lineage_ok(item, seen):
        if item.evidence_hash in lineage_status:
            return lineage_status[item.evidence_hash]
        if item.evidence_id in seen:
            return False
        for parent_id in item.parent_evidence_ids:
            parents = by_id.get(parent_id, ())
            if len(parents) != 1 or parents[0].scope[:3] != item.scope[:3]:
                lineage_status[item.evidence_hash] = False
                return False
            if not lineage_ok(parents[0], seen | {item.evidence_id}):
                lineage_status[item.evidence_hash] = False
                return False
        lineage_status[item.evidence_hash] = True
        return True
    retained = tuple(found[k] for k in sorted(found) if lineage_ok(found[k], set()))
    if len(retained) != len(found):
        rejections.add("invalid_evidence_lineage")
    exposure_refs = set()
    from empire_os.real_world_exposure_graph import ExposureRelationship
    for index, edge in enumerate(islice(iter(exposures), MAX_EVIDENCE + 1)):
        if index == MAX_EVIDENCE:
            exposure_refs.clear()
            rejections.add("exposure_batch_limit")
            break
        if isinstance(edge, ExposureRelationship) and edge.tenant_id == tenant_id:
            exposure_refs.add(edge.relationship_id)
        else:
            rejections.add("invalid_exposure_record")
    groups = {}
    for item in retained:
        groups.setdefault(item.scope, []).append(item)
    origins = dict(policy.independent_origins)
    qualified = {v.evidence_hash for v in policy.verifications}
    assertions = []
    for scope in sorted(groups):
        items = groups[scope]
        physical = [e for e in items if e.physical_truth != ImpactTruth.UNKNOWN]
        findings = {e.finding for e in physical}
        versions = {}
        for e in items:
            versions.setdefault(e.evidence_id, set()).add(e.evidence_hash)
        conflict = len(findings) > 1 or any(len(v) > 1 for v in versions.values())
        known_origins = {origins[e.source] for e in physical if e.source in origins}
        reasons = set()
        truth = ImpactTruth.UNKNOWN
        suitable = [e for e in physical if e.physical_truth == ImpactTruth.SOURCE_REPORTED
                    and e.evidence_class not in (EvidenceClass.MODEL, EvidenceClass.OTHER)]
        independent = {origins[e.source] for e in suitable if e.source in origins}
        if conflict:
            reasons.add("conflicting_evidence_requires_resolution")
        elif physical:
            truth = ImpactTruth.INFERRED
            if suitable:
                truth = ImpactTruth.SOURCE_REPORTED
            if len(independent) >= 2:
                truth = ImpactTruth.CORROBORATED
            if any(e.evidence_hash in qualified and e.evidence_class in (EvidenceClass.FIELD, EvidenceClass.FIRST_PARTY) for e in suitable):
                truth = ImpactTruth.VERIFIED
        if not physical:
            reasons.add("exposure_without_physical_evidence" if scope[5] == "exposure" else "missing_physical_observation")
        if physical and all(e.physical_truth == ImpactTruth.INFERRED for e in physical):
            reasons.add("only_inference_available")
        if len(independent) < 2:
            reasons.add("missing_independent_physical_observation")
        if scope[5] == "damage" and truth != ImpactTruth.VERIFIED:
            reasons.add("missing_qualified_damage_verification")
        if any(e.source not in origins for e in physical):
            reasons.add("source_independence_unknown")
        confs = [e.confidence for e in physical]
        conf = min(confs) if confs and None not in confs and not conflict else None
        domain = scope[5]
        assertions.append(ImpactAssertion(*scope, tuple(sorted(e.evidence_hash for e in items)),
            len({e.source for e in items}), len(known_origins),
            "CONFLICT" if conflict else "AGREE" if len(known_origins) >= 2 and len(findings) == 1 else "INSUFFICIENT",
            "CONFLICT" if conflict else "NONE", next(iter(findings)) if len(findings) == 1 and not conflict else "unknown",
            truth if domain in ("physical_effect", "damage") else ImpactTruth.UNKNOWN,
            truth if domain == "impact" else ImpactTruth.UNKNOWN,
            truth if domain == "damage" else ImpactTruth.UNKNOWN, ImpactTruth.UNKNOWN,
            conf, tuple(sorted({e.observed_at for e in items})), tuple(sorted(reasons))))
    reasons = set().union(*(set(a.reason_codes) for a in assertions))
    if not any(e.physical_truth != ImpactTruth.UNKNOWN for e in retained):
        reasons.add("exposure_without_physical_evidence" if exposure_refs else "missing_physical_observation")
    return ImpactAssessment(tenant_id, retained, tuple(assertions), tuple(sorted(rejections)[:MAX_DIAGNOSTICS]),
                            tuple(sorted(reasons)[:MAX_DIAGNOSTICS]), tuple(sorted(exposure_refs)), policy)


def write_impact_snapshot(path, assessment, *, generated_at):
    if not isinstance(assessment, ImpactAssessment) or len(assessment.evidence) > MAX_EVIDENCE:
        raise ValueError("invalid_snapshot")
    payload = assessment.as_dict()
    payload["generated_at"] = normalized(source_timestamp(generated_at))
    payload["snapshot_hash"] = _hash(payload)
    replay_impact_snapshot(payload)  # Refuse artifacts that cannot reproduce their assertions.
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    if len(encoded.encode()) > 2_000_000:
        raise ValueError("snapshot_size_limit")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".impact-")
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


def replay_impact_snapshot(payload):
    """Verify the full artifact and re-derive truth from its retained trusted policy."""
    data = dict(payload)
    expected = data.pop("snapshot_hash")
    if _hash(data) != expected:
        raise ValueError("tampered_snapshot")
    generated_at = data.pop("generated_at")
    assessment_hash = data.pop("assessment_hash")
    if _assessment_hash(data) != assessment_hash or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("tampered_assessment")
    policy = ConvergencePolicy(tuple(tuple(p) for p in data["policy"]["independent_origins"]),
                               tuple(QualifiedVerification(**v) for v in data["policy"]["verifications"]))
    result = assess_impact(data["evidence"], tenant_id=data["tenant_id"], now=generated_at, policy=policy)
    if normalized(result.assertions) != data["assertions"]:
        raise ValueError("assessment_replay_mismatch")
    # Exposure refs and bounded rejection diagnostics are retained metadata, not evidence.
    restored = replace(result, rejections=tuple(data["rejections"]),
                       reason_codes=tuple(data["reason_codes"]),
                       exposure_refs=tuple(data["exposure_refs"]))
    if restored.as_dict() != dict(data, assessment_hash=assessment_hash):
        raise ValueError("snapshot_replay_mismatch")
    return restored
