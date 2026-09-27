import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.predictive_cloud_status_api import (
    create_predictive_cloud_status_router,
    read_predictive_cloud_status,
)


def test_missing_snapshot_is_unavailable(tmp_path):
    result = read_predictive_cloud_status(
        tmp_path / "missing.json"
    )
    assert result["available"] is False
    assert result["mode"] == "OBSERVE"
    assert result["execution_authority"] == "none"


def test_api_exposes_snapshot_read_only(tmp_path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({
        "schema_version": "empire.predictive_cloud.status.v1",
        "mode": "OBSERVE",
        "component_count": 2,
        "available_component_count": 2,
        "components": {
            "opportunity_loop": {"available": True},
            "revenue_pulse": {"available": True},
        },
        "execution_authority": "none",
    }))

    app = FastAPI()
    app.include_router(
        create_predictive_cloud_status_router(path)
    )
    client = TestClient(app)
    response = client.get("/v1/predictive-cloud/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["mode"] == "OBSERVE"
    assert body["component_count"] == 2
    assert body["execution_authority"] == "none"
