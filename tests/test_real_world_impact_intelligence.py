from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.real_world_impact_intelligence import (
    ImpactEvidence, ImpactTruth as T, TruthDomain as D, EvidenceClass as E,
    EffectCategory as C, ConvergencePolicy, QualifiedVerification, assess_impact,
    replay_impact_evidence, write_impact_snapshot, replay_impact_snapshot,
)
from empire_os.real_world_event_intelligence import AUTHORITY_FIELDS

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
POLICY = ConvergencePolicy((("sensor-a", "origin-a"), ("sensor-b", "origin-b")))


def evidence(**kwargs):
    values = dict(tenant_id="tenant", event_id="event", subject_id="property-1",
        source="sensor-a", source_record_id="record-1", evidence_class=E.SENSOR,
        phenomenon="roof_damage", effect_category=C.STRUCTURAL, domain=D.DAMAGE,
        finding="present", observed_at=NOW, processed_at=NOW, valid_from=NOW,
        valid_until=NOW + timedelta(hours=1), source_truth="OBSERVED_SOURCE_RECORD",
        physical_truth=T.SOURCE_REPORTED, confidence=0.8, raw_evidence_hash="a" * 64,
        provenance=("source://record-1",))
    values.update(kwargs)
    return ImpactEvidence(**values)


def assess(rows=(), **kwargs):
    return assess_impact(rows, tenant_id="tenant", now=NOW, policy=kwargs.pop("policy", POLICY), **kwargs)


def test_zero_and_exposure():
    result = assess()
    assert result.impact_evidence_count == 0
    assert not result.assertions
    item = evidence(domain=D.EXPOSURE, physical_truth=T.UNKNOWN)
    a = assess([item]).assertions[0]
    assert a.physical_truth == a.impact_truth == a.damage_truth == T.UNKNOWN
    assert "exposure_without_physical_evidence" in a.reason_codes


@pytest.mark.parametrize("source", ["nws", "nws_alert"])
def test_nws_cannot_verify_damage(source):
    with pytest.raises(ValueError):
        evidence(source=source, physical_truth=T.VERIFIED)
    with pytest.raises(ValueError):
        evidence(source=source)


@pytest.mark.parametrize("truth", [T.SOURCE_REPORTED, T.CORROBORATED, T.VERIFIED])
def test_model_cannot_escalate(truth):
    with pytest.raises(ValueError):
        evidence(evidence_class=E.MODEL, physical_truth=truth)


def test_inference_diagnostics_and_qualified_model_rejected():
    item = evidence(evidence_class=E.MODEL, physical_truth=T.INFERRED)
    policy = ConvergencePolicy(verifications=(QualifiedVerification(item.evidence_hash, "v", "ref"),))
    result = assess([item], policy=policy).assertions[0]
    assert result.damage_truth == T.INFERRED
    assert "only_inference_available" in result.reason_codes
    assert "missing_qualified_damage_verification" in result.reason_codes


def test_duplicate_retrieval_and_independence():
    item = evidence()
    repeat = replace(item, processed_at=NOW + timedelta(minutes=1))
    assert item.evidence_hash == repeat.evidence_hash
    one, many = assess([item]), assess([item, repeat, item])
    assert one == many
    assert many.assertions[0].independent_source_count == 1
    other_record = evidence(source_record_id="record-2")
    assert assess([item, other_record]).assertions[0].independent_source_count == 1


def test_independent_agreement_and_conservative_confidence():
    a = assess([evidence(), evidence(source="sensor-b", confidence=0.7)]).assertions[0]
    assert a.source_count == a.independent_source_count == 2
    assert a.agreement_state == "AGREE"
    assert a.damage_truth == T.CORROBORATED
    assert a.confidence == 0.7
    assert a.economic_truth == T.UNKNOWN


def test_syndication_and_unknown_independence():
    rows = [evidence(), evidence(source="sensor-b")]
    assert assess(rows, policy=ConvergencePolicy()).assertions[0].independent_source_count == 0
    policy = ConvergencePolicy((("sensor-a", "same"), ("sensor-b", "same")))
    assert assess(rows, policy=policy).assertions[0].damage_truth == T.SOURCE_REPORTED


@pytest.mark.parametrize("same_source", [True, False])
def test_conflict_third_duplicate_cannot_erase(same_source):
    first = evidence()
    second = evidence(source="sensor-a" if same_source else "sensor-b", finding="absent")
    a = assess([first, second]).assertions[0]
    assert a == assess([first, second, first]).assertions[0]
    assert a.damage_truth == T.UNKNOWN
    assert a.conflict_state == "CONFLICT"
    assert a.confidence is None
    assert "conflicting_evidence_requires_resolution" in a.reason_codes


