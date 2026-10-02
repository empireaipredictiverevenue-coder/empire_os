from __future__ import annotations

import json
from pathlib import Path

from empire_os.revenue_completion_supervisor import buyer_status, tam_status


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_tam_status_reports_completed_job(tmp_path):
    runtime = tmp_path / "coder"
    _write(runtime / "jobs/completed/job.json", {
        "id": "job-1",
        "task_id": "task-1",
        "attempts": 1,
        "status": "COMPLETED",
    })
    result = tam_status(runtime)
    assert result["state"] == "COMPLETED"
    assert result["job_id"] == "job-1"
    assert result["task_id"] == "task-1"


def test_buyer_status_surfaces_only_genuine_review_ready(tmp_path):
    deferred = tmp_path / "deferred.json"
    materializer = tmp_path / "materializer.json"
    _write(deferred, {
        "p1": {
            "status": "pending",
            "reason": "no_bound_contact",
            "priority_score": 95,
            "attempts": 2,
            "target_people": [{"name": "A", "title": "Founder"}],
        },
        "p2": {
            "status": "deferred",
            "reason": "site_timeout",
            "priority_score": 95,
            "attempts": 12,
        },
    })
    _write(materializer, {
        "eligible": 2,
        "deferred_enrichment": 1,
        "outcomes": [
            {
                "prospect_id": "p1",
                "decision_name": "A",
                "decision_title": "Founder",
                "preferred_email": "a@example.com",
                "review_ready": True,
                "outreach_ready": True,
            },
            {
                "prospect_id": "p2",
                "decision_name": "B",
                "preferred_email": None,
                "review_ready": True,
                "outreach_ready": False,
            },
        ],
    })
    result = buyer_status(deferred, materializer)
    assert result["evidence_rich_high_priority"] == 1
    assert result["retry_saturated"] == 1
    assert result["genuine_review_ready_count"] == 1
    assert result["genuine_review_ready"][0]["prospect_id"] == "p1"


def test_supervisor_systemd_is_observe_only():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-revenue-completion-supervisor.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-revenue-completion-supervisor.timer"
    ).read_text()
    assert "run_revenue_completion_supervisor.py" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=2min" in timer


def test_tam_coder_timer_is_plan_only_and_bounded():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "deploy/systemd/empire-tam-coder-plan.service"
    ).read_text()
    timer = (
        root / "deploy/systemd/empire-tam-coder-plan.timer"
    ).read_text()
    assert "scripts/empire_coder_worker.py" in service
    assert "runtime/coder_tam_lane" in service
    assert "--max-attempts 3" in service
    assert "ReadWritePaths=/srv/empire_os/runtime" in service
    assert "OnUnitActiveSec=5min" in timer
