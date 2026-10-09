"""Local fixtures only; no network, execution, or production persistence."""
from dataclasses import replace, FrozenInstanceError
from datetime import datetime, timedelta, timezone
import copy
import json

import pytest

from empire_os.real_world_decision_intelligence import (
    CandidateType, DecisionState, DecisionContext, DecisionWindow, QualityDimensions,
    CounterfactualReference, DecisionRegret, InformationRequest, WaitingRisk,
    DecisionCandidate, DecisionRecommendation, make_candidate, recommend, dominates,
    waiting_risk, next_best_evidence, build_decision_snapshot, replay_decision_snapshot,
    replay_candidate, replay_context, write_decision_snapshot, build_storm_decision_surface,
    MAX_CANDIDATES, MAX_DIAGNOSTICS,
)
from empire_os.real_world_future_state_intelligence import (
    FutureStateForecast, Horizon, Scenario, ScenarioBranch, Uncertainty, build_future_state_snapshot,
)
from empire_os.real_world_impact_intelligence import (
    ImpactEvidence, ImpactTruth, EvidenceClass, EffectCategory, TruthDomain,
    ConvergencePolicy, QualifiedVerification, assess_impact, _hash,
)
from empire_os.real_world_event_intelligence import AUTHORITY_FIELDS

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def evidence(**changes):
    data = dict(tenant_id="tenant", event_id="event", subject_id="subject",
        source="sensor", source_record_id="record", evidence_class=EvidenceClass.SENSOR,
        phenomenon="water", effect_category=EffectCategory.FLOODING, domain=TruthDomain.IMPACT,
        finding="present", observed_at=NOW, processed_at=NOW, valid_from=NOW,
        valid_until=NOW + timedelta(hours=24), source_truth="OBSERVED_SOURCE_RECORD",
        physical_truth=ImpactTruth.SOURCE_REPORTED, confidence=None,
        raw_evidence_hash="a" * 64, provenance=("source-record",))
    return ImpactEvidence(**dict(data, **changes))


def context(*, empty=False, verified=False, forecast=False, scenario=Scenario.WORSENING,
            seconds=3600, **changes):
    e = evidence(evidence_class=EvidenceClass.FIELD if verified else EvidenceClass.SENSOR)
    policy = ConvergencePolicy(verifications=(QualifiedVerification(e.evidence_hash, "verifier", "proof"),)) if verified else ConvergencePolicy()
    a = assess_impact(() if empty else (e,), tenant_id="tenant", now=NOW, policy=policy)
    forecasts = ()
    if forecast:
        forecasts = (FutureStateForecast("tenant", "event", "subject", "water", "flooding", "impact",
            NOW, Horizon(seconds), "supplied-model", "model", (), (e.evidence_hash,), (a.assessment_id,),
            (ScenarioBranch(scenario, "present", 0.8, Uncertainty(), (e.evidence_hash,)),),
            NOW + timedelta(seconds=seconds), NOW, ("model-output",)),)
    data = dict(tenant_id="tenant", event_id="event", subject_id="subject", assessment=a,
                forecasts=forecasts, as_of=NOW, objective="Review impact", constraints=("internal_only",))
    return DecisionContext(**dict(data, **changes))


def candidate(c=None, action=CandidateType.OBSERVE, **kwargs):
    return make_candidate(c or context(), action, **kwargs)


def artifact(c=None, candidates=None, generated_at=NOW):
    return build_decision_snapshot(recommend(c or context(), candidates), generated_at=generated_at)


def test_recommendation_cannot_execute_and_economics_unknown():
    result = recommend(context(verified=True, forecast=True))
    assert result.state == DecisionState.RECOMMEND
    assert result.economics == "unknown"
    for obj in (result, result.context, *result.candidates, result.waiting_risk, result.regret,
                result.candidates[0].window, result.candidates[0].dimensions, *result.candidates[0].information_requests):
        assert all(getattr(obj, key) == "none" for key in AUTHORITY_FIELDS)
        assert not hasattr(obj, "execute")
    for forbidden in ("expected_revenue", "cost", "roi", "pricing"):
        assert forbidden not in result.as_dict()
    with pytest.raises(FrozenInstanceError):
        result.economics = "revenue"


