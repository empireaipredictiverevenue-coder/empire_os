from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
import copy
import json

import pytest

from empire_os.real_world_future_state_intelligence import (
    Horizon, CANONICAL_HORIZONS, Scenario, ScenarioBranch, Uncertainty,
    FutureStateForecast, ForecastOriginPolicy, ForecastResolution,
    validate_forecast, forecast_freshness, convergence, build_future_state_snapshot,
    replay_forecast, replay_future_state_snapshot, write_future_state_snapshot,
)
from empire_os.real_world_impact_intelligence import (
    ImpactEvidence, ImpactTruth, EvidenceClass, EffectCategory, TruthDomain,
    ConvergencePolicy, QualifiedVerification, assess_impact,
)
from empire_os.real_world_event_intelligence import AUTHORITY_FIELDS

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def evidence(**kwargs):
    data = dict(tenant_id="tenant", event_id="event", subject_id="subject",
                source="sensor", source_record_id="record", evidence_class=EvidenceClass.SENSOR,
                phenomenon="water", effect_category=EffectCategory.FLOODING, domain=TruthDomain.IMPACT,
                finding="present", observed_at=NOW, processed_at=NOW, valid_from=NOW,
                valid_until=NOW + timedelta(hours=24), source_truth="OBSERVED_SOURCE_RECORD",
                physical_truth=ImpactTruth.SOURCE_REPORTED, confidence=None,
                raw_evidence_hash="a" * 64, provenance=("source-record",))
    return ImpactEvidence(**dict(data, **kwargs))


def assessment(e=None, **kwargs):
    return assess_impact((e or evidence(),), tenant_id="tenant", now=NOW, **kwargs)


def forecast(a=None, **kwargs):
    a = a or assessment()
    e = a.evidence[0]
    branch = ScenarioBranch(Scenario.PERSISTING, "present", 0.8, Uncertainty(), (e.evidence_hash,))
    data = dict(tenant_id=e.tenant_id, event_id=e.event_id, subject_id=e.subject_id,
                phenomenon=e.phenomenon, effect=e.effect_category.value, domain=e.domain.value,
                forecast_origin_time=NOW, horizon=Horizon(3600), forecast_method="supplied-model",
                model_id="model-a", method_configuration=(("version", "1"),),
                input_evidence_hashes=(e.evidence_hash,), input_assessment_hashes=(a.assessment_id,),
                branches=(branch,), valid_until=NOW + timedelta(hours=1), generated_at=NOW,
                provenance=("model-output-reference",))
    return FutureStateForecast(**dict(data, **kwargs))


def snapshot(rows=(), a=None, **kwargs):
    return build_future_state_snapshot(rows, assessment=a or assessment(), generated_at=kwargs.pop("generated_at", NOW), **kwargs)


def test_truth_boundaries_and_immutable():
    a = assessment()
    before = a.as_dict()
    f = forecast(a)
    snapshot([f], a)
    assert a.as_dict() == before
    assert a.assertions[0].impact_truth == ImpactTruth.SOURCE_REPORTED
    assert a.assertions[0].damage_truth == ImpactTruth.UNKNOWN
    with pytest.raises(FrozenInstanceError):
        f.model_id = "other"
    with pytest.raises(TypeError):
        replace(f, impact_truth="VERIFIED")


def test_horizons_and_explicit_unknown():
    assert [h.seconds for h in CANONICAL_HORIZONS] == [3600, 21600, 86400, 259200, 604800]
    s = snapshot([forecast()])
    points = s["trajectories"][0]["points"]
    assert points[0]["state"] == "KNOWN_AT_ORIGIN"
    assert points[1]["state"] == "FORECAST"
    assert all(p["state"] == "UNAVAILABLE" and p["reason_codes"] == ["horizon_not_supported"] for p in points[2:])
    assert Horizon(120).seconds == 120


@pytest.mark.parametrize("seconds", [-1, 0, True, 1.5, 40000000])
def test_invalid_horizon(seconds):
    with pytest.raises(ValueError):
        Horizon(seconds)


def test_identity_retrieval_and_replay():
    a = assessment()
    f = forecast(a)
    later = replace(f, generated_at=NOW + timedelta(minutes=1))
    assert f.forecast_id == later.forecast_id
    again = assessment(replace(a.evidence[0], processed_at=NOW + timedelta(minutes=1)))
    assert a.assessment_id == again.assessment_id
    assert f.forecast_hash == forecast(again).forecast_hash
    assert replay_forecast(json.loads(json.dumps(f.as_dict()))) == f


