import json
from datetime import datetime, timedelta, timezone

import pytest

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
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    body = response.json()
    assert body["available"] is True
    assert body["mode"] == "OBSERVE"
    assert body["component_count"] == 2
    assert body["execution_authority"] == "none"


@pytest.mark.parametrize("payload", ["{}", "[]", "null", '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', "{bad"])
def test_invalid_snapshot_is_unavailable_not_an_api_error(tmp_path, payload):
    path = tmp_path/"status.json"
    path.write_text(payload)
    app = FastAPI()
    app.include_router(create_predictive_cloud_status_router(path))
    response = TestClient(app).get("/v1/predictive-cloud/status")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["customer_forecast_verified"] is False
    assert response.headers["Cache-Control"] == "no-store"


def test_current_snapshot_requires_trustworthy_generation_time(tmp_path):
    path = tmp_path/"status.json"
    now = datetime(2026,11,16,18,tzinfo=timezone.utc)
    payload = {"schema_version":"empire.predictive_cloud.status.v2", "mode":"OBSERVE",
        "execution_authority":"none", "components":{}, "framework_operational":False,
        "commercial_prediction_authorized":False, "customer_forecast_verified":False}
    for clock in [None, "bad", now.replace(tzinfo=None).isoformat(),
            (now-timedelta(hours=1)).isoformat(), (now+timedelta(seconds=1)).isoformat()]:
        path.write_text(json.dumps({**payload,"generated_at":clock}))
        assert read_predictive_cloud_status(path,now=now)["available"] is False
    path.write_text(json.dumps({**payload,"generated_at":now.isoformat()}))
    result = read_predictive_cloud_status(path,now=now)
    assert result["available"] is True
    assert result["framework_operational"] is False
    assert result["commercial_prediction_authorized"] is False


def test_oversized_and_symlink_snapshots_fail_closed(tmp_path):
    from empire_os.predictive_cloud_status_api import MAX_SNAPSHOT_BYTES
    path = tmp_path/"status.json"
    path.write_bytes(b" "*(MAX_SNAPSHOT_BYTES+1))
    assert read_predictive_cloud_status(path)["available"] is False
    alias = tmp_path/"alias.json"
    alias.symlink_to(path)
    assert read_predictive_cloud_status(alias)["snapshot_state"] == "UNTRUSTED_SNAPSHOT_PATH"
