"""Durable bounded queue for governed Empire Revenue Actors."""
from __future__ import annotations

import fcntl
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.revenue_actor import fingerprint
from empire_os.revenue_actor_registry import run_registered_actor


ROOT = Path("runtime/revenue_actors")
QUEUE = ROOT / "queue.json"
LOCK = ROOT / "queue.lock"

SCHEMA_VERSION = "empire.revenue_actor_queue.v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schema_version": SCHEMA_VERSION,
            "jobs": {},
        }

    if not isinstance(value, dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "jobs": {},
        }

    jobs = value.get("jobs")
    if not isinstance(jobs, dict):
        jobs = {}

    return {
        "schema_version": SCHEMA_VERSION,
        "jobs": jobs,
    }


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        ) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def enqueue_actor_job(
    actor_key: str,
    payload: Mapping[str, Any],
    *,
    source_ref: str,
    queue: Path = QUEUE,
    lock: Path = LOCK,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or _now()).astimezone(timezone.utc)

    actor = str(actor_key or "").strip()
    source = str(source_ref or "").strip()

    if not actor:
        raise ValueError("actor_key required")
    if not source:
        raise ValueError("source_ref required")

    input_fp = fingerprint(dict(payload))
    job_id = fingerprint({
        "actor_key": actor,
        "source_ref": source,
        "input_fingerprint": input_fp,
    })

    queue.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)

    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            state = _load(queue)
            jobs = state["jobs"]

            existing = jobs.get(job_id)
            if isinstance(existing, dict):
                return {
                    "job_id": job_id,
                    "created": False,
                    "status": existing.get("status"),
                }

            jobs[job_id] = {
                "job_id": job_id,
                "actor_key": actor,
                "source_ref": source,
                "input_fingerprint": input_fp,
                "payload": dict(payload),
                "status": "pending",
                "attempts": 0,
                "created_at": current.isoformat(),
                "updated_at": current.isoformat(),
                "lease_until": None,
                "completed_at": None,
                "result": None,
                "error": None,
                "execution_authority": "none",
            }

            _write(queue, state)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return {
        "job_id": job_id,
        "created": True,
        "status": "pending",
    }


def process_actor_queue(
    *,
    limit: int = 10,
    queue: Path = QUEUE,
    lock: Path = LOCK,
    now: datetime | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > 50:
        raise ValueError("actor queue limit must be 1-50")

    current = (now or _now()).astimezone(timezone.utc)

    queue.parent.mkdir(parents=True, exist_ok=True)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)

    claimed: list[tuple[str, dict[str, Any]]] = []

    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            state = _load(queue)
            jobs = state["jobs"]

            eligible: list[tuple[str, dict[str, Any]]] = []

            for job_id, row in jobs.items():
                if not isinstance(row, dict):
                    continue

                status = str(row.get("status") or "")

                if status == "pending":
                    eligible.append((job_id, row))
                    continue

                if status == "running":
                    lease = _parse_time(row.get("lease_until"))
                    if lease is not None and lease <= current:
                        eligible.append((job_id, row))

            eligible.sort(
                key=lambda item: str(
                    item[1].get("created_at") or ""
                )
            )

            for job_id, row in eligible[:limit]:
                row["status"] = "running"
                row["attempts"] = int(
                    row.get("attempts") or 0
                ) + 1
                row["updated_at"] = current.isoformat()
                row["lease_until"] = (
                    current + timedelta(minutes=15)
                ).isoformat()

                claimed.append(
                    (job_id, dict(row))
                )

            _write(queue, state)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    updates: dict[str, dict[str, Any]] = {}
    completed = 0
    failed = 0

    for job_id, row in claimed:
        actor_key = str(row.get("actor_key") or "")
        payload = row.get("payload")

        if not isinstance(payload, Mapping):
            failed += 1
            updates[job_id] = {
                "status": "failed",
                "error": "invalid_actor_payload",
                "lease_until": None,
                "updated_at": current.isoformat(),
            }
            continue

        try:
            result = run_registered_actor(
                actor_key,
                payload,
            )
        except Exception as exc:
            failed += 1
            updates[job_id] = {
                "status": "failed",
                "error": (
                    f"actor_failed:{type(exc).__name__}"
                ),
                "lease_until": None,
                "updated_at": current.isoformat(),
            }
            continue

        governance = result.get("governance")
        if (
            not isinstance(governance, Mapping)
            or governance.get("execution_authority")
            != "none"
            or governance.get("outreach_authorized")
            is not False
        ):
            failed += 1
            updates[job_id] = {
                "status": "failed",
                "error": "actor_governance_violation",
                "lease_until": None,
                "updated_at": current.isoformat(),
            }
            continue

        completed += 1
        updates[job_id] = {
            "status": "completed",
            "result": result,
            "error": None,
            "lease_until": None,
            "completed_at": current.isoformat(),
            "updated_at": current.isoformat(),
        }

    if updates:
        with lock.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                state = _load(queue)
                jobs = state["jobs"]

                for job_id, update in updates.items():
                    row = jobs.get(job_id)
                    if isinstance(row, dict):
                        row.update(update)

                _write(queue, state)
            finally:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_UN,
                )

    return {
        "schema_version":
            "empire.revenue_actor_queue_run.v1",
        "mode": "OBSERVE",
        "claimed": len(claimed),
        "completed": completed,
        "failed": failed,
        "outbound_sent": False,
        "canonical_promotion_performed": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def actor_queue_snapshot(
    queue: Path = QUEUE,
) -> dict[str, Any]:
    state = _load(queue)
    jobs = state["jobs"]

    by_status: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    by_decision: dict[str, int] = {}

    for row in jobs.values():
        if not isinstance(row, Mapping):
            continue

        status = str(row.get("status") or "unknown")
        actor = str(
            row.get("actor_key") or "unknown"
        )

        by_status[status] = (
            by_status.get(status, 0) + 1
        )
        by_actor[actor] = (
            by_actor.get(actor, 0) + 1
        )

        result = row.get("result")
        if isinstance(result, Mapping):
            decision = str(
                result.get("decision") or "unknown"
            )
            by_decision[decision] = (
                by_decision.get(decision, 0) + 1
            )

    return {
        "schema_version":
            "empire.revenue_actor_queue_snapshot.v1",
        "job_count": len(jobs),
        "by_status": by_status,
        "by_actor": by_actor,
        "by_decision": by_decision,
        "execution_authority": "none",
    }