def test_repetition_and_independent_origins():
    f = forecast()
    g = replace(f, provenance=("second-call",))
    policy = ForecastOriginPolicy((("supplied-model", "model-a", "family-a"), ("supplied-model", "model-b", "family-b")))
    result = convergence([f, g], as_of=NOW, policy=policy)[0]
    assert result["forecast_count"] == 2
    assert result["independent_forecast_origin_count"] == 1
    assert result["consensus_state"] is None
    g = replace(g, model_id="model-b")
    result = convergence([f, g], as_of=NOW, policy=policy)[0]
    assert result["independent_forecast_origin_count"] == 2
    assert result["agreement_state"] == "AGREE"
    assert result["consensus_state"] == "present"
    assert convergence([f, g], as_of=NOW)[0]["independent_forecast_origin_count"] == 0


def test_conflict_visible():
    f = forecast()
    g = replace(f, branches=(replace(f.branches[0], predicted_state="absent"),))
    s = snapshot([f, g, f])
    assert s["forecast_count"] == 2
    assert s["convergence"][0]["conflict_state"] == "CONFLICT"
    assert s["convergence"][0]["consensus_state"] is None
    assert "forecast_conflict" in s["reason_codes"]


@pytest.mark.parametrize("p", [-0.1, 1.1, float("nan"), float("inf"), -float("inf"), True, "0.5"])
def test_probability_invalid(p):
    with pytest.raises(ValueError):
        replace(forecast().branches[0], probability=p)


def test_branch_mass_and_uncertainty():
    f = forecast()
    with pytest.raises(ValueError):
        replace(f, branches=(f.branches[0], replace(f.branches[0], scenario=Scenario.IMPROVING)))
    for low, high in [(0.8, 0.2), (None, 0.5), (float("nan"), 0.5), (-1, 1)]:
        with pytest.raises(ValueError):
            Uncertainty(low, high)
    with pytest.raises(ValueError):
        replace(f.branches[0], scenario="garbage")
    with pytest.raises(ValueError):
        replace(f.branches[0], uncertainty=Uncertainty(0.1, 0.2))


@pytest.mark.parametrize("field", ["forecast_origin_time", "generated_at", "valid_until"])
def test_naive_timestamp(field):
    with pytest.raises(ValueError):
        replace(forecast(), **{field: NOW.replace(tzinfo=None)})


@pytest.mark.parametrize("field", ["observed_at", "processed_at", "valid_from"])
def test_future_leakage(field):
    e = evidence(**{field: NOW + timedelta(minutes=1)})
    a = assessment(e)
    f = forecast(a)
    with pytest.raises(ValueError, match="future_leakage"):
        validate_forecast(f, a)
    assert validate_forecast(replace(f, retrospective=True), a)
    assert convergence([replace(f, retrospective=True)], as_of=NOW)[0]["consensus_state"] is None


@pytest.mark.parametrize("field", ["tenant_id", "event_id", "subject_id", "phenomenon", "effect", "domain"])
def test_scope_isolation(field):
    value = "damage" if field == "domain" else "other"
    with pytest.raises(ValueError):
        validate_forecast(replace(forecast(), **{field: value}), assessment())


def test_missing_identity_and_hashes():
    for field in ("tenant_id", "event_id", "subject_id"):
        with pytest.raises(ValueError):
            replace(forecast(), **{field: ""})
    with pytest.raises(ValueError):
        validate_forecast(replace(forecast(), input_assessment_hashes=("b" * 64,)), assessment())


def test_freshness_preserves_forecast():
    f = forecast()
    original = f.as_dict()
    assert forecast_freshness(f, as_of=NOW).state == "CURRENT"
    assert forecast_freshness(f, as_of=f.target_time).state == "STALE"
    newer = evidence(observed_at=NOW + timedelta(minutes=1), processed_at=NOW + timedelta(minutes=1))
    assert forecast_freshness(f, as_of=NOW + timedelta(minutes=2), newer_evidence=[newer]).state == "SUPERSEDED"
    assert forecast_freshness(f, as_of=NOW, event_closed_at=NOW).state == "STALE"
    assert f.as_dict() == original
    stale = snapshot([f], generated_at=f.target_time)
    assert stale["forecast_count"] == 1
    assert "forecast_stale" in stale["reason_codes"]


def test_zero_and_uncalibrated():
    assert snapshot()["forecast_count"] == 0
    assert forecast().calibration_status == "unknown"
    with pytest.raises(ValueError):
        replace(forecast(), calibration_status="calibrated")
    assert "forecast_model_uncalibrated" in snapshot([forecast()])["reason_codes"]


