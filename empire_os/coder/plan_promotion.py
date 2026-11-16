"""Fail-closed promotion of completed advisory PLAN jobs.

Only an explicit promotion_contract may create a VERIFY or IMPLEMENT job.
Narrative plan text, completion registry membership, or historical approvals
never imply mutation authority.
"""
from __future__ import annotations

from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path, PureWindowsPath
import re
from typing import Any, Mapping

from .jobs import JobKind, LocalJobQueue
from .orchestrator import EmpireCoder


SCHEMA_VERSION = "empire.coder.plan-promotion.v1"
OUTPUT = Path("runtime/coder/plan_promotion_latest.json")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_repo_path(value: Any) -> bool:
    path = _text(value)
    return (
        bool(path)
        and not path.startswith("/")
        and not PureWindowsPath(path).drive
        and "\\" not in path
        and ":" not in path
        and all(ord(char) >= 32 and ord(char) != 127 for char in path)
        and all(part not in {"", ".", ".."} for part in path.split("/"))
    )


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


INTAKE_DIRECTORY = Path("runtime/execution_plane/coder_plan_intake")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
ISOLATED_CANDIDATE_MODE = "ISOLATED_CANDIDATE_ONLY"


def _contract_hash(contract: Mapping[str, Any]) -> str:
    return sha256(json.dumps(dict(contract), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _intake_record_path(root: Path, request_id: str) -> Path:
    if not SAFE_REQUEST_ID.fullmatch(request_id):
        raise ValueError("governed_coder_request_id_must_be_safe")
    return root / INTAKE_DIRECTORY / f"{request_id}.json"


def enqueue_authorized_implementation_plan(
    repo_root: str | Path,
    *,
    request_id: str,
    objective: str,
    source_ref: str,
    allowed_paths: tuple[str, ...],
    lease_resources: tuple[str, ...],
    required_tests: tuple[str, ...],
    base_branch: str,
    max_runtime_seconds: int = 900,
    priority: int = 50,
) -> dict[str, Any]:
    """Bind an explicit caller-owned write request to the ORIGINAL Coder plan.

    Requires the governed dispatcher to authenticate its caller. This routine
    cannot derive authority from plan text, completion lists, or model output.
    All IMPLEMENT results are sandbox proposals requiring founder release.
    """
    root = Path(repo_root).resolve()
    request_id = str(request_id).strip()
    if not str(source_ref).strip() or not str(objective).strip():
        raise ValueError("explicit_execution_source_and_objective_required")
    contract = {
        "kind": "IMPLEMENT",
        "authority": "internal_write",
        "execution_mode": ISOLATED_CANDIDATE_MODE,
        "execution_plane_request_id": request_id,
        "allowed_paths": list(allowed_paths),
        "lease_resources": list(lease_resources),
        "required_tests": list(required_tests),
        "base_branch": base_branch,
        "max_runtime_seconds": max(120, min(int(max_runtime_seconds), 1800)),
    }
    kind, blockers = _validate_contract(contract)
    # An execution lease is not authority, but it must collide with any
    # concurrent owner editing the same exact source path. Domain-only leases
    # cannot protect file-level changes.
    if any(
        f"path:{path}" not in contract["lease_resources"]
        for path in contract["allowed_paths"]
    ):
        blockers.append("exact_path_lease_required_for_each_allowed_path")
    if kind is not JobKind.IMPLEMENT or blockers:
        raise ValueError("invalid_governed_implementation_contract:" + ",".join(blockers))
    path = _intake_record_path(root, request_id)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    lock = path.parent / ".intake.lock"
    lock.touch(exist_ok=True)
    os.chmod(lock, 0o600)
    digest = _contract_hash(contract)
    with lock.open("r+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                if (
                    saved.get("contract_sha256") != digest
                    or saved.get("source_ref") != source_ref
                    or saved.get("objective") != objective
                ):
                    raise ValueError("existing_execution_request_scope_conflict")
                return {
                    "status": "EXISTS",
                    "task_id": saved["task_id"],
                    "plan_job_id": saved["plan_job_id"],
                    "request_id": request_id,
                    "authority_inferred": False,
                }
            coder = EmpireCoder(root)
            task = coder.create_task(
                "Plan only: governed Empire Coder implementation intake. "
                "Scope and authority are bound to the original execution-plane "
                f"request {request_id}. Objective: {objective}"
            )
            queue = LocalJobQueue(root)
            job = queue.enqueue(
                task_id=task.id, kind=JobKind.PLAN,
                priority=priority,
                payload={
                    "promotion_contract": contract,
                    "governed_intake_request_id": request_id,
                    "governed_intake_contract_sha256": digest,
                    "governed_intake_source_ref": source_ref,
                    "execution_authority": "none",
                    "terms": ["governed_coder_implementation_intake"],
                },
            )
            record = {
                "schema_version": "empire.coder.authorized-plan-intake.v1",
                "status": "ACCEPTED_SCOPED_REQUEST",
                "request_id": request_id,
                "objective": objective,
                "source_ref": source_ref,
                "contract": contract,
                "contract_sha256": digest,
                "plan_job_id": job.id,
                "task_id": task.id,
                "founder_release_required": True,
                "code_mutation_in_producer": False,
                "execution_authority": "none",
            }
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.chmod(tmp, 0o600)
            tmp.replace(path)
            coder._record_and_sync(
                task_id=task.id, event="governed_implementation_plan_intake",
                data={
                    "request_id": request_id, "source_ref": source_ref,
                    "contract_sha256": digest,
                    "allowed_paths": list(allowed_paths),
                    "required_tests": list(required_tests),
                    "founder_release_required": True,
                },
            )
            return {
                "status": "QUEUED",
                "request_id": request_id,
                "task_id": task.id,
                "plan_job_id": job.id,
                "authority_inferred": False,
                "founder_release_required": True,
            }
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_governed_intake(
    root: Path,
    plan_job: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> bool:
    payload = plan_job.get("payload") or {}
    request_id = str(payload.get("governed_intake_request_id") or "")
    if not SAFE_REQUEST_ID.fullmatch(request_id):
        return False
    if str(contract.get("execution_plane_request_id") or "") != request_id:
        return False
    if contract.get("execution_mode") != ISOLATED_CANDIDATE_MODE:
        return False
    path = _intake_record_path(root, request_id)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (
        stored.get("schema_version") == "empire.coder.authorized-plan-intake.v1"
        and stored.get("status") == "ACCEPTED_SCOPED_REQUEST"
        and stored.get("plan_job_id") == plan_job.get("id")
        and stored.get("task_id") == plan_job.get("task_id")
        and stored.get("source_ref") == payload.get("governed_intake_source_ref")
        and stored.get("contract") == dict(contract)
        and stored.get("contract_sha256") == _contract_hash(contract)
        and payload.get("governed_intake_contract_sha256") == _contract_hash(contract)
    )


def _existing_promotion_keys(queue: LocalJobQueue) -> set[str]:
    """Index existing promotions ONCE per cycle, not once per PLAN.

    The live Coder queue contains tens of thousands of VERIFY jobs. Reopening
    them for each candidate made the 15-second owner cycle take 55 seconds.
    """
    keys: set[str] = set()
    for directory in (
        queue.pending, queue.running, queue.delegated,
        queue.awaiting_approval, queue.completed, queue.failed,
    ):
        for path in directory.glob("*.json"):
            try:
                raw = path.read_text(encoding="utf-8")
                if '"plan_promotion_key"' not in raw:
                    continue
                packet = json.loads(raw)
            except (OSError, json.JSONDecodeError):
                continue
            payload = packet.get("payload") or {}
            key = payload.get("plan_promotion_key")
            if isinstance(key, str) and key:
                keys.add(key)
    return keys

def _validate_contract(
    contract: Mapping[str, Any],
) -> tuple[JobKind | None, list[str]]:
    blockers: list[str] = []
    kind_raw = _text(contract.get("kind")).upper()
    if kind_raw not in {"VERIFY", "IMPLEMENT"}:
        return None, ["promotion_kind_must_be_VERIFY_or_IMPLEMENT"]
    kind = JobKind(kind_raw)

    path_fields = (
        ("changed_files", "tests")
        if kind is JobKind.VERIFY
        else ("allowed_paths", "required_tests")
    )
    for field in path_fields:
        if any(not _safe_repo_path(value) for value in (contract.get(field) or ())):
            blockers.append(f"{field}_must_be_safe_repository_paths")
    if kind is JobKind.IMPLEMENT:
        for resource in (contract.get("lease_resources") or ()):
            resource = _text(resource)
            if resource.startswith("path:") and not _safe_repo_path(resource[5:]):
                blockers.append("lease_resources_must_be_safe_repository_paths")

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
        if contract.get("execution_mode") != ISOLATED_CANDIDATE_MODE:
            blockers.append("isolated_candidate_mode_required")
        if _text(contract.get("base_branch")) not in {
            "agent/data-cloud-wave4", "feature/revenue-intelligence-v2",
        }:
            blockers.append("governed_base_branch_required")
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

    promoted_keys = (
        _existing_promotion_keys(queue)
        if any(
            isinstance((packet.get("payload") or {}).get("promotion_contract"), Mapping)
            for _, packet in candidates
        )
        else set()
    )

    def promotion_priority(row: tuple[str, dict[str, Any]]) -> tuple[int, str]:
        timestamp, job = row
        payload = job.get("payload") or {}
        contract = payload.get("promotion_contract")
        if isinstance(contract, Mapping):
            if (
                _text(contract.get("kind")).upper() == "IMPLEMENT"
                and _validate_governed_intake(root, job, contract)
            ):
                return (2, timestamp)
            return (1, timestamp)
        return (0, timestamp)

    # A genuine completed, scoped request must not be buried beneath 160
    # more recent advisory-only plans, which cannot grant write authority.
    for _, job in sorted(candidates, key=promotion_priority, reverse=True):
        payload = dict(job.get("payload") or {})
        contract = payload.get("promotion_contract")
        # Already-promoted plans do not occupy the bounded scan budget.
        if (
            isinstance(contract, Mapping)
            and _promotion_key(str(job.get("id")), contract) in promoted_keys
        ):
            continue
        if scanned >= bounded:
            break
        scanned += 1
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

        if kind is JobKind.IMPLEMENT and not _validate_governed_intake(
            root, job, contract,
        ):
            held.append({
                "plan_job_id": job.get("id"),
                "task_id": job.get("task_id"),
                "status": "HELD_NO_GOVERNED_IMPLEMENTATION_INTAKE",
                "reason": "exact_execution_plane_request_binding_required",
            })
            continue

        key = _promotion_key(str(job.get("id")), contract)
        if key in promoted_keys:
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
                "execution_mode": ISOLATED_CANDIDATE_MODE,
                "founder_release_required": True,
                "source_ref": payload.get("governed_intake_source_ref"),
                "base_branch": contract.get("base_branch"),
                "max_runtime_seconds": contract.get("max_runtime_seconds"),
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
        promoted_keys.add(key)
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