@pytest.mark.parametrize("authority", AUTHORITY_FIELDS)
def test_authority_escalation_all_objects(authority):
    c = context(forecast=True)
    d = recommend(c)
    objects = (c, d, candidate(c), DecisionWindow(), QualityDimensions(), next_best_evidence(c)[0],
               CounterfactualReference(c.forecasts[0].forecast_id, Scenario.WORSENING), waiting_risk(c), d.regret)
    for obj in objects:
        with pytest.raises(ValueError, match="authority"):
            replace(obj, **{authority: "live"})


@pytest.mark.parametrize("field,value", [("tenant_id", "other"), ("event_id", "other"), ("subject_id", "other")])
def test_context_scope_isolation(field, value):
    with pytest.raises(ValueError):
        context(**{field: value})


@pytest.mark.parametrize("field", ["tenant_id", "event_id", "subject_id"])
def test_forecast_scope_isolation(field):
    c = context(forecast=True)
    with pytest.raises(ValueError):
        replace(c, forecasts=(replace(c.forecasts[0], **{field: "other"}),))


def test_forecast_cannot_rewrite_observations():
    c = context(forecast=True)
    before = c.assessment.as_dict()
    recommend(c)
    assert c.assessment.as_dict() == before
    assert c.assessment.assertions[0].impact_truth == ImpactTruth.SOURCE_REPORTED


def test_insufficient_evidence_and_zero_recommendations_valid():
    d = recommend(context(empty=True))
    assert d.state == DecisionState.INSUFFICIENT_EVIDENCE
    assert d.recommended_candidate is None
    assert d.candidates == ()
    assert replay_decision_snapshot(artifact(context(empty=True))).decision_id == d.decision_id


@pytest.mark.parametrize("action,state", [
    (CandidateType.OBSERVE, DecisionState.OBSERVE), (CandidateType.WAIT, DecisionState.WAIT),
    (CandidateType.GATHER_EVIDENCE, DecisionState.GATHER_EVIDENCE),
    (CandidateType.ESCALATE_FOR_REVIEW, DecisionState.REVIEW_REQUIRED),
    (CandidateType.NO_ACTION, DecisionState.NO_ACTION), (CandidateType.OTHER, DecisionState.UNKNOWN),
])
def test_explicit_states(action, state):
    c = context()
    d = recommend(c, [candidate(c, action)])
    assert d.state == state
    assert d.reason_codes


def test_gather_evidence_is_default_when_impact_not_verified():
    d = recommend(context(forecast=True))
    assert d.state == DecisionState.GATHER_EVIDENCE
    request = d.candidates[0].information_requests[0]
    assert request.could_change_recommendation is True
    assert request.missing_evidence == ("physical_verification_missing",)
    assert request.decision_sensitive_uncertainty == "impact_presence_unresolved"
    assert request.recommended_evidence_class == EvidenceClass.FIELD
    assert request.expected_decision_effect


def test_verified_worsening_can_prepare_or_review_only():
    c = context(verified=True, forecast=True)
    assert recommend(c).state == DecisionState.RECOMMEND
    assert recommend(c, [candidate(c, CandidateType.REVIEW)]).state == DecisionState.REVIEW_REQUIRED
    assert all(getattr(recommend(c), k) == "none" for k in AUTHORITY_FIELDS)


def test_unverified_prepare_rejected():
    c = context(forecast=True)
    d = recommend(c, [candidate(c, CandidateType.PREPARE)])
    assert d.recommended_candidate is None
    assert d.diagnostics == ("invalid_candidate",)


def test_ambiguous_ties_remain_visible_and_stable():
    c = context()
    a, b = candidate(c), candidate(c, CandidateType.WAIT)
    x, y = recommend(c, [a, b]), recommend(c, [b, a, a])
    assert x.decision_id == y.decision_id
    assert x.state == DecisionState.REVIEW_REQUIRED and x.ambiguous
    assert x.recommended_candidate is None
    assert len(x.alternatives) == 2 and len(x.candidates) == 2
    assert not dominates(a, b)


def test_conservative_pareto_no_magic_score():
    a, b = candidate(), candidate(action=CandidateType.WAIT)
    all_known = QualityDimensions(**{name: 0.5 for name in (
        "evidence_strength", "forecast_support", "uncertainty", "urgency", "reversibility",
        "optionality", "information_gap", "time_sensitivity", "downside_risk", "confidence")})
    b = replace(b, dimensions=all_known)
    a = replace(a, dimensions=replace(all_known, reversibility=0.9))
    assert dominates(a, b) and not dominates(b, a)
    assert not dominates(replace(a, dimensions=replace(a.dimensions, confidence=0.2)), b)
    assert not dominates(replace(a, dimensions=replace(a.dimensions, downside_risk=None)), b)
    assert not dominates(replace(a, dimensions=replace(a.dimensions, urgency=0.9)), b)
    assert not hasattr(a.dimensions, "score")
    # V1 cannot certify these caller-invented dimensions as supported.
    assert recommend(context(), [a]).diagnostics == ("invalid_candidate",)


