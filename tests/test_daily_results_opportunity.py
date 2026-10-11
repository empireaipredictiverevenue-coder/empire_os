"""Founder daily opportunity proof must distinguish cycle observations from truth."""
from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from empire_os.daily_results import build_daily_results, opportunity_daily_results

NOW = datetime(2026, 10, 11, 16, 30, tzinfo=timezone.utc)
START = "2026-10-11T16:13:16+00:00"
ROUTED = "2026-10-11T16:13:42+00:00"
FINISH = "2026-10-11T16:13:44+00:00"


def loop():
    return {
        "schema_version": "empire.predictive_cloud.opportunity_loop.v2",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "ok": True,
        "started_at": START, "finished_at": FINISH,
        "radar_candidate_count": 18,
        "research_candidate_count": 3,
        "research_new_observation_count": 10,
        "factory_blocked_count": 18,
        "opportunity_stage_counts": {"QUALIFY": 18},
        "revenue_recognized": False,
        "outreach_sent": False,
    }


def routes(*, with_history=False):
    result = {
        "schema_version": "empire.opportunity_evidence_routes.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "automatic_external_execution_allowed": False,
        "generated_at": ROUTED,
        "stage_counts": {"QUALIFY": 18},
    }
    if with_history:
        result["history"] = {
            "schema_version": "empire.opportunity_evidence_history.v1",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "automatic_external_execution_allowed": False,
            "commercial_stage_independently_verified": False,
            "previous_stage_never_promoted": True,
            "generated_at": ROUTED,
            "new_identity_count": 2,
            "stage_transition_count_this_cycle": 1,
        }
    return result


def cortex():
    return {
        "schema_version": "empire.cortex_learning_snapshot.v1",
        "mode": "OBSERVE", "execution_authority": "none",
        "generated_at": "2026-10-11T16:15:00+00:00",
        "forecast_used_as_outcome": False,
        "synthetic_commercial_label_count": 0,
        "model_weight_mutation_authorized": False,
        "verified_customer_learning_count": 0,
    }


def test_latest_same_day_cycle_reports_exact_observation_not_daily_totals():
    out = opportunity_daily_results(loop(), routes(), {}, now=NOW)
    assert out["source_status"] == "OBSERVED_LATEST_ON_DATE_LOOP"
    assert out["date"] == "2026-10-11"
    assert out["coverage"] == "LATEST_COMPLETED_CYCLE_ONLY_NOT_DAILY_TOTAL"
    assert out["found"]["observed_candidates_latest_cycle"] == 18
    assert out["found"]["new_identity_count_latest_cycle"] is None
    assert out["researched"]["candidates_latest_cycle"] == 3
    assert out["researched"]["new_public_observations_latest_cycle"] == 10
    assert out["blocked"]["factory_blocked_latest_cycle"] == 18
    assert out["advanced"]["derived_stage_transitions_latest_cycle"] is None
    assert out["advanced"]["current_derived_stage_counts"] == {"QUALIFY": 18}
    assert out["advanced"]["commercial_promotion_verified"] is False
    assert out["proved"]["verified_commercial_outcomes_today"] is None
    assert out["learned"]["verified_customer_learning_packets_latest_snapshot"] is None
    assert out["learned"]["model_weights_changed"] is None
    assert out["forecast_as_realized_revenue"] is False
    assert out["execution_authority"] == "none"
    assert out["external_execution_performed"] is False


def test_exact_matching_observe_only_history_provides_derived_transitions():
    out = opportunity_daily_results(loop(), routes(with_history=True), cortex(), now=NOW)
    assert out["found"]["new_identity_count_latest_cycle"] == 2
    assert out["advanced"]["derived_stage_transitions_latest_cycle"] == 1
    assert out["advanced"]["commercial_promotion_verified"] is False
    assert out["source_freshness"]["routes_current_day"] is True
    assert out["source_freshness"]["cortex_current_day"] is True
    assert out["learned"]["verified_customer_learning_packets_latest_snapshot"] == 0
    assert out["learned"]["model_weights_changed"] is False
    assert out["proved"]["verified_commercial_outcomes_today"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("automatic_external_execution_allowed", True),
    ("ok", False),
    ("schema_version", "not-the-opportunity-loop"),
    ("finished_at", "2026-10-10T16:13:44+00:00"),
    ("started_at", "2026-10-10T16:13:16+00:00"),
    ("finished_at", "2026-10-11T17:10:44+00:00"),
    ("finished_at", "2026-10-11T16:13:44"),
])
def test_old_untrusted_or_future_loop_never_claims_today_findings(field, value):
    candidate = loop()
    candidate[field] = value
    result = opportunity_daily_results(candidate, routes(with_history=True), {}, now=NOW)
    assert result["source_status"] == "NO_COMPLETE_ON_DATE_OPPORTUNITY_LOOP"
    assert result["found"]["observed_candidates_latest_cycle"] is None
    assert result["researched"]["new_public_observations_latest_cycle"] is None
    assert result["blocked"]["factory_blocked_latest_cycle"] is None
    assert result["advanced"]["current_derived_stage_counts"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("radar_candidate_count", True),
    ("radar_candidate_count", "18"),
    ("research_new_observation_count", -1),
    ("research_new_observation_count", "10"),
    ("factory_blocked_count", 3.14),
    ("factory_blocked_count", 1_000_001),
])
def test_missing_or_untyped_count_cannot_be_inferred(field, value):
    candidate = loop()
    candidate[field] = value
    out = opportunity_daily_results(candidate, routes(), {}, now=NOW)
    assert out["source_status"] == "OBSERVED_LATEST_ON_DATE_LOOP"
    lookup = {
        "radar_candidate_count": ("found", "observed_candidates_latest_cycle"),
        "research_new_observation_count": ("researched", "new_public_observations_latest_cycle"),
        "factory_blocked_count": ("blocked", "factory_blocked_latest_cycle"),
    }
    section, key = lookup[field]
    assert out[section][key] is None


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("automatic_external_execution_allowed", True),
    ("generated_at", "2026-10-10T16:13:42+00:00"),
    ("generated_at", "2026-10-11T17:00:42+00:00"),
    ("schema_version", "fabricated"),
])
def test_wrong_day_or_untrusted_router_cannot_create_advancement(field, value):
    source = routes(with_history=True)
    source[field] = value
    out = opportunity_daily_results(loop(), source, cortex(), now=NOW)
    assert out["source_freshness"]["routes_current_day"] is False
    assert out["advanced"]["derived_stage_transitions_latest_cycle"] is None
    assert out["found"]["new_identity_count_latest_cycle"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("commercial_stage_independently_verified", True),
    ("automatic_external_execution_allowed", True),
    ("previous_stage_never_promoted", False),
    ("generated_at", "2026-10-10T16:13:42+00:00"),
    ("new_identity_count", True),
    ("stage_transition_count_this_cycle", "1"),
])
def test_untrusted_history_cannot_be_promoted_into_daily_progress(field, value):
    source = routes(with_history=True)
    source["history"][field] = value
    out = opportunity_daily_results(loop(), source, {}, now=NOW)
    if field == "new_identity_count":
        assert out["found"]["new_identity_count_latest_cycle"] is None
    elif field == "stage_transition_count_this_cycle":
        assert out["advanced"]["derived_stage_transitions_latest_cycle"] is None
    else:
        assert out["advanced"]["derived_stage_transitions_latest_cycle"] is None
        assert out["found"]["new_identity_count_latest_cycle"] is None