def test_resolution_preserves_original_and_error():
    f = forecast()
    before = f.as_dict()
    outcome = evidence(observed_at=f.target_time, processed_at=f.target_time, finding="absent")
    r = ForecastResolution(f, Scenario.PERSISTING, outcome, f.target_time)
    d = r.as_dict()
    assert d["brier_score"] == pytest.approx(0.64)
    assert d["observed_binary_outcome"] == 0
    assert d["forecast_error"] == 1
    assert d["log_loss"] > 0
    assert f.as_dict() == before
    assert d["resolution_status"] == "RESOLVED_SOURCE_REPORTED"
    for e in [replace(outcome, subject_id="other"), replace(outcome, source_truth="MODEL_INFERENCE", physical_truth=ImpactTruth.INFERRED), evidence()]:
        with pytest.raises(ValueError):
            ForecastResolution(f, Scenario.PERSISTING, e, f.target_time)


def test_tamper_and_snapshot_atomic(tmp_path):
    f = forecast()
    row = f.as_dict()
    row["branches"][0]["probability"] = 0.5
    with pytest.raises(ValueError, match="tampered"):
        replay_forecast(row)
    s = snapshot([f])
    assert replay_future_state_snapshot(s) == s
    path = write_future_state_snapshot(tmp_path / "forecast.json", s)
    assert json.loads(path.read_text()) == s
    changed = copy.deepcopy(s)
    changed["forecasts"][0]["model_id"] = "tampered"
    with pytest.raises(ValueError):
        replay_future_state_snapshot(changed)
    assert list(tmp_path.iterdir()) == [path]


def test_stable_ordering_and_malformed_isolation():
    f = forecast()
    g = replace(f, horizon=Horizon(21600))
    assert snapshot([f, g]) == snapshot([g, f])
    s = snapshot([{}, None, {"private": "never diagnostic"}, f])
    assert s["forecast_count"] == 1
    assert s["rejections"] == ["invalid_forecast_record"]
    assert replay_future_state_snapshot(s) == s
    s = snapshot([{}] * 101)
    assert s["forecast_count"] == 0
    assert len(s["rejections"]) <= 32
    assert s["rejections"] == ["forecast_batch_limit"]


def test_next_best_evidence():
    s = snapshot()
    assert {"insufficient_recent_observation", "physical_verification_missing"} <= set(s["reason_codes"])
    empty = assess_impact((), tenant_id="tenant", now=NOW)
    assert "impact_truth_unknown" in snapshot(a=empty)["reason_codes"]


@pytest.mark.parametrize("authority", AUTHORITY_FIELDS)
def test_all_authority_none(authority):
    f = forecast()
    assert getattr(f, authority) == "none"
    assert snapshot([f])[authority] == "none"
    with pytest.raises(ValueError):
        replace(f, **{authority: "allowed"})


def test_verified_impact_high_probability_no_authority():
    e = evidence(evidence_class=EvidenceClass.FIELD)
    a = assessment(e, policy=ConvergencePolicy(verifications=(QualifiedVerification(e.evidence_hash, "verifier", "proof"),)))
    assert a.assertions[0].impact_truth == ImpactTruth.VERIFIED
    f = forecast(a)
    f = replace(f, branches=(replace(f.branches[0], probability=0.999),))
    assert all(getattr(f, field) == "none" for field in AUTHORITY_FIELDS)
    assert all(snapshot([f], a)[field] == "none" for field in AUTHORITY_FIELDS)


def test_storm_zero_and_rejected_input():
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    result = build_storm_intelligence_runtime(now=NOW, future_state_forecasts=[forecast().as_dict(), {}])
    future = result["future_state_intelligence"]
    assert future["forecast_count"] == 0
    assert future["rejections"] == ["forecast_missing_canonical_event"]


def test_superseded_snapshot_replay_preserves_history():
    f = forecast()
    newer = evidence(observed_at=NOW + timedelta(minutes=1), processed_at=NOW + timedelta(minutes=1))
    s = snapshot([f], generated_at=NOW + timedelta(minutes=2), newer_evidence=(newer,))
    assert s["forecast_count"] == 1
    assert s["freshness"][0]["state"] == "SUPERSEDED"
    assert s["convergence"][0]["consensus_state"] is None
    assert replay_future_state_snapshot(s) == s
    with pytest.raises(ValueError):
        snapshot([f], newer_evidence=[replace(newer, tenant_id="another")])