def test_cross_tenant_isolation():
    result = assess([evidence(), evidence(tenant_id="other")])
    assert len(result.evidence) == 1
    assert result.rejections == ("invalid_evidence_record",)


@pytest.mark.parametrize("changes", [dict(subject_id="property-2"), dict(event_id="event-2"),
    dict(phenomenon="wall_damage"), dict(effect_category=C.FLOODING), dict(domain=D.IMPACT),
    dict(valid_until=NOW + timedelta(hours=2))])
def test_compatibility(changes):
    result = assess([evidence(), evidence(source="sensor-b", **changes)])
    assert len(result.assertions) == 2
    assert all(a.independent_source_count == 1 for a in result.assertions)


def test_stable_order_identity_hash_replay():
    a, b = evidence(), evidence(source="sensor-b")
    assert replay_impact_evidence(a.as_dict()) == a
    assert a.evidence_id == evidence().evidence_id
    assert a.evidence_hash == evidence().evidence_hash
    assert assess([a, b]).as_dict() == assess([b, a]).as_dict()
    row = a.as_dict()
    row["finding"] = "absent"
    with pytest.raises(ValueError, match="tampered"):
        replay_impact_evidence(row)


@pytest.mark.parametrize("field", ["observed_at", "processed_at", "valid_from", "valid_until"])
def test_naive_time_rejected(field):
    with pytest.raises(ValueError):
        evidence(**{field: NOW.replace(tzinfo=None)})


def test_future_time_safety():
    with pytest.raises(ValueError):
        evidence(observed_at=NOW + timedelta(minutes=6))
    future = evidence(observed_at=NOW + timedelta(days=1), processed_at=NOW + timedelta(days=1))
    assert not assess([future]).evidence
    assert assess([evidence(observed_at=NOW + timedelta(minutes=5))]).evidence


def test_invalid_window():
    with pytest.raises(ValueError):
        evidence(valid_until=NOW - timedelta(seconds=1))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.1, 1.1, True, "0.5"])
def test_invalid_confidence(value):
    with pytest.raises(ValueError):
        evidence(confidence=value)


def test_malformed_isolation_and_bounded_diagnostics():
    result = assess([None, {}, "bad", evidence()])
    assert len(result.evidence) == 1
    assert len(result.rejections) <= 32
    assert not assess([{}] * 101).evidence
    assert assess([{}] * 101).rejections == ("evidence_batch_limit",)


def test_qualified_verification_is_bound_to_exact_evidence():
    item = evidence(evidence_class=E.FIELD)
    policy = ConvergencePolicy(verifications=(QualifiedVerification(item.evidence_hash, "inspector", "inspection://1"),))
    assert assess([item], policy=policy).assertions[0].damage_truth == T.VERIFIED
    assert assess([replace(item, finding="absent")], policy=policy).assertions[0].damage_truth == T.SOURCE_REPORTED
    assert assess([item, evidence(source="sensor-b", finding="absent")], policy=policy).assertions[0].damage_truth == T.UNKNOWN


@pytest.mark.parametrize("truth", [T.CORROBORATED, T.VERIFIED])
def test_illegal_input_truth(truth):
    with pytest.raises(ValueError):
        evidence(physical_truth=truth)


def test_lineage_requires_same_subject_and_actual_evidence():
    parent = evidence(domain=D.PHYSICAL_EFFECT, phenomenon="flooding")
    child = evidence(phenomenon="road_closure", parent_evidence_ids=(parent.evidence_id,))
    assert len(assess([parent, child]).evidence) == 2
    assert not assess([child]).evidence
    assert len(assess([parent, replace(child, subject_id="other")]).evidence) == 1


def test_immutable_and_authority_none():
    item = evidence()
    with pytest.raises(FrozenInstanceError):
        item.confidence = 1
    for obj in (item, assess([item]), assess([item]).assertions[0]):
        assert all(getattr(obj, name) == "none" for name in AUTHORITY_FIELDS)
    for name in AUTHORITY_FIELDS:
        with pytest.raises(ValueError):
            replace(item, **{name: "live"})


