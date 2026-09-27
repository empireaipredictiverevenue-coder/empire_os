import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.spatial_physical_api import create_spatial_physical_router


def client(root):
    app = FastAPI()
    app.include_router(create_spatial_physical_router(root))
    return TestClient(app)


def test_status_reports_runtime_truth_without_execution(tmp_path):
    root = tmp_path / "repo"
    strike_dir = root / "runtime" / "revenue_strike"
    strike_dir.mkdir(parents=True)
    (strike_dir / "storm.json").write_text(json.dumps({
        "execution_authority": "none",
        "market": "Dallas-Fort Worth, TX",
        "observed_at": "2026-09-20T22:50:00Z",
        "trigger": {
            "source": "NWS",
            "modeled_multiplier": 2.454,
        },
    }))

    response = client(root).get("/v1/spatial-physical/status")
    assert response.status_code == 200
    body = response.json()
    assert body["physical_observations"] == 1
    assert body["volumetric_observations"] is None
    assert body["execution_allowed"] is False
    assert body["revenue_mutation"] is False


def test_preview_fuses_evidence_and_builds_simulation_only_twin(tmp_path):
    response = client(tmp_path).post(
        "/v1/spatial-physical/preview",
        json={
            "vertical": "roofing",
            "volumetric": {
                "subject_ref": "property:123",
                "source": "lidar",
                "observed_at": "2026-09-21T16:00:00Z",
                "representation": "point_cloud",
                "evidence_refs": ["lidar:123"],
                "confidence": 0.9,
                "evidence_class": "observed",
            },
            "physical": {
                "subject_ref": "property:123",
                "source": "satellite_vision",
                "observed_at": "2026-09-21T16:01:00Z",
                "phenomenon": "roof_condition",
                "evidence_refs": ["satellite:123"],
                "measurements": {"damage_score": 80},
                "units": {"damage_score": "score_0_100"},
                "confidence": 0.8,
                "evidence_class": "model_inference",
            },
            "storm": {
                "niche": "roofing",
                "event_type": "hail",
                "severity": "severe",
                "evidence_confidence": 0.95,
                "territory_match": 1.0,
                "age_hours": 8,
                "evidence_refs": ["nws:123"],
            },
            "digital_twin_scenario_id": "roofing-123-v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["execution_allowed"] is False
    assert body["actual_revenue"] is False
    assert body["fusion"]["modeled_only"] is True
    assert body["fusion"]["combined_priority_boost"] > 0
    twin = body["digital_twin_scenario"]
    assert twin["simulation_only"] is True
    assert twin["capacity_multiplier"] == 1.0
    assert twin["price_multiplier"] == 1.0
    assert body["digital_twin_evidence"]["actual_revenue"] is False


def test_preview_rejects_missing_spatial_and_physical_evidence(tmp_path):
    response = client(tmp_path).post(
        "/v1/spatial-physical/preview",
        json={
            "vertical": "roofing",
            "storm": {
                "niche": "roofing",
                "event_type": "hail",
                "severity": "severe",
                "evidence_confidence": 1.0,
                "territory_match": 1.0,
                "age_hours": 1,
                "evidence_refs": ["nws:123"],
            },
        },
    )
    assert response.status_code == 422
    assert "requires volumetric or physical evidence" in response.json()["detail"]


def test_preview_rejects_subject_identity_mismatch(tmp_path):
    response = client(tmp_path).post(
        "/v1/spatial-physical/preview",
        json={
            "vertical": "property",
            "volumetric": {
                "subject_ref": "property:1",
                "source": "mesh",
                "observed_at": "2026-09-21T16:00:00Z",
                "representation": "mesh",
                "evidence_refs": ["mesh:1"],
            },
            "physical": {
                "subject_ref": "property:2",
                "source": "inspection",
                "observed_at": "2026-09-21T16:00:00Z",
                "phenomenon": "roof_condition",
                "evidence_refs": ["inspection:2"],
            },
        },
    )
    assert response.status_code == 422
    assert "identity mismatch" in response.json()["detail"]