@pytest.mark.parametrize("seconds,level", [(3600, "HIGH"), (7200, "MODERATE")])
def test_waiting_risk_supported_temporal_facts(seconds, level):
    risk = waiting_risk(context(forecast=True, seconds=seconds))
    assert risk.level.value == level
    assert risk.supporting_forecasts


def test_unknown_waiting_risk_and_expired_forecast():
    assert waiting_risk(context()).level.value == "UNKNOWN"
    c = context(forecast=True)
    assert waiting_risk(replace(c, as_of=NOW + timedelta(hours=2))).level.value == "UNKNOWN"
    assert waiting_risk(context(forecast=True, scenario=Scenario.IMPROVING)).level.value == "UNKNOWN"


def test_counterfactual_is_hypothetical_with_branch_lineage():
    c = context(forecast=True)
    ref = CounterfactualReference(c.forecasts[0].forecast_id, Scenario.WORSENING)
    a = candidate(c, counterfactuals=(ref,))
    assert recommend(c, [a]).recommended_candidate == a.candidate_id
    assert ref.hypothetical and ref.causal_effect == "unknown"
    invalid = replace(a, counterfactuals=(replace(ref, scenario=Scenario.RESOLVED),))
    assert recommend(c, [invalid]).diagnostics == ("invalid_candidate",)
    with pytest.raises(ValueError):
        replace(ref, hypothetical=False)
    with pytest.raises(ValueError):
        replace(ref, causal_effect="caused")


def test_decision_window_and_stale_recommendation():
    c = context(forecast=True)
    f = c.forecasts[0]
    w = DecisionWindow(NOW, f.target_time, f.valid_until, f.valid_until, (f.forecast_id,))
    d = recommend(c, [candidate(c, window=w)])
    assert d.freshness_at(NOW) == "CURRENT"
    assert d.freshness_at(f.valid_until) == "STALE"
    assert artifact(c, [candidate(c, window=w)], f.valid_until)["freshness"] == "STALE"
    expired = replace(c, as_of=f.valid_until)
    assert recommend(expired, [candidate(expired, window=w)]).recommended_candidate is None
    with pytest.raises(ValueError):
        DecisionWindow(f.target_time, NOW)
    invalid = replace(w, review_at=NOW + timedelta(minutes=1))
    assert recommend(c, [candidate(c, window=invalid)]).diagnostics == ("invalid_candidate",)


def test_determinism_generation_not_identity_replay(tmp_path):
    c = context(forecast=True, as_of=NOW + timedelta(minutes=2))
    f = replace(c.forecasts[0], generated_at=NOW + timedelta(minutes=1))
    again = replace(c, forecasts=(f,))
    assert c.context_id == again.context_id
    assert candidate(c).candidate_id == candidate(again).candidate_id
    assert recommend(c).decision_id == recommend(again).decision_id
    a = artifact(c, generated_at=c.as_of)
    b = artifact(c, generated_at=c.as_of + timedelta(minutes=1))
    assert a["decision"]["decision_id"] == b["decision"]["decision_id"]
    p = write_decision_snapshot(tmp_path / "decision.json", a)
    assert replay_decision_snapshot(json.loads(p.read_text())).decision_id == recommend(c).decision_id
    assert not list(tmp_path.glob(".decision-*"))


def test_retrieval_time_not_identity():
    c = context(as_of=NOW + timedelta(minutes=5))
    e = replace(c.assessment.evidence[0], processed_at=NOW + timedelta(minutes=1))
    a = assess_impact([e], tenant_id="tenant", now=c.as_of)
    again = replace(c, assessment=a)
    assert c.context_id == again.context_id
    assert recommend(c).decision_id == recommend(again).decision_id