def test_snapshot_atomic_replay_and_tamper(tmp_path):
    result = assess([evidence(), evidence(source="sensor-b")])
    path = write_impact_snapshot(tmp_path / "latest.json", result, generated_at=NOW)
    payload = json.loads(path.read_text())
    assert replay_impact_snapshot(payload) == result
    assert len(list(tmp_path.iterdir())) == 1
    payload["evidence"][0]["confidence"] = 1
    with pytest.raises(ValueError):
        replay_impact_snapshot(payload)


def test_storm_empty_integration():
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    result = build_storm_intelligence_runtime(now=NOW)
    assert result["impact_intelligence"]["impact_evidence_count"] == 0


def exposed_edge():
    from empire_os.real_world_exposure_graph import ExposureRelationship, SpatialPrecision
    return ExposureRelationship("tenant", "event", "footprint", "property-1", "subject-observation",
        "EXPOSED", (SpatialPrecision.POINT, SpatialPrecision.SOURCE_GEOMETRY), True,
        None, 0.9, ("a" * 64, "b" * 64), NOW)


def test_actual_exposure_is_not_impact_and_snapshot_preserves_diagnostics(tmp_path):
    result = assess([{}], exposures=[exposed_edge()])
    assert result.impact_evidence_count == 0
    assert not result.assertions
    assert result.exposure_refs
    assert "exposure_without_physical_evidence" in result.reason_codes
    payload = json.loads(write_impact_snapshot(tmp_path / "snapshot.json", result, generated_at=NOW).read_text())
    assert replay_impact_snapshot(payload) == result


def test_cross_tenant_exposure_rejected():
    result = assess(exposures=[replace(exposed_edge(), tenant_id="other")])
    assert not result.exposure_refs
    assert "invalid_exposure_record" in result.rejections


def test_lineage_cycle_rejected():
    first = evidence(phenomenon="flooding")
    second = evidence(phenomenon="closure", parent_evidence_ids=(first.evidence_id,))
    first = replace(first, parent_evidence_ids=(second.evidence_id,))
    assert not assess([first, second]).evidence


def test_missing_identity_forecast_and_deferred_economics():
    with pytest.raises(ValueError):
        evidence(subject_id="")
    with pytest.raises(ValueError):
        evidence(source_truth="SOURCE_FORECAST")
    with pytest.raises(ValueError):
        evidence(domain=D.ECONOMIC_CONSEQUENCE)


def test_verified_assertion_authority_none():
    item = evidence(evidence_class=E.FIRST_PARTY)
    policy = ConvergencePolicy(verifications=(QualifiedVerification(item.evidence_hash, "v", "ref"),))
    result = assess([item], policy=policy)
    assert result.assertions[0].damage_truth == T.VERIFIED
    assert all(getattr(result.assertions[0], field) == "none" for field in AUTHORITY_FIELDS)


def storm_event_row():
    return dict(tenant_id="tenant", event_id="event", event_type="hail", severity="severe",
        starts_at=NOW.isoformat(), ends_at=(NOW + timedelta(hours=1)).isoformat(),
        truth_class="OBSERVED", evidence=[dict(tenant_id="tenant", ref="nws:event", source="nws",
            observed_at=NOW.isoformat(), valid_until=(NOW + timedelta(hours=1)).isoformat())])


def test_storm_event_alone_and_explicit_impact_input():
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    row = storm_event_row()
    baseline = build_storm_intelligence_runtime(events=[row], now=NOW)
    assert baseline["impact_intelligence"]["impact_evidence_count"] == 0
    observed = build_storm_intelligence_runtime(events=[row], now=NOW,
        impact_evidence=[evidence().as_dict()], impact_policy=POLICY)
    assert observed["impact_intelligence"]["impact_evidence_count"] == 1
    assert observed["candidates"] == baseline["candidates"]
    rejected = build_storm_intelligence_runtime(events=[row], now=NOW,
        impact_evidence=[evidence(event_id="other").as_dict()])
    assert rejected["impact_intelligence"]["impact_evidence_count"] == 0
    assert rejected["impact_intelligence"]["rejections"] == ["impact_missing_canonical_event"]


def test_snapshot_clock_must_support_replay(tmp_path):
    with pytest.raises(ValueError):
        write_impact_snapshot(tmp_path / "snapshot.json", assess([evidence()]),
                              generated_at=NOW - timedelta(days=1))
    assert not (tmp_path / "snapshot.json").exists()


def test_retrieval_time_not_canonical_assessment_identity():
    first = evidence()
    repeated = replace(first, processed_at=NOW + timedelta(minutes=2))
    assert assess([first]).assessment_id == assess([repeated]).assessment_id
    assert assess([first]).assertions == assess([repeated]).assertions
