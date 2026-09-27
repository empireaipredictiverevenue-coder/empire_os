from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.capital_api import create_capital_router
from empire_os.capital_calibration_registry import CapitalCalibrationRecord


class FakeCalibrationRegistry:
    def __init__(self):
        self.rows = {}

    def record_calibration(self, item: CapitalCalibrationRecord):
        item.validate()
        key = item.calibration.candidate_id
        if key in self.rows:
            return {
                "status": "existing",
                "calibration_id": self.rows[key]["calibration_id"],
            }
        row = {
            "calibration_id": f"calibration-{len(self.rows) + 1}",
            "candidate_id": key,
            "calibration_available": item.calibration.calibration_available,
            "return_multiple_error": item.calibration.return_multiple_error,
        }
        self.rows[key] = row
        return {"status": "recorded", **row}

    def list_calibrations(self, *, limit):
        return list(self.rows.values())[:limit]


def client(registry=None):
    app = FastAPI()
    app.include_router(
        create_capital_router(calibration_registry=registry)
    )
    return TestClient(app)


def body(**overrides):
    payload = {
        "candidate_id": "candidate-1",
        "expected_return_cents": 30000,
        "required_capital_cents": 10000,
        "recognized_revenue_cents": 26000,
        "observed_cost_cents": 6000,
        "observed_at": "2026-09-20T11:00:00+00:00",
        "evidence_refs": ["revenue:recognized:1", "cost:observed:1"],
        "recommendation_recorded_at": "2026-09-19T12:00:00+00:00",
        "now_utc": "2026-09-20T12:00:00+00:00",
        "max_age_seconds": 604800,
        "evidence": {"source": "canonical_capital_outcome"},
    }
    payload.update(overrides)
    return payload


def test_unbound_calibration_registry_fails_closed():
    response = client().post(
        "/v1/capital/outcome/calibration/register",
        json=body(),
    )
    assert response.status_code == 503


def test_available_calibration_registers_without_mutation():
    response = client(FakeCalibrationRegistry()).post(
        "/v1/capital/outcome/calibration/register",
        json=body(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recorded"
    assert data["mode"] == "OBSERVE"
    assert data["recommendation_only"] is True
    assert data["execution_authority"] == "none"
    assert data["funds_movement"] is False
    assert data["budget_mutation"] is False
    assert data["recommendation_mutation"] is False
    assert data["model_weight_mutation"] is False
    assert data["calibration_record"]["eligible_for_model_review"] is True
    assert (
        data["calibration_record"]["calibration"]["return_multiple_error"]
        == -1.0
    )


def test_blocked_calibration_can_be_retained_for_audit():
    response = client(FakeCalibrationRegistry()).post(
        "/v1/capital/outcome/calibration/register",
        json=body(recognized_revenue_cents=None),
    )
    assert response.status_code == 200
    record = response.json()["calibration_record"]
    assert record["eligible_for_model_review"] is False
    assert "recognized_revenue_or_cost_evidence_missing" in (
        record["calibration"]["blockers"]
    )


def test_calibration_registry_is_idempotent_and_history_read_only():
    repo = FakeCalibrationRegistry()
    c = client(repo)
    first = c.post(
        "/v1/capital/outcome/calibration/register",
        json=body(),
    )
    second = c.post(
        "/v1/capital/outcome/calibration/register",
        json=body(),
    )
    history = c.get("/v1/capital/outcome/calibrations")
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"
    assert second.json()["status"] == "existing"
    assert history.status_code == 200
    payload = history.json()
    assert payload["read_only"] is True
    assert payload["recommendation_only"] is True
    assert payload["execution_authority"] == "none"
    assert payload["funds_movement"] is False
    assert payload["budget_mutation"] is False
    assert payload["recommendation_mutation"] is False
    assert payload["model_weight_mutation"] is False
    assert payload["count"] == 1


def test_registry_requires_provenance_evidence():
    response = client(FakeCalibrationRegistry()).post(
        "/v1/capital/outcome/calibration/register",
        json=body(evidence={}),
    )
    assert response.status_code == 422
    assert "requires evidence" in response.json()["detail"]
