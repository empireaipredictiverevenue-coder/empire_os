"""Fail-closed promotion of completed advisory PLAN jobs.

Only an explicit promotion_contract may create a VERIFY or IMPLEMENT job.
Narrative plan text, completion registry membership, or historical approvals
never imply mutation authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from .jobs import JobKind, LocalJobQueue


SCHEMA_VERSION = "empire.coder.plan-promotion.v1"
OUTPUT = Path("runtime/coder/plan_promotion_latest.json")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _promotion_key(job_id: str, contract: Mapping[str, Any]) -> str:
    material = json.dumps(
        {
            "job_id": job_id,
            "contract": dict(contract),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(material).hexdigest()


def _existing_promotion(
    queue: LocalJobQueue,
    key: str,
) -> bool:
    for directory in (
        queue.pending,
        queue.running,
        queue.delegated,
        queue.completed,
        queue.failed,
    ):
        for path in directory.glob("*.json"):
            try:
                packet = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            payload = packet.get("payload") or {}
            if payload.get("plan_promotion_key") == key:
                return True
    return False


def _validate_contract(
    contract: Mapping[str, Any],
) -> tuple[JobKind | None, list[str]]:
    blockers: list[str] = []
    kind_raw = _text(contract.get("kind")).upper()
    if kind_raw not in {"VERIFY", "IMPLEMENT"}:
        return None, ["promotion_kind_must_be_VERIFY_or_IMPLEMENT"]
    kind = JobKind(kind_raw)

    if kind is JobKind.VERIFY:
        changed_files = [
            _text(value)
            for value in (contract.get("changed_files") or ())
            if _text(value)
        ]
        tests = [
            _text(value)
            for value in (contract.get("tests") or ())
            if _text(value)
        ]
        if not changed_files:
            blockers.append("changed_files_required")
        if not tests:
            blockers.append("tests_required")
        if any(
            not test.startswith("tests/") or not test.endswith(".py")
            for test in tests
        ):
            blockers.append("tests_must_be_repository_test_files")

    if kind is JobKind.IMPLEMENT:
        authority = _text(contract.get("authority"))
        if authority != "internal_write":
            blockers.append("internal_write_authority_required")
        if not [
            value
            for value in (contract.get("allowed_paths") or ())
            if _text(value)
        ]:
            blockers.append("allowed_paths_required")
        if not [
            value
            for value in (contract.get("lease_resources") or ())
            if _text(value)
        ]:
            blockers.append("lease_resources_required")
        if not _text(contract.get("execution_plane_request_id")):
            blockers.append("execution_plane_request_id_required")
        tests = [
            _text(value)
            for value in (contract.get("required_tests") or ())
            if _text(value)
        ]
        if not tests:
            blockers.append("required_tests_required")
        if any(
            not test.startswith("tests/") or not test.endswith(".py")
            for test in tests
        ):
            blockers.append("required_tests_must_be_repository_test_files")

    return kind, sorted(set(blockers))


def run_plan_promotion_cycle(
    repo_root: str | Path,
    *,
    max_jobs: int = 100,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    queue = LocalJobQueue(root)
    bounded = max(1, min(int(max_jobs), 250))

    promoted: list[dict[str, Any]] = []
    held: list[dict[str, Any]] = []
    scanned = 0

    candidates = []
    for path in queue.completed.glob("*.json"):
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if packet.get("kind") != "PLAN":
            continue
        if (packet.get("result") or {}).get("proposal_persisted") is not True:
            continue
        candidates.append((str(packet.get("updated_at") or ""), packet))

    for _, job in sorted(candidates, reverse=True):
        if scanned >= bounded:
            break
        scanned += 1
        payload = dict(job.get("payload") or {})
        contract = payload.get("promotion_contract")
        if not isinstance(contract, Mapping):
            held.append({
                "plan_job_id": job.get("id"),
                "task_id": job.get("task_id"),
                "status": "AWAITING_EXACT_CONTRACT",
                "reason": "promotion_contract_missing",
                "fastpath_family": (
                    (job.get("result") or {}).get("fastpath_family")
                ),
            })
            continue

        kind, blockers = _validate_contract(contract)
        if kind is None or blockers:
            held.append({
                "plan_job_id": job.get("id"),
                "task_id": job.get("task_id"),
                "status": "HELD_INVALID_CONTRACT",
                "blockers": blockers,
            })
            continue

        key = _promotion_key(str(job.get("id")), contract)
        if _existing_promotion(queue, key):
            continue

        next_payload = {
            "plan_promotion_key": key,
            "source_plan_job_id": job.get("id"),
            "source_plan_task_id": job.get("task_id"),
            "execution_authority": "none",
        }
        for metadata_key in (
            "department_work_id",
            "completion_item_ids",
            "completion_checklist_lines",
            "completion_workstreams",
        ):
            if metadata_key in payload:
                next_payload[metadata_key] = payload[metadata_key]
        if kind is JobKind.VERIFY:
            next_payload.update({
                "changed_files": list(contract.get("changed_files") or ()),
                "tests": list(contract.get("tests") or ()),
            })
        else:
            next_payload.update({
                "execution_plane_request_id": contract.get(
                    "execution_plane_request_id"
                ),
                "allowed_paths": list(contract.get("allowed_paths") or ()),
                "lease_resources": list(
                    contract.get("lease_resources") or ()
                ),
                "required_tests": list(
                    contract.get("required_tests") or ()
                ),
                "terms": list(contract.get("terms") or ()),
            })

        next_job = queue.enqueue(
            task_id=str(job.get("task_id")),
            kind=kind,
            payload=next_payload,
            priority=int(job.get("priority") or 50),
        )
        promoted.append({
            "source_plan_job_id": job.get("id"),
            "promoted_job_id": next_job.id,
            "kind": kind.value,
            "promotion_key": key,
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "scanned_count": scanned,
        "promoted_count": len(promoted),
        "held_count": len(held),
        "promoted": promoted,
        "held": held[:100],
        "narrative_plan_text_grants_authority": False,
        "founder_gate_inferred": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