def test_stale_cortex_cannot_be_reported_as_today_learning():
    source = cortex()
    source["generated_at"] = "2026-09-22T23:16:26+00:00"
    source["verified_customer_learning_count"] = 73
    out = opportunity_daily_results(loop(), routes(), source, now=NOW)
    assert out["source_freshness"]["cortex_current_day"] is False
    assert out["learned"]["verified_customer_learning_packets_latest_snapshot"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("mode", "EXECUTE"),
    ("execution_authority", "live"),
    ("forecast_used_as_outcome", True),
    ("model_weight_mutation_authorized", True),
    ("synthetic_commercial_label_count", 1),
    ("verified_customer_learning_count", True),
])
def test_forged_learning_source_not_real_verified_learning(field, value):
    item = cortex()
    item[field] = value
    out = opportunity_daily_results(loop(), routes(), item, now=NOW)
    if field == "verified_customer_learning_count":
        assert out["learned"]["verified_customer_learning_packets_latest_snapshot"] is None
    else:
        assert out["source_freshness"]["cortex_current_day"] is False
        assert out["learned"]["verified_customer_learning_packets_latest_snapshot"] is None


def test_british_day_rollover_never_reuses_prior_local_day_snapshot():
    after_midnight = datetime(2026, 10, 11, 23, 5, tzinfo=timezone.utc)
    out = opportunity_daily_results(loop(), routes(), cortex(), now=after_midnight)
    assert out["date"] == "2026-10-12"
    assert out["source_freshness"]["loop_current_day"] is False
    assert out["found"]["observed_candidates_latest_cycle"] is None


def test_pure_projection_does_not_mutate_input_data():
    inputs = (loop(), routes(with_history=True), cortex())
    originals = deepcopy(inputs)
    result = opportunity_daily_results(*inputs, now=NOW)
    assert inputs == originals
    assert result["proved"]["status"] == "CANONICAL_OUTCOME_EVENT_FEED_NOT_BOUND"


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def test_existing_daily_results_includes_new_section_without_new_reporting_runtime(tmp_path):
    runtime = tmp_path / "runtime"
    _write(runtime / "opportunity_radar/loop_latest.json", loop())
    _write(runtime / "opportunity_factory/evidence_routes_latest.json", routes(with_history=True))
    _write(runtime / "cortex_learning/cortex_learning_latest.json", cortex())
    original_files = {str(path): path.read_bytes() for path in runtime.rglob("*.json")}
    report = build_daily_results(tmp_path, now=NOW)
    assert report["schema_version"] == "empire.daily_results.v1"
    assert report["opportunity_daily"]["found"]["observed_candidates_latest_cycle"] == 18
    assert report["opportunity_daily"]["researched"]["new_public_observations_latest_cycle"] == 10
    assert report["opportunity_daily"]["advanced"]["derived_stage_transitions_latest_cycle"] == 1
    assert report["opportunity_daily"]["proved"]["verified_commercial_outcomes_today"] is None
    assert report["controls_execution"] is False
    assert {str(path): path.read_bytes() for path in runtime.rglob("*.json")} == original_files
    assert not (runtime / "daily_results").exists()



def test_existing_founder_daily_results_api_exposes_opportunity_section(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import empire_os.founder_daily_results_api as api

    _write(tmp_path / "runtime/opportunity_radar/loop_latest.json", loop())
    _write(tmp_path / "runtime/opportunity_factory/evidence_routes_latest.json", routes())
    payload = build_daily_results(tmp_path, now=NOW)
    latest = tmp_path / "runtime/daily_results/latest.json"
    _write(latest, payload)
    monkeypatch.setattr(api, "LATEST", latest)
    app = FastAPI()
    app.include_router(api.create_founder_daily_results_router())
    response = TestClient(app).get("/v1/founder-daily-results/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["opportunity_daily"]["found"]["observed_candidates_latest_cycle"] == 18
    assert body["opportunity_daily"]["proved"]["verified_commercial_outcomes_today"] is None
    assert body["execution_authority"] == "none"