def test_resolution_replay_and_infinite_log_loss():
    from empire_os.real_world_future_state_intelligence import replay_forecast_resolution
    f = forecast()
    f = replace(f, branches=(replace(f.branches[0], probability=1),))
    outcome = evidence(observed_at=f.target_time, processed_at=f.target_time, finding="absent")
    r = ForecastResolution(f, Scenario.PERSISTING, outcome, f.target_time)
    data = r.as_dict()
    assert data["log_loss"] is None
    assert data["log_loss_status"] == "infinite"
    assert replay_forecast_resolution(json.loads(json.dumps(data))) == r
    data["brier_score"] = 0
    with pytest.raises(ValueError):
        replay_forecast_resolution(data)


def test_stale_input_explicit():
    e = evidence(valid_until=NOW)
    a = assessment(e)
    s = snapshot([forecast(a)], a)
    assert "insufficient_recent_observation" in s["reason_codes"]


def test_upstream_assessment_tamper_rejected():
    a = assessment()
    fake = replace(a, assertions=(replace(a.assertions[0], impact_truth=ImpactTruth.VERIFIED),))
    with pytest.raises(ValueError, match="tampered_assessment"):
        snapshot([forecast(fake)], fake)


def test_supporting_inputs_and_configuration_order():
    f = forecast(method_configuration=(("z", "1"), ("a", "2")))
    assert f.forecast_id == replace(f, method_configuration=(("a", "2"), ("z", "1"))).forecast_id
    with pytest.raises(ValueError):
        replace(f, branches=(replace(f.branches[0], supporting_inputs=("b" * 64,)),))
    with pytest.raises(ValueError):
        replace(f, method_configuration=(("same", "1"), ("same", "2")))


def test_storm_explicit_forecast_adapter():
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    from empire_os.spatial_physical_adapters import event_evidence_from_storm_event
    from empire_os.storm_predictor import StormEvent
    from empire_os.real_world_event_intelligence import normalized_event_evidence
    storm = StormEvent(event_id="event", event_type="Severe Thunderstorm Warning",
        area_description="County", headline="Warning", occurred_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=1)).isoformat(), severity=3,
        raw={"id": "event", "event": "Severe Thunderstorm Warning", "sent": NOW.isoformat(),
             "expires": (NOW + timedelta(hours=1)).isoformat(), "messageType": "Alert", "certainty": "Observed"},
        retrieved_at=NOW.isoformat())
    source = event_evidence_from_storm_event(storm)
    row = {"tenant_id": "tenant", "event_id": "event", "event_type": "hail", "severity": "severe",
           "starts_at": NOW.isoformat(), "ends_at": (NOW + timedelta(hours=1)).isoformat(),
           "truth_class": "OBSERVED", "event_truth_evidence": normalized_event_evidence(source),
           "evidence": [{"tenant_id": "tenant", "ref": "event", "source": "nws",
                         "observed_at": NOW.isoformat(), "valid_until": (NOW + timedelta(hours=1)).isoformat()}]}
    a = assessment()
    result = build_storm_intelligence_runtime(events=[row], impact_evidence=[evidence().as_dict()],
        future_state_forecasts=[forecast(a).as_dict()], now=NOW)
    assert result["future_state_intelligence"]["forecast_count"] == 1


def test_disjoint_uncertainty_conflict():
    f = forecast()
    f = replace(f, branches=(replace(f.branches[0], uncertainty=Uncertainty(0.7, 0.9)),))
    g = replace(f, model_id="model-b", branches=(replace(f.branches[0], probability=0.2, uncertainty=Uncertainty(0.1, 0.3)),))
    assert convergence([f, g], as_of=NOW)[0]["conflict_state"] == "CONFLICT"


def test_retrospective_trajectory_does_not_label_future_inputs_known():
    a = assessment(evidence(processed_at=NOW + timedelta(minutes=1)))
    f = forecast(a, retrospective=True)
    s = snapshot([f], a)
    trajectory = s["trajectories"][0]
    assert trajectory["retrospective"] is True
    assert trajectory["points"][0]["input_evidence_hashes"] == []


def test_resolution_unknown_probability_and_wrong_target():
    f = forecast()
    f = replace(f, branches=(replace(f.branches[0], probability=None),))
    outcome = evidence(observed_at=f.target_time, processed_at=f.target_time)
    assert ForecastResolution(f, Scenario.PERSISTING, outcome, f.target_time).as_dict()["brier_score"] is None
    with pytest.raises(ValueError):
        ForecastResolution(f, Scenario.PERSISTING, replace(outcome, valid_until=NOW), f.target_time)
