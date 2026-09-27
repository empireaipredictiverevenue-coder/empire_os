from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path

from empire_os.founder_execution_plane_api import (
    build_execution_plane_status,
    create_founder_execution_plane_router,
)


def test_founder_execution_plane_is_read_only(tmp_path):
    payload = build_execution_plane_status(
        lease_root=tmp_path / "leases",
    )
    assert payload["architecture_first_required"] is True
    assert payload["read_only"] is True
    assert payload["execution_authority"] == "none"
    assert payload["registry"]["worker_count"] >= 8
    assert payload["active_mutation_lease_count"] == 0



def test_founder_execution_plane_exposes_coding_team_status(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.founder_execution_plane_api."
        "build_predictive_coding_team_status",
        lambda repo_root: {
            "schema_version": "empire.coding_team_status.v1",
            "task_count": 5,
            "read_only": True,
            "execution_authority": "none",
        },
    )
    app = FastAPI()
    app.include_router(
        create_founder_execution_plane_router(
            lease_root=tmp_path / "leases",
            repo_root=tmp_path,
        )
    )
    response = TestClient(app).get(
        "/v1/founder-execution-plane/coding-team/status"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["task_count"] == 5
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"
