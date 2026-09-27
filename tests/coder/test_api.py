from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.coder.api import router


def make_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BLUEPRINT_V6.md").write_text(
        "# Blueprint\nEmpire Coder remains OBSERVE.\n"
    )
    (tmp_path / "empire_os").mkdir()
    return tmp_path


def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def configure(monkeypatch, root, *, enabled="1", token="internal-test-token"):
    monkeypatch.setenv("EMPIRE_CODER_API_ENABLED", enabled)
    monkeypatch.setenv("EMPIRE_CODER_API_INTERNAL_TOKEN", token)
    monkeypatch.setenv("EMPIRE_CODER_WORKSPACE", str(root))
    monkeypatch.setenv(
        "EMPIRE_CODER_RUNTIME_ROOT",
        str(root / "runtime" / "coder"),
    )


def headers(token="internal-test-token"):
    return {"X-Empire-Coder-Token": token}


def test_health_is_safe_and_api_defaults_disabled(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    configure(monkeypatch, root, enabled="0")
    c = client()

    response = c.get("/v1/coder/health")
    assert response.status_code == 200
    body = response.json()
    assert body["api_enabled"] is False
    assert body["execution_mode"] == "OBSERVE"
    assert body["production_authority"] is False
    assert body["command_execution_endpoint"] is False
    assert body["patch_execution_endpoint"] is False

    denied = c.post(
        "/v1/coder/tasks",
        json={"objective": "Inspect this safely"},
        headers=headers(),
    )
    assert denied.status_code == 503


def test_internal_auth_is_required(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    configure(monkeypatch, root)
    c = client()

    missing = c.post(
        "/v1/coder/tasks",
        json={"objective": "Inspect this safely"},
    )
    assert missing.status_code == 401

    wrong = c.post(
        "/v1/coder/tasks",
        json={"objective": "Inspect this safely"},
        headers=headers("wrong-token"),
    )
    assert wrong.status_code == 401


def test_authorized_task_queue_and_memory_flow(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    configure(monkeypatch, root)
    c = client()

    created = c.post(
        "/v1/coder/tasks",
        json={"objective": "Improve repository retrieval safely"},
        headers=headers(),
    )
    assert created.status_code == 200
    task_id = created.json()["task_id"]
    assert created.json()["production_authority"] is False

    status = c.get(
        f"/v1/coder/tasks/{task_id}",
        headers=headers(),
    )
    assert status.status_code == 200
    assert status.json()["objective"] == "Improve repository retrieval safely"

    memory = c.get(
        f"/v1/coder/tasks/{task_id}/memory",
        headers=headers(),
    )
    assert memory.status_code == 200
    assert memory.json()["task"]["objective"] == "Improve repository retrieval safely"

    queued = c.post(
        f"/v1/coder/tasks/{task_id}/plan",
        json={
            "terms": ["retrieval"],
            "symbols": ["RepoIntelligence"],
            "budget_chars": 8000,
        },
        headers=headers(),
    )
    assert queued.status_code == 200
    job = queued.json()
    assert job["status"] == "PENDING"
    assert job["executed"] is False

    fetched = c.get(
        f"/v1/coder/jobs/{job['job_id']}",
        headers=headers(),
    )
    assert fetched.status_code == 200
    assert fetched.json()["kind"] == "PLAN"


def test_blueprint_must_stay_under_docs(tmp_path, monkeypatch):
    root = make_repo(tmp_path)
    configure(monkeypatch, root)
    c = client()

    response = c.post(
        "/v1/coder/tasks",
        json={
            "objective": "Inspect safely",
            "blueprint_path": "../outside.md",
        },
        headers=headers(),
    )
    assert response.status_code == 400


def test_router_has_no_remote_execution_or_patch_surface():
    paths = {route.path for route in router.routes}
    forbidden_fragments = (
        "/run",
        "/execute",
        "/patch",
        "/commit",
        "/deploy",
        "/merge",
    )
    assert not any(
        fragment in path
        for path in paths
        for fragment in forbidden_fragments
    )
