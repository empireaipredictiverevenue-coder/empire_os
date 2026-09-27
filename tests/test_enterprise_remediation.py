from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.enterprise_api import create_enterprise_router
from empire_os.enterprise_controls import ControlEvidence, SloObservation
from empire_os.enterprise_freshness import review_enterprise_evidence
from empire_os.enterprise_remediation import review_enterprise_remediation


NOW = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)


def control(status="fail", observed_at="2026-09-20T15:00:00+00:00"):
    return ControlEvidence(
        control_key="backup_restore_test",
        family="backup_dr",
        tenant_key="tenant-1",
        status=status,
        evidence_refs=("backup:test:1",),
        observed_at=observed_at,
        source="control_probe",
    )


def slo(observed=0.98, observed_at="2026-09-20T15:00:00+00:00"):
    return SloObservation(
        service_key="public-api",
        metric="availability",
        target=0.99,
        observed=observed,
        window="30m",
        observed_at=observed_at,
        source="slo_probe",
    )


def freshness(controls, slos):
    return review_enterprise_evidence(
        controls=controls,
        slos=slos,
        now=NOW,
    )


def test_failures_and_breaches_become_operator_review_items_only():
    controls = (control(),)
    slos = (slo(),)
    review = review_enterprise_remediation(
        controls=controls,
        slos=slos,
        freshness=freshness(controls, slos),
    )
    assert review.remediation_review_required is True
    assert review.operator_queue_ready is True
    assert [item.kind for item in review.items] == ["control", "slo"]
    assert review.execution_authority == "none"
    assert review.infrastructure_mutation is False
    assert review.backup_mutation is False
    assert review.compliance_mutation is False
    assert review.deployment_execution is False


def test_all_passing_evidence_produces_no_remediation_queue():
    controls = (control(status="pass"),)
    slos = (slo(observed=0.999),)
    review = review_enterprise_remediation(
        controls=controls,
        slos=slos,
        freshness=freshness(controls, slos),
    )
    assert review.remediation_review_required is False
    assert review.operator_queue_ready is False
    assert review.items == ()


def test_unknown_evidence_remains_explicit():
    controls = (control(status="unknown"),)
    slos = (slo(observed=None),)
    review = review_enterprise_remediation(
        controls=controls,
        slos=slos,
        freshness=freshness(controls, slos),
    )
    states = {item.state for item in review.items}
    assert "unknown" in states
    assert review.remediation_review_required is True


def test_stale_evidence_blocks_operator_queue_without_erasing_exception():
    controls = (control(observed_at="2026-09-10T15:00:00+00:00"),)
    slos = (slo(observed_at="2026-09-10T15:00:00+00:00"),)
    review = review_enterprise_remediation(
        controls=controls,
        slos=slos,
        freshness=freshness(controls, slos),
    )
    assert review.remediation_review_required is True
    assert review.operator_queue_ready is False
    assert review.blockers


def test_api_remediation_preview_never_mutates_enterprise_state():
    app = FastAPI()
    app.include_router(create_enterprise_router())
    response = TestClient(app).post(
        "/v1/enterprise/remediation/preview",
        json={
            "now_utc": "2026-09-20T16:00:00+00:00",
            "controls": [{
                "control_key": "backup_restore_test",
                "family": "backup_dr",
                "tenant_key": "tenant-1",
                "status": "fail",
                "evidence_refs": ["backup:test:1"],
                "observed_at": "2026-09-20T15:00:00+00:00",
                "source": "control_probe",
            }],
            "slos": [{
                "service_key": "public-api",
                "metric": "availability",
                "target": 0.99,
                "observed": 0.98,
                "window": "30m",
                "observed_at": "2026-09-20T15:00:00+00:00",
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
    assert body["backup_mutation"] is False
    assert body["compliance_mutation"] is False
    assert body["deployment_execution"] is False
    assert body["review"]["operator_queue_ready"] is True
