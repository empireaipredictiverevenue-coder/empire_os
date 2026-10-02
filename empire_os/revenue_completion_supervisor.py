"""Observe-only supervisor for TAM planning and buyer evidence progression."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping


ROOT = Path("/srv/empire_os")
DEFAULT_TAM_RUNTIME = ROOT / "runtime/coder_tam_lane"
DEFAULT_DEFERRED = ROOT / "runtime/hunter/buyer_deferred_enrichment.json"
DEFAULT_MATERIALIZER = ROOT / "runtime/buyer_review_materializer/latest.json"
DEFAULT_OUTPUT = ROOT / "runtime/revenue_completion_supervisor/latest.json"
DEFAULT_TAM_SNAPSHOT = ROOT / "runtime/tam_market_intelligence/latest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _job_rows(runtime_root: Path, state: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    folder = runtime_root / "jobs" / state
    for path in sorted(folder.glob("*.json")) if folder.exists() else ():
        value = _read_json(path)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def tam_status(runtime_root: Path = DEFAULT_TAM_RUNTIME) -> dict[str, Any]:
    completed = _job_rows(runtime_root, "completed")
    failed = _job_rows(runtime_root, "failed")
    running = _job_rows(runtime_root, "running")
    pending = _job_rows(runtime_root, "pending")

    state = "NOT_QUEUED"
    job: Mapping[str, Any] | None = None
    if completed:
        state, job = "COMPLETED", completed[-1]
    elif failed:
        state, job = "FAILED", failed[-1]
    elif running:
        state, job = "RUNNING", running[-1]
    elif pending:
        state, job = "PENDING", pending[-1]

    worker_alive = None
    if state == "RUNNING" and job is not None:
        worker_id = str(job.get("worker_id") or "")
        if worker_id.startswith("pid:"):
            try:
                pid = int(worker_id.split(":", 1)[1])
                os.kill(pid, 0)
                worker_alive = True
            except (ValueError, ProcessLookupError, PermissionError):
                worker_alive = False

    return {
        "state": state,
        "job_id": job.get("id") if job else None,
        "task_id": job.get("task_id") if job else None,
        "attempts": int(job.get("attempts") or 0) if job else 0,
        "worker_alive": worker_alive,
        "error": job.get("error") if job else None,
    }


def _genuine_review_rows(materializer: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in materializer.get("outcomes") or []:
        if not isinstance(raw, Mapping):
            continue
        decision_name = str(raw.get("decision_name") or "").strip()
        preferred_email = str(raw.get("preferred_email") or "").strip()
        if (
            raw.get("review_ready") is True
            and raw.get("outreach_ready") is True
            and decision_name
            and preferred_email
        ):
            rows.append(dict(raw))
    return rows


def buyer_status(
    deferred_path: Path = DEFAULT_DEFERRED,
    materializer_path: Path = DEFAULT_MATERIALIZER,
) -> dict[str, Any]:
    deferred = _read_json(deferred_path)
    materializer = _read_json(materializer_path)
    deferred = deferred if isinstance(deferred, dict) else {}
    materializer = materializer if isinstance(materializer, dict) else {}

    rows = [row for row in deferred.values() if isinstance(row, Mapping)]
    reasons = Counter(str(row.get("reason") or "unknown") for row in rows)
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)

    evidence_rich = 0
    saturated = 0
    for row in rows:
        target_people = [
            x for x in (row.get("target_people") or [])
            if isinstance(x, Mapping)
            and str(x.get("name") or "").strip()
            and str(x.get("title") or "").strip()
        ]
        verified_routes = [
            x for x in (row.get("company_contact_routes") or [])
            if isinstance(x, Mapping)
            and x.get("verified") is True
            and str(x.get("value") or "").strip()
        ]
        if int(row.get("priority_score") or 0) >= 90 and (
            target_people or verified_routes
        ):
            evidence_rich += 1
        if int(row.get("attempts") or 0) >= 8:
            saturated += 1

    genuine = _genuine_review_rows(materializer)
    return {
        "deferred_total": len(rows),
        "status_counts": dict(sorted(statuses.items())),
        "reason_counts": dict(reasons.most_common()),
        "evidence_rich_high_priority": evidence_rich,
        "retry_saturated": saturated,
        "materializer_eligible": int(materializer.get("eligible") or 0),
        "materializer_deferred_enrichment": int(
            materializer.get("deferred_enrichment") or 0
        ),
        "genuine_review_ready_count": len(genuine),
        "genuine_review_ready": genuine[:25],
    }


def build_snapshot() -> dict[str, Any]:
    tam = tam_status()
    tam_runtime = _read_json(DEFAULT_TAM_SNAPSHOT)
    tam_runtime_available = isinstance(tam_runtime, dict)
    buyers = buyer_status()
    if buyers["genuine_review_ready_count"] > 0:
        next_action = "founder_review_genuine_buyers"
    elif buyers["evidence_rich_high_priority"] > 0:
        next_action = "continue_targeted_buyer_enrichment"
    else:
        next_action = "refresh_buyer_scout_research"

    blockers: list[str] = []
    if not tam_runtime_available:
        blockers.append("tam_runtime_evidence_unavailable")
    elif tam["state"] == "FAILED":
        blockers.append("tam_planner_failed_historical")
    if tam["state"] == "RUNNING" and tam["worker_alive"] is False:
        blockers.append("tam_planner_worker_missing")
    if buyers["genuine_review_ready_count"] == 0:
        blockers.append("no_genuine_review_ready_buyer")

    return {
        "schema_version": "empire.revenue-completion-supervisor.v1",
        "observed_at": _now(),
        "mode": "OBSERVE",
        "tam": tam,
        "tam_runtime": {
            "available": tam_runtime_available,
            "schema_version": (
                tam_runtime.get("schema_version")
                if isinstance(tam_runtime, dict)
                else None
            ),
            "opportunity_class_count": (
                len(tam_runtime.get("opportunity_classes") or [])
                if isinstance(tam_runtime, dict)
                else 0
            ),
        },
        "buyers": buyers,
        "next_action": next_action,
        "blockers": blockers,
        "outbound_sent": False,
        "call_execution": False,
        "binding_terms": False,
        "payment_action": False,
        "revenue_recognition": False,
        "execution_authority": "none",
    }


def write_snapshot(
    path: Path = DEFAULT_OUTPUT,
    payload: Mapping[str, Any] | None = None,
) -> Path:
    value = dict(payload or build_snapshot())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
    return path
