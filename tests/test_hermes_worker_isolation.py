from pathlib import Path

import empire_os.hermes_control as hermes


def _job(job_id, allowed_paths):
    return {
        "schema_version": hermes.SCHEMA_VERSION,
        "job_id": job_id,
        "kind": "code_task",
        "authority": "internal_write",
        "base_branch": hermes.DEFAULT_BASE_BRANCH,
        "prompt": "Bounded internal implementation.",
        "allowed_paths": list(allowed_paths),
        "lease_resources": [
            f"path:{path.rstrip('/')}"
            for path in allowed_paths
        ],
        "pytest_targets": [],
        "max_runtime_seconds": 900,
    }


def test_worker_quarantines_invalid_job_and_continues(
    tmp_path,
    monkeypatch,
):
    bad_path = "jobs/inbox/bad.json"
    good_path = "jobs/inbox/good.json"

    monkeypatch.setattr(
        hermes,
        "fetch_control_refs",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        hermes,
        "list_pending_job_paths",
        lambda *args, **kwargs: [bad_path, good_path],
    )

    def read_json(repo_root, path, **kwargs):
        if path == bad_path:
            return _job(
                "bad",
                ("apps/search-command-centre/src/app/founder/",),
            )
        return _job(
            "good",
            ("empire_os/good.py",),
        )

    monkeypatch.setattr(hermes, "read_control_json", read_json)
    monkeypatch.setattr(
        hermes,
        "control_path_exists",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        hermes,
        "process_job",
        lambda *args, **kwargs: {
            "job_id": "good",
            "status": "CANDIDATE_GATE_PASSED",
        },
    )

    result = hermes.run_worker(tmp_path, max_jobs=1)

    assert result["invalid_job_count"] == 1
    assert result["invalid_jobs"][0]["job_path"] == bad_path
    assert "outside worker policy" in result["invalid_jobs"][0]["reason"]
    assert result["processed_count"] == 1
    assert result["processed"][0]["job_id"] == "good"
    assert result["processed"][0]["status"] == "CANDIDATE_GATE_PASSED"
    assert result["execution_authority"] == "none"
