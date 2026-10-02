import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_execution_ledger_api import create_founder_execution_ledger_router


def client(tmp_path: Path, *, progress=True, registry=True):
    checklist = tmp_path / "checklist.md"
    checklist.write_text("# X\n- [ ] pending\n", encoding="utf-8")
    progress_path = tmp_path / "progress.json"
    registry_path = tmp_path / "registry.json"
    if progress is True:
        progress_path.write_text(json.dumps({"program": "empire_os_full_completion", "current_stage": "IMPLEMENT"}), encoding="utf-8")
    elif progress == "invalid":
        progress_path.write_text("{broken", encoding="utf-8")
    if registry is True:
        registry_path.write_text(json.dumps({"workstream_count": 31, "workstreams": []}), encoding="utf-8")
    elif registry == "invalid":
        registry_path.write_text("[]", encoding="utf-8")
    app = FastAPI()
    app.include_router(create_founder_execution_ledger_router(checklist, progress_path, registry_path))
    return TestClient(app)


def test_completion_program_returns_persisted_progress_and_registry(tmp_path):
    response = client(tmp_path).get("/v1/founder-execution-ledger/completion-program")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["blockers"] == []
    assert body["programme_progress"]["current_stage"] == "IMPLEMENT"
    assert body["capability_registry"]["workstream_count"] == 31
    assert body["read_only"] is True
    assert body["execution_authority"] == "none"


def test_completion_program_missing_artifact_fails_closed(tmp_path):
    response = client(tmp_path, registry=False).get("/v1/founder-execution-ledger/completion-program")
    body = response.json()
    assert body["available"] is False
    assert body["capability_registry"] is None
    assert "capability_registry_missing" in body["blockers"]
    assert body["execution_authority"] == "none"


def test_completion_program_corrupt_artifact_fails_closed(tmp_path):
    response = client(tmp_path, progress="invalid", registry="invalid").get("/v1/founder-execution-ledger/completion-program")
    body = response.json()
    assert body["available"] is False
    assert "completion_progress_invalid" in body["blockers"]
    assert "capability_registry_invalid" in body["blockers"]
    assert body["read_only"] is True
