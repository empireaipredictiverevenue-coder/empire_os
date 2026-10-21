"""The existing Cloud timer refreshes actual local optimization inventory."""
from __future__ import annotations

import json
from pathlib import Path
import scripts.run_predictive_cloud_materializer as owner


def test_existing_cloud_runner_refreshes_local_solver_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(owner, "ROOT", tmp_path)
    assert owner.main() == 0
    response = json.loads(capsys.readouterr().out)
    assert response["optimization_fabric"]["status"] == "AVAILABLE"
    assert response["optimization_fabric"]["external_qpu_called"] is False
    assert response["optimization_fabric"]["execution_authority"] == "none"
    path = tmp_path / "runtime/predictive_cloud/optimization_fabric_latest.json"
    record = json.loads(path.read_text())
    assert record["schema_version"] == "empire.optimization.status.v2"
    assert record["mode"] == "OBSERVE"
    assert record["third_party_services"]["execution_allowed"] is False
    assert record["external_qpu_called"] is False
    assert record["automatic_production_routing"] is False
    assert record["execution_authority"] == "none"
    cloud = json.loads((
        tmp_path / "runtime/predictive_cloud/status_latest.json"
    ).read_text())
    item = cloud["components"]["optimization_fabric"]
    assert item["available"] is True
    assert item["freshness"] == "fresh"
    assert cloud["customer_forecast_verified"] is False
    assert cloud["framework_operational"] is False
    assert response["materializer"]["prediction_ready_component_count"] == 0