@pytest.mark.parametrize("target", ["hash", "authority", "state", "regret", "context", "candidate"])
def test_tamper_rejection_even_rehashed(target):
    s = artifact()
    if target == "hash":
        s["snapshot_hash"] = "a" * 64
    else:
        d = s["decision"]
        if target == "authority":
            d["payment_authority"] = "live"
        elif target == "state":
            d["state"] = "RECOMMEND"
        elif target == "regret":
            d["regret"]["regret_classification"] = "LOW"
        elif target == "context":
            d["context"]["event_id"] = "other"
        elif target == "candidate":
            d["candidates"][0]["why_considered"] = "tampered"
        s["snapshot_hash"] = _hash({k: v for k, v in s.items() if k != "snapshot_hash"})
    with pytest.raises((ValueError, TypeError)):
        replay_decision_snapshot(s)


@pytest.mark.parametrize("value", [NOW.replace(tzinfo=None), "2026-10-05T00:00:00", None])
def test_naive_or_missing_timestamp_rejected(value):
    with pytest.raises(ValueError):
        context(as_of=value)


def test_future_leakage_rejected():
    with pytest.raises(ValueError):
        context(as_of=NOW - timedelta(seconds=1))
    c = context(forecast=True)
    with pytest.raises(ValueError):
        replace(c, forecasts=(replace(c.forecasts[0], generated_at=NOW + timedelta(seconds=1)),))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.1, 1.1, True, "0.5"])
def test_invalid_dimensions(value):
    with pytest.raises(ValueError):
        QualityDimensions(confidence=value)


@pytest.mark.parametrize("action", ["SEND", "CALL", "PAY", "DISPATCH", "PURCHASE", "RECOGNISE_REVENUE"])
def test_unsupported_action_class(action):
    with pytest.raises(ValueError):
        candidate(action=action)


def test_malformed_batch_isolation_and_bounds():
    c = context()
    a = candidate(c)
    d = recommend(c, [None, {}, a, {"execution_authority": "live"}])
    assert d.recommended_candidate == a.candidate_id
    assert d.diagnostics == ("invalid_candidate",)
    assert len(d.diagnostics) <= MAX_DIAGNOSTICS
    overflow = recommend(c, (a for _ in range(MAX_CANDIDATES + 100)))
    assert overflow.candidates == () and overflow.diagnostics == ("candidate_batch_limit",)


def test_bad_candidate_context_isolated():
    c = context()
    other = context(objective="different")
    assert recommend(c, [candidate(other), candidate(c)]).diagnostics == ("invalid_candidate",)


def test_regret_unresolved_without_outcome():
    r = recommend(context()).regret
    assert r.regret_classification == "UNRESOLVED" and r.resolved_at is None
    assert r.future_outcome_reference is None
    with pytest.raises(ValueError):
        replace(r, regret_classification="LOW")
    with pytest.raises(ValueError):
        replace(r, future_outcome_reference="invented")


def test_storm_warning_without_impact_observes_no_commercial_action():
    c = context(empty=True)
    f = build_future_state_snapshot((), assessment=c.assessment, generated_at=NOW)
    result = build_storm_decision_surface([f], [("tenant", "event")], as_of=NOW)
    assert result["diagnostics"] == []
    d = replay_decision_snapshot(result["decisions"][0])
    assert d.state == DecisionState.OBSERVE
    assert all(getattr(d, k) == "none" for k in AUTHORITY_FIELDS)
    assert d.candidates[0].information_requests[0].could_change_recommendation


def test_storm_verified_worsening_still_no_authority():
    c = context(verified=True, forecast=True)
    f = build_future_state_snapshot(c.forecasts, assessment=c.assessment, generated_at=NOW)
    result = build_storm_decision_surface([f], [("tenant", "event")], as_of=NOW)
    assert result["diagnostics"] == []
    d = replay_decision_snapshot(result["decisions"][0])
    assert d.state == DecisionState.RECOMMEND
    assert all(getattr(d, k) == "none" for k in AUTHORITY_FIELDS)


def test_conflicting_impact_requires_review():
    c = context()
    a = assess_impact([evidence(), evidence(source_record_id="other", finding="absent")],
                      tenant_id="tenant", now=NOW)
    d = recommend(replace(c, assessment=a))
    assert d.state == DecisionState.REVIEW_REQUIRED
    assert d.reason_codes == ("conflicting_impact_evidence",)


def test_verified_without_worsening_observes():
    assert recommend(context(verified=True)).state == DecisionState.OBSERVE


@pytest.mark.parametrize("field", ["tenant_id", "event_id", "subject_id", "objective"])
def test_missing_identity_rejected(field):
    with pytest.raises(ValueError):
        context(**{field: " "})


