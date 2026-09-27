import json
from pathlib import Path

import empire_os.predictive_coding_team_status as status_module
from empire_os.predictive_coding_team_status import (
    build_predictive_coding_team_status,
)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_status_aggregates_all_five_coding_team_lanes(
    tmp_path,
    monkeypatch,
):
    # Pi request
    _write(
        tmp_path
        / "runtime/execution_plane/requests/pi"
        / "predictive-action-portfolio-design-v1.json",
        {
            "queued_at": "2026-09-26T21:15:02+00:00",
            "lane": "pi",
        },
    )

    # Swarm request
    _write(
        tmp_path
        / "runtime/execution_plane/requests/swarm_v6"
        / "predictive-algorithm-integration-qa-v1.json",
        {
            "queued_at": "2026-09-26T21:09:13+00:00",
            "lane": "swarm_v6",
        },
    )

    # Empire Coder verification job
    _write(
        tmp_path
        / "runtime/coder/jobs/pending"
        / "coder_job_verify.json",
        {
            "id": "coder_job_verify",
            "task_id": "coder_task_verify",
            "kind": "PLAN",
            "status": "PENDING",
            "attempts": 0,
            "payload": {
                "execution_plane_request_id": (
                    "predictive-algorithm-verification-hardening-v1"
                )
            },
            "updated_at": "2026-09-26T21:09:12+00:00",
        },
    )

    def fake_hermes(
        repo_root,
        request_id,
        *,
        control_branch,
        remote,
    ):
        return {
            "queue_state": "QUEUED_OR_RUNNING",
            "status": "AWAITING_RESULT",
            "job_path": f"jobs/inbox/{request_id}.json",
        }

    monkeypatch.setattr(
        status_module,
        "_hermes_state",
        fake_hermes,
    )

    payload = build_predictive_coding_team_status(tmp_path)

    assert payload["task_count"] == 5
    assert payload["read_only"] is True
    assert payload["remote_fetch_performed"] is False
    assert payload["worker_started"] is False
    assert payload["merge_performed"] is False
    assert payload["production_deploy"] is False
    assert payload["execution_authority"] == "none"

    by_id = {
        row["request_id"]: row
        for row in payload["tasks"]
    }
    assert by_id[
        "predictive-action-portfolio-design-v1"
    ]["worker"] == "pi"
    assert by_id[
        "predictive-action-portfolio-design-v1"
    ]["state"]["queue_state"] == "QUEUED"

    assert by_id[
        "predictive-action-portfolio-implementation-v2"
    ]["worker"] == "hermes"
    assert by_id[
        "predictive-quantum-exchange-bridge-v1"
    ]["worker"] == "hermes"

    verify = by_id[
        "predictive-algorithm-verification-hardening-v1"
    ]
    assert verify["worker"] == "empire_coder"
    assert verify["state"]["queue_state"] == "PENDING"
    assert verify["state"]["job_id"] == "coder_job_verify"

    swarm = by_id[
        "predictive-algorithm-integration-qa-v1"
    ]
    assert swarm["worker"] == "swarm_v6"
    assert swarm["state"]["queue_state"] == "QUEUED"


def test_status_marks_unobserved_work_as_unknown(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        status_module,
        "_hermes_state",
        lambda *args, **kwargs: {
            "queue_state": "NOT_OBSERVED",
            "status": "UNKNOWN",
        },
    )

    payload = build_predictive_coding_team_status(tmp_path)

    assert payload["task_count"] == 5
    assert payload["blocker_count"] == 5
    assert all(
        row["state"]["queue_state"] == "NOT_OBSERVED"
        for row in payload["tasks"]
    )


def test_status_surfaces_hermes_failure(
    tmp_path,
    monkeypatch,
):
    def fake_hermes(
        repo_root,
        request_id,
        *,
        control_branch,
        remote,
    ):
        if request_id == "predictive-quantum-exchange-bridge-v1":
            return {
                "queue_state": "RESULT_AVAILABLE",
                "status": "VERIFICATION_FAILED",
                "error": "test_failure",
            }
        return {
            "queue_state": "QUEUED_OR_RUNNING",
            "status": "AWAITING_RESULT",
        }

    monkeypatch.setattr(
        status_module,
        "_hermes_state",
        fake_hermes,
    )

    payload = build_predictive_coding_team_status(tmp_path)

    failed = [
        row
        for row in payload["blockers"]
        if row["request_id"]
        == "predictive-quantum-exchange-bridge-v1"
    ]
    assert len(failed) == 1
    assert failed[0]["status"] == "VERIFICATION_FAILED"
    assert failed[0]["reason"] == "test_failure"



def test_status_exposes_coder_backend_readiness(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        status_module,
        "_hermes_state",
        lambda *args, **kwargs: {
            "queue_state": "NOT_OBSERVED",
            "status": "UNKNOWN",
        },
    )
    monkeypatch.setattr(
        status_module,
        "aider_health",
        lambda: {
            "ready": True,
            "reason": "aider_ready",
            "version": "aider test",
            "executable": "/home/ubuntu/.local/bin/aider",
            "execution_authority": "none",
        },
    )
    _write(
        tmp_path
        / "runtime/execution_plane/builder_capabilities.json",
        {
            "schema_version": "empire.builder-capabilities.v1",
            "workers": {
                "empire_coder": {
                    "structured_patch_mutation": {
                        "ready": True,
                    },
                    "aider_mutation": {
                        "ready": True,
                    },
                }
            },
        },
    )

    payload = build_predictive_coding_team_status(tmp_path)
    backends = payload["coder_backends"]

    assert backends["native_structured_patch"]["capability"][
        "ready"
    ] is True
    assert backends["aider"]["health"]["ready"] is True
    assert backends["aider"]["capability"]["ready"] is True
    assert backends["openhands"]["workspace_contract_ready"] is True
    assert backends["openhands"]["mutation_capability_proven"] is False
