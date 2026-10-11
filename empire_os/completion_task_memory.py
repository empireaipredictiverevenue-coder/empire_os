"""Shared, immutable completion-attempt memory in EmpireOS's existing checkpoints.

This is a preflight guard for *new* completion dispatches, not task completion.
No agent, external service, timer, commercial authority or DB is introduced.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Mapping

from empire_os.master_execution_ledger import parse_checklist


SCHEMA = "empire.completion-task-attempt-memory.v1"
CHECKLIST = Path("docs/MASTER_REMAINING_CHECKLIST.md")
CHECKPOINTS = Path("runtime/execution_plane/completion_checkpoints")
PREFIX = "task_memory_"
MAX_EVENTS = 2048
MAX_BYTES = 32768
STATES = frozenset({
    "CODE_VERIFIED_NOT_LIVE",
    "PROVIDER_CAPACITY_BLOCKED",
    "REVIEW_REQUIRED",
    "RESOLVED_WITH_NEW_EVIDENCE",
})
HOLD_STATES = STATES - {"RESOLVED_WITH_NEW_EVIDENCE"}
PROVIDER_BLOCKERS = frozenset({
    "hermes_zero_cost_model_unavailable",
    "local_structured_patch_no_proposal",
    "local_model_probe_timeout",
})
REF_PREFIXES = (
    "commit:", "pytest:", "feature_branch:", "hermes_result:",
    "runtime:", "model_probe:", "source:", "verification:",
)
REF_BAD = ("password", "secret", "access_token", "api_key", "bearer", "://", "@")


class AttemptMemoryError(ValueError):
    """Invalid memory evidence: fail closed, never silently forget a hold."""


def task_key(section: str, item: str) -> str:
    """Stable across checklist line-number changes, not unrelated task names."""
    if not isinstance(section, str) or not isinstance(item, str):
        raise AttemptMemoryError("task identity must be text")
    section = " ".join(section.split())
    item = " ".join(item.split())
    if not section or not item or len(section) > 300 or len(item) > 600:
        raise AttemptMemoryError("invalid task identity")
    return "task_" + sha256(f"{section}\x00{item}".encode()).hexdigest()[:24]


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 48:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc) if dt.tzinfo else None


def _evidence_refs(raw: Any) -> list[str]:
    if not isinstance(raw, list) or not raw or len(raw) > 12:
        raise AttemptMemoryError("bounded evidence references required")
    refs: list[str] = []
    for ref in raw:
        if not isinstance(ref, str) or len(ref) > 180 or not ref:
            raise AttemptMemoryError("invalid evidence reference")
        if (not ref.startswith(REF_PREFIXES)
                or any(bad in ref.casefold() for bad in REF_BAD)
                or any(ord(c) < 32 for c in ref)):
            raise AttemptMemoryError("unsafe or unsupported evidence reference")
        if ref in refs:
            raise AttemptMemoryError("duplicate evidence reference")
        refs.append(ref)
    return refs


def _identity_payload(
    *,
    section: str,
    item: str,
    attempt_state: str,
    evidence_refs: list[str],
    owner: str,
    commit: str | None,
    blocker: str | None,
    reopens: str | None,
) -> dict[str, Any]:
    if attempt_state not in STATES:
        raise AttemptMemoryError("unknown attempt state")
    if not isinstance(owner, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,55}", owner):
        raise AttemptMemoryError("canonical department owner required")
    key = task_key(section, item)
    refs = _evidence_refs(evidence_refs)
    if attempt_state == "CODE_VERIFIED_NOT_LIVE":
        if (not isinstance(commit, str)
                or re.fullmatch(r"[0-9a-f]{8,40}", commit) is None
                or f"commit:{commit}" not in refs
                or not any(v.startswith("pytest:") for v in refs)
                or not any(v.startswith("feature_branch:") for v in refs)
                or blocker is not None or reopens is not None):
            raise AttemptMemoryError("commit, tests and feature branch required")
    elif attempt_state == "PROVIDER_CAPACITY_BLOCKED":
        if (commit is not None or reopens is not None
                or blocker not in PROVIDER_BLOCKERS
                or not any(v.startswith(("hermes_result:", "model_probe:")) for v in refs)):
            raise AttemptMemoryError("specific failed provider evidence required")
    elif attempt_state == "REVIEW_REQUIRED":
        if commit is not None or reopens is not None or blocker is None:
            raise AttemptMemoryError("review must carry exact blocker")
        if not re.fullmatch(r"[a-z0-9_]{5,90}", str(blocker)):
            raise AttemptMemoryError("invalid review blocker")
    else:
        if (commit is not None or blocker is not None
                or not isinstance(reopens, str)
                or re.fullmatch(r"attempt_[0-9a-f]{24}", reopens) is None
                or not any(ref.startswith(("model_probe:", "verification:", "runtime:")) for ref in refs)):
            raise AttemptMemoryError("explicit fresh resolution evidence required")
    return {
        "task_key": key,
        "section": " ".join(section.split()),
        "item": " ".join(item.split()),
        "attempt_state": attempt_state,
        "evidence_refs": refs,
        "owner": owner,
        "commit": commit,
        "blocker": blocker,
        "reopens": reopens,
    }


def _attempt_id(core: Mapping[str, Any]) -> str:
    material = json.dumps(core, sort_keys=True, separators=(",", ":"))
    return "attempt_" + sha256(material.encode("utf-8")).hexdigest()[:24]


def _validate_receipt(receipt: Any, *, now: datetime) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise AttemptMemoryError("invalid memory event")
    core = _identity_payload(
        section=receipt.get("section"),
        item=receipt.get("item"),
        attempt_state=receipt.get("attempt_state"),
        evidence_refs=receipt.get("evidence_refs"),
        owner=receipt.get("owner"),
        commit=receipt.get("commit"),
        blocker=receipt.get("blocker"),
        reopens=receipt.get("reopens"),
    )
    created = _timestamp(receipt.get("recorded_at"))
    if (receipt.get("schema_version") != SCHEMA
            or receipt.get("scope") != "task_attempt_memory"
            or receipt.get("stage") != "TASK_MEMORY_EVENT"
            or receipt.get("state") != "OBSERVED"
            or receipt.get("read_only") is not True
            or receipt.get("live_verified") is not False
            or receipt.get("execution_authority") != "none"
            or receipt.get("founder_approval_inferred") is not False
            or receipt.get("external_action_performed") is not False
            or created is None
            or created.year < 2026
            or created > now + timedelta(minutes=5)
            or receipt.get("attempt_id") != _attempt_id(core)):
        raise AttemptMemoryError("memory receipt provenance invalid")
    if any(receipt.get(field) != value for field, value in core.items()):
        raise AttemptMemoryError("memory receipt identity mismatch")
    return receipt


def load_attempt_memory(
    repo_root: str | Path, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Read all immutable attempts. Corruption blocks *new* dispatch entirely."""
    root = Path(repo_root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise AttemptMemoryError("timezone-aware clock required")
    current = current.astimezone(timezone.utc)
    files = sorted((root / CHECKPOINTS).glob(PREFIX + "*.json"))
    if len(files) > MAX_EVENTS:
        return {"status": "MEMORY_INVALID_HOLD", "reason": "memory_event_cap_exceeded"}
    events: dict[str, list[dict[str, Any]]] = {}
    seen_attempts: set[str] = set()
    try:
        for path in files:
            if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                raise AttemptMemoryError("memory file is unsafe or oversized")
            receipt = _validate_receipt(
                json.loads(path.read_text(encoding="utf-8")), now=current,
            )
            if (path.name != PREFIX + receipt["attempt_id"] + ".json"
                    or receipt["attempt_id"] in seen_attempts):
                raise AttemptMemoryError("receipt filename/identity mismatch")
            seen_attempts.add(receipt["attempt_id"])
            events.setdefault(receipt["task_key"], []).append(receipt)
        latest: dict[str, dict[str, Any]] = {}
        for key, history in events.items():
            ordered = sorted(history, key=lambda x: (
                x["recorded_at"], x["attempt_id"],
            ))
            previous: dict[str, Any] | None = None
            for receipt in ordered:
                if receipt["attempt_state"] == "RESOLVED_WITH_NEW_EVIDENCE":
                    if (previous is None
                            or previous["attempt_state"] not in HOLD_STATES
                            or receipt["reopens"] != previous["attempt_id"]):
                        raise AttemptMemoryError("unbound or invalid reopening")
                previous = receipt
            latest[key] = previous  # type: ignore[assignment]
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {"status": "MEMORY_INVALID_HOLD", "reason": "corrupt_or_unbound_receipt"}

    return {
        "schema_version": SCHEMA,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "event_count": len(files),
        "known_task_count": len(latest),
        "held_task_count": sum(
            row["attempt_state"] in HOLD_STATES for row in latest.values()
        ),
        "latest_by_task": latest,
        "execution_authority": "none",
        "checklist_mutation_performed": False,
    }


def preflight_task(
    state: Mapping[str, Any], *, section: str, item: str,
) -> dict[str, Any]:
    """Find what to read before any new PLAN/IMPLEMENT assignment."""
    if state.get("status") != "AVAILABLE":
        return {"decision": "HOLD", "reason": "memory_unavailable",
                "execution_authority": "none"}
    key = task_key(section, item)
    latest = (state.get("latest_by_task") or {}).get(key)
    if not isinstance(latest, dict):
        return {"decision": "NEW_EVIDENCE_REQUIRED",
                "reason": "no_cross_task_attempt_record",
                "task_key": key, "execution_authority": "none"}
    held = latest.get("attempt_state") in HOLD_STATES
    return {
        "decision": "HOLD" if held else "REVIEW_NEW_EVIDENCE",
        "reason": latest["attempt_state"],
        "task_key": key,
        "last_attempt_id": latest["attempt_id"],
        "commit": latest.get("commit"),
        "blocker": latest.get("blocker"),
        "evidence_refs": list(latest["evidence_refs"]),
        "execution_authority": "none",
    }


def record_attempt(
    repo_root: str | Path,
    *,
    section: str,
    item: str,
    attempt_state: str,
    evidence_refs: list[str],
    owner: str,
    commit: str | None = None,
    blocker: str | None = None,
    reopens: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Exclusive, idempotent checkpoint; no checklist or worker state mutation."""
    root = Path(repo_root).resolve()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise AttemptMemoryError("timezone-aware clock required")
    current = current.astimezone(timezone.utc)
    matching = [
        row for row in parse_checklist(root / CHECKLIST)
        if row.status == "PENDING"
        and " ".join(row.section.split()) == " ".join(section.split())
        and " ".join(row.item.split()) == " ".join(item.split())
    ]
    if len(matching) != 1:
        raise AttemptMemoryError("exact unique current pending checklist item required")
    core = _identity_payload(
        section=section, item=item, attempt_state=attempt_state,
        evidence_refs=evidence_refs, owner=owner, commit=commit,
        blocker=blocker, reopens=reopens,
    )
    existing = load_attempt_memory(root, now=current)
    if existing["status"] != "AVAILABLE":
        raise AttemptMemoryError("existing attempt memory unsafe")
    previous = (existing["latest_by_task"] or {}).get(core["task_key"])
    if attempt_state == "RESOLVED_WITH_NEW_EVIDENCE":
        if (not previous or previous.get("attempt_id") != reopens
                or previous.get("attempt_state") not in HOLD_STATES):
            raise AttemptMemoryError("resolution must reopen latest held attempt")
    if attempt_state == "CODE_VERIFIED_NOT_LIVE":
        assert commit is not None
        check = subprocess.run(
            ["git", "cat-file", "-t", commit],
            cwd=root, capture_output=True, text=True, timeout=8, check=False,
        )
        if check.returncode != 0 or check.stdout.strip() != "commit":
            raise AttemptMemoryError("source commit not registered in EmpireOS")
    identity = _attempt_id(core)
    packet = {
        "schema_version": SCHEMA,
        "scope": "task_attempt_memory",
        "stage": "TASK_MEMORY_EVENT",
        "state": "OBSERVED",
        "attempt_id": identity,
        "recorded_at": current.isoformat(),
        "checklist_line_at_capture": matching[0].line,
        "checklist_source_sha256": sha256((root / CHECKLIST).read_bytes()).hexdigest(),
        **core,
        "read_only": True,
        "live_verified": False,
        "founder_approval_inferred": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }
    directory = root / CHECKPOINTS
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{PREFIX}{identity}.json"
    payload = (json.dumps(packet, sort_keys=True, indent=2) + "\n").encode()
    if len(payload) > MAX_BYTES:
        raise AttemptMemoryError("memory event exceeds bounded size")
    # Finish an immutable receipt before publishing it. An exclusive link
    # makes duplicate writers idempotent; readers never see partial JSON.
    fd, pending = tempfile.mkstemp(
        prefix=".task_memory_", suffix=".pending", dir=directory,
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(pending, path)
            created = True
        except FileExistsError:
            created = False
            old = _validate_receipt(
                json.loads(path.read_text(encoding="utf-8")), now=current,
            )
            if old["attempt_id"] != identity or any(
                old.get(k) != v for k, v in core.items()
            ):
                raise AttemptMemoryError("conflicting existing immutable attempt")
        dirfd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        Path(pending).unlink(missing_ok=True)
    return {
        "created": created,
        "attempt_id": identity,
        "checkpoint_ref": str(path.relative_to(root)),
        "execution_authority": "none",
    }



def preflight_checklist_source(
    repo_root: str | Path, source_ref: str, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Shared source-ref gate for Hermes/Pi/Empire Coder execution requests.

    Legacy check_ID:line_N references are bound to the exact current checklist
    row; stable task_ID references survive line-number changes by design.
    """
    if not source_ref.startswith("checklist:"):
        return {"decision": "NOT_CHECKLIST_SCOPED", "execution_authority": "none"}
    match = re.fullmatch(
        r"checklist:(check_[0-9a-f]{16}|task_[0-9a-f]{24}):line_(\d{1,6})",
        source_ref,
    )
    if match is None:
        return {"decision": "HOLD", "reason": "invalid_checklist_source_ref",
                "execution_authority": "none"}
    task_id, raw_line = match.groups()
    root = Path(repo_root).resolve()
    try:
        candidates = parse_checklist(root / CHECKLIST)
    except OSError:
        return {"decision": "HOLD", "reason": "checklist_unavailable",
                "execution_authority": "none"}
    line = int(raw_line)
    matches = []
    for row in candidates:
        if row.status != "PENDING":
            continue
        stable = task_key(row.section, row.item)
        legacy = "check_" + sha256(
            f"{row.line}|{row.section}|{row.item}".encode()
        ).hexdigest()[:16]
        if ((task_id == stable)
                or (task_id == legacy and line == row.line)):
            matches.append(row)
    if len(matches) != 1:
        return {"decision": "HOLD", "reason": "stale_or_unbound_checklist_task",
                "execution_authority": "none"}
    memory = load_attempt_memory(root, now=now)
    verdict = preflight_task(
        memory, section=matches[0].section, item=matches[0].item,
    )
    return {
        **verdict,
        "checklist_line_current": matches[0].line,
    }


def preflight_completion_packet(
    repo_root: str | Path,
    intelligence_request: Mapping[str, Any],
    *, now: datetime | None = None,
) -> dict[str, Any]:
    """Recheck old READY completion queue payload before invoking any model.

    Old packet jobs can predate a new hold. Block the whole mixed packet until
    its actionable portion is explicitly rebound rather than execute held text.
    """
    root = Path(repo_root).resolve()
    ids = intelligence_request.get("item_ids")
    lines = intelligence_request.get("checklist_lines")
    if (not isinstance(ids, list) or not isinstance(lines, list)
            or not ids or len(ids) != len(lines) or len(ids) > 40):
        return {"decision": "HOLD", "reason": "stale_completion_packet_contract",
                "execution_authority": "none"}
    # Single canonical-read / memory-read per packet: no N-times replay scans.
    try:
        rows = parse_checklist(root / CHECKLIST)
    except OSError:
        return {"decision": "HOLD", "reason": "checklist_unavailable",
                "execution_authority": "none"}
    memory = load_attempt_memory(root, now=now)
    if memory.get("status") != "AVAILABLE":
        return {"decision": "HOLD", "reason": "memory_unavailable",
                "execution_authority": "none"}
    by_line = {row.line: row for row in rows if row.status == "PENDING"}
    for work_id, line in zip(ids, lines):
        if (not isinstance(work_id, str)
                or not re.fullmatch(r"check_[0-9a-f]{16}", work_id)
                or type(line) is not int):
            return {"decision": "HOLD", "reason": "invalid_completion_packet_item",
                    "execution_authority": "none"}
        row = by_line.get(line)
        expected = (
            "check_" + sha256(
                f"{row.line}|{row.section}|{row.item}".encode()
            ).hexdigest()[:16] if row is not None else None
        )
        if expected != work_id:
            return {"decision": "HOLD",
                    "reason": "prior_attempt_or_stale_checklist",
                    "held_item_id": work_id,
                    "hold_detail": "stale_or_unbound_checklist_task",
                    "execution_authority": "none"}
        result = preflight_task(
            memory, section=row.section, item=row.item,
        )
        if result["decision"] != "NEW_EVIDENCE_REQUIRED":
            return {
                "decision": "HOLD",
                "reason": "prior_attempt_or_stale_checklist",
                "held_item_id": work_id,
                "hold_detail": result["reason"],
                "execution_authority": "none",
            }
    return {"decision": "ALLOW", "checked_item_count": len(ids),
            "execution_authority": "none"}