def test_candidate_cannot_omit_evidence_used_by_dimensions():
    c = context(forecast=True)
    a = candidate(c)
    for bad in (replace(a, supporting_evidence=()), replace(a, supporting_forecasts=())):
        assert recommend(c, [bad, a]).diagnostics == ("invalid_candidate",)


def test_invalid_counterfactual_forecast_lineage_isolated():
    c = context(forecast=True)
    ref = CounterfactualReference("b" * 64, Scenario.WORSENING)
    assert recommend(c, [candidate(c, counterfactuals=(ref,)), candidate(c)]).diagnostics == ("invalid_candidate",)


def test_storm_actual_runtime_hook():
    from empire_os.storm_intelligence_runtime import build_storm_intelligence_runtime
    result = build_storm_intelligence_runtime(events=[{
        "tenant_id": "tenant", "event_id": "event", "event_type": "hail", "severity": "severe",
        "starts_at": (NOW - timedelta(hours=2)).isoformat(),
        "ends_at": (NOW + timedelta(hours=2)).isoformat(), "truth_class": "OBSERVED",
        "evidence": [{"tenant_id": "tenant", "ref": "event:nws:event", "source": "nws",
            "observed_at": NOW.isoformat(), "valid_until": (NOW + timedelta(hours=3)).isoformat()}],
    }], now=NOW)
    surface = result["decision_intelligence"]
    assert surface["diagnostics"] == []
    assert len(surface["decisions"]) == 1
    assert surface["decisions"][0]["decision"]["state"] == "OBSERVE"


def test_storm_multi_event_does_not_rebind_forecasts():
    c = context(forecast=True)
    a = assess_impact([evidence(), evidence(event_id="other-event", source_record_id="other")],
                      tenant_id="tenant", now=NOW)
    f = replace(c.forecasts[0], input_assessment_hashes=(a.assessment_id,))
    upstream = build_future_state_snapshot([f], assessment=a, generated_at=NOW)
    surface = build_storm_decision_surface([upstream], [("tenant", "event"), ("tenant", "other-event")], as_of=NOW)
    assert surface["diagnostics"] == ["forecast_requires_scoped_assessment"]
    assert len(surface["decisions"]) == 2
    for row in surface["decisions"]:
        d = replay_decision_snapshot(row)
        assert all(e.event_id == d.context.event_id for e in d.context.assessment.evidence)
        assert d.context.forecasts == ()


def test_storm_future_assessment_isolated_and_duplicate_ambiguous():
    c = context()
    upstream = build_future_state_snapshot([], assessment=c.assessment, generated_at=NOW)
    duplicate = build_storm_decision_surface([upstream, upstream], [("tenant", "event")], as_of=NOW)
    assert duplicate["decisions"] == []
    assert duplicate["diagnostics"] == ["ambiguous_future_assessment"]
    invalid = build_storm_decision_surface([{}, upstream], [("tenant", "event")], as_of=NOW)
    assert len(invalid["decisions"]) == 1
    assert invalid["diagnostics"] == ["invalid_future_assessment"]


def test_storm_superseded_forecasts_not_recommended():
    c = context(verified=True, forecast=True)
    later = NOW + timedelta(minutes=1)
    newer = replace(c.assessment.evidence[0], source_record_id="new", observed_at=later, processed_at=later)
    upstream = build_future_state_snapshot(c.forecasts, assessment=c.assessment, generated_at=later,
                                          newer_evidence=(newer,))
    surface = build_storm_decision_surface([upstream], [("tenant", "event")], as_of=later)
    assert surface["diagnostics"] == ["forecast_not_current"]
    d = replay_decision_snapshot(surface["decisions"][0])
    assert d.state == DecisionState.OBSERVE and d.context.forecasts == ()


def test_generated_before_decision_and_read_before_decision_rejected():
    d = recommend(context())
    with pytest.raises(ValueError):
        build_decision_snapshot(d, generated_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        d.freshness_at(NOW - timedelta(seconds=1))


def test_missing_constraint_fails_closed():
    c = context()
    assert recommend(c, [replace(candidate(c), constraints=())]).diagnostics == ("invalid_candidate",)


def test_snapshot_size_bound(monkeypatch):
    import empire_os.real_world_decision_intelligence as module
    monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", 10)
    with pytest.raises(ValueError, match="snapshot_size_limit"):
        artifact()
