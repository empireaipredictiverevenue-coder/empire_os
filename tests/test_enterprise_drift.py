from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.enterprise_api import create_enterprise_router
from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_drift import review_enterprise_drift


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def control(status, observed_at):
    return ControlEvidence(
        control_key="tenant_row_isolation",
        family="data_isolation",
        tenant_key="tenant-1",
        status=status,
        evidence_refs=("rls:test",),
        observed_at=observed_at,
        source="control_probe",
    )


def slo(observed, observed_at):
    return SloObservation(
        service_key="public-gateway",
        metric="availability",
        target=0.99,
        observed=observed,
        window="30d",
        observed_at=observed_at,
        source="slo_probe",
    )


def test_control_and_slo_improvement_are_observed_only():
    result = review_enterprise_drift(
        baseline_controls=(control("unknown", "2026-09-20T08:00:00+00:00"),),
        current_controls=(control("pass", "2026-09-20T11:00:00+00:00"),),
        baseline_slos=(slo(0.991, "2026-09-20T08:00:00+00:00"),),
        current_slos=(slo(0.996, "2026-09-20T11:00:00+00:00"),),
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.comparison_available is True
    assert result.blockers == ()
    assert result.control_drift[0].direction == "improving"
    assert result.slo_drift[0].trend == "improving"
    assert result.slo_drift[0].margin_delta == 0.005
    assert result.execution_authority == "none"
    assert result.control_mutation is False
    assert result.infrastructure_mutation is False


def test_unknown_slo_observation_stays_unknown_and_blocks_full_comparison():
    result = review_enterprise_drift(
        baseline_controls=(control("pass", "2026-09-20T08:00:00+00:00"),),
        current_controls=(control("pass", "2026-09-20T11:00:00+00:00"),),
        baseline_slos=(slo(None, "2026-09-20T08:00:00+00:00"),),
        current_slos=(slo(0.996, "2026-09-20T11:00:00+00:00"),),
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.comparison_available is False
    assert result.slo_drift[0].trend == "unknown"
    assert result.slo_drift[0].margin_delta is None
    assert any(
        blocker.endswith("_observed_value_missing")
        for blocker in result.blockers
    )


def test_stale_baseline_blocks_drift_review():
    result = review_enterprise_drift(
        baseline_controls=(control("pass", "2026-09-20T01:00:00+00:00"),),
        current_controls=(control("pass", "2026-09-20T11:00:00+00:00"),),
        baseline_slos=(slo(0.991, "2026-09-20T01:00:00+00:00"),),
        current_slos=(slo(0.996, "2026-09-20T11:00:00+00:00"),),
        now=NOW,
        max_age_seconds=21600,
    )
    assert result.comparison_available is False
    assert any("evidence_stale" in blocker for blocker in result.blockers)


def test_drift_preview_cannot_mutate_enterprise_state():
    app = FastAPI()
    app.include_router(create_enterprise_router())
    payload = {
        "now_utc": "2026-09-20T12:00:00+00:00",
        "max_age_seconds": 21600,
        "baseline_controls": [{
            "control_key": "tenant_row_isolation",
            "family": "data_isolation",
            "tenant_key": "tenant-1",
            "status": "unknown",
            "evidence_refs": ["rls:test"],
            "observed_at": "2026-09-20T08:00:00+00:00",
            "source": "control_probe",
        }],
        "current_controls": [{
            "control_key": "tenant_row_isolation",
            "family": "data_isolation",
            "tenant_key": "tenant-1",
            "status": "pass",
            "evidence_refs": ["rls:test:current"],
            "observed_at": "2026-09-20T11:00:00+00:00",
            "source": "control_probe",
        }],
        "baseline_slos": [{
            "service_key": "public-gateway",
            "metric": "availability",
            "target": 0.99,
            "observed": 0.991,
            "window": "30d",
            "observed_at": "2026-09-20T08:00:00+00:00",
            "source": "slo_probe",
        }],
        "current_slos": [{
            "service_key": "public-gateway",
            "metric": "availability",
            "target": 0.99,
            "observed": 0.996,
            "window": "30d",
            "observed_at": "2026-09-20T11:00:00+00:00",
            "source": "slo_probe",
        }],
    }
    response = TestClient(app).post(
        "/v1/enterprise/drift/preview",
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["control_mutation"] is False
    assert body["infrastructure_mutation"] is False
    assert body["identity_mutation"] is False
    assert body["backup_mutation"] is False
    assert body["slo_target_mutation"] is False
    assert body["compliance_mutation"] is False
    assert body["drift"]["comparison_available"] is True
    assert body["drift"]["control_drift"][0]["direction"] == "improving"
    assert body["drift"]["slo_drift"][0]["trend"] == "improving"
