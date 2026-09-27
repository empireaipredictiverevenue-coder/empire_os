from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.enterprise_api import create_enterprise_router
from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_freshness import review_enterprise_evidence


NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def control(observed_at="2026-09-20T11:30:00+00:00"):
    return ControlEvidence(
        control_key="tenant_row_isolation",
        family="data_isolation",
        tenant_key="tenant-1",
        status="pass",
        evidence_refs=("rls:test",),
        observed_at=observed_at,
        source="control_probe",
    )


def slo(observed_at, observed):
    return SloObservation(
        service_key="public-gateway",
        metric="availability",
        target=0.99,
        observed=observed,
        window="30d",
        observed_at=observed_at,
        source="slo_probe",
    )


def test_fresh_evidence_and_improving_slo_trend():
    review = review_enterprise_evidence(
        controls=(control(),),
        slos=(
            slo("2026-09-20T10:00:00+00:00", 0.992),
            slo("2026-09-20T11:00:00+00:00", 0.995),
        ),
        now=NOW,
        max_age_seconds=10800,
    )
    assert review.fresh_for_review is True
    assert review.trend_review_complete is True
    assert review.blockers == ()
    trend = review.slo_trends[0]
    assert trend.trend == "improving"
    assert trend.observed_sample_count == 2
    assert trend.latest_meets_target is True
    assert review.execution_authority == "none"


def test_unknown_slo_value_preserves_unknown_trend():
    review = review_enterprise_evidence(
        controls=(control(),),
        slos=(
            slo("2026-09-20T10:00:00+00:00", None),
            slo("2026-09-20T11:00:00+00:00", 0.995),
        ),
        now=NOW,
        max_age_seconds=10800,
    )
    assert review.fresh_for_review is True
    assert review.trend_review_complete is False
    trend = review.slo_trends[0]
    assert trend.trend == "unknown"
    assert trend.observed_sample_count == 1


def test_stale_and_future_evidence_are_explicit_blockers():
    review = review_enterprise_evidence(
        controls=(control("2026-09-20T03:00:00+00:00"),),
        slos=(
            slo("2026-09-20T12:05:00+00:00", 0.995),
            slo("2026-09-20T11:00:00+00:00", 0.994),
        ),
        now=NOW,
        max_age_seconds=21600,
    )
    assert review.fresh_for_review is False
    assert "control_tenant_row_isolation_evidence_stale" in review.blockers
    assert any(item.endswith("_evidence_future") for item in review.blockers)


def test_preview_endpoint_is_observe_only():
    app = FastAPI()
    app.include_router(create_enterprise_router())
    response = TestClient(app).post(
        "/v1/enterprise/freshness/preview",
        json={
            "now_utc": "2026-09-20T12:00:00+00:00",
            "max_age_seconds": 10800,
            "controls": [{
                "control_key": "tenant_row_isolation",
                "family": "data_isolation",
                "tenant_key": "tenant-1",
                "status": "pass",
                "evidence_refs": ["rls:test"],
                "observed_at": "2026-09-20T11:30:00+00:00",
                "source": "control_probe",
            }],
            "slos": [{
                "service_key": "public-gateway",
                "metric": "availability",
                "target": 0.99,
                "observed": 0.995,
                "window": "30d",
                "observed_at": "2026-09-20T11:00:00+00:00",
                "source": "slo_probe",
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["control_mutation"] is False
    assert body["infrastructure_mutation"] is False
    assert body["slo_target_mutation"] is False
    assert body["review"]["fresh_for_review"] is True
    assert body["review"]["trend_review_complete"] is False


def test_preview_rejects_naive_now_timestamp():
    app = FastAPI()
    app.include_router(create_enterprise_router())
    response = TestClient(app).post(
        "/v1/enterprise/freshness/preview",
        json={
            "now_utc": "2026-09-20T12:00:00",
            "controls": [{
                "control_key": "tenant_row_isolation",
                "family": "data_isolation",
                "tenant_key": "tenant-1",
                "status": "pass",
                "evidence_refs": ["rls:test"],
                "observed_at": "2026-09-20T11:30:00+00:00",
                "source": "control_probe",
            }],
            "slos": [{
                "service_key": "public-gateway",
                "metric": "availability",
                "target": 0.99,
                "observed": 0.995,
                "window": "30d",
                "observed_at": "2026-09-20T11:00:00+00:00",
                "source": "slo_probe",
            }],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "now_utc must include timezone"
