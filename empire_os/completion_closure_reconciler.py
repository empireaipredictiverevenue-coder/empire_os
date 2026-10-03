"""Evidence-gated reconciliation from verification to checklist closure.

A passing repository VERIFY is necessary but never sufficient for DONE.
Checklist mutation is permitted only when the exact pending row has:
1. a successful VERIFY result bound to its current checklist line, and
2. an explicit live-closure checkpoint bound to the same current item/line/id.

Everything else remains pending with a machine-readable blocker.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from empire_os.master_execution_ledger import parse_checklist


SCHEMA_VERSION = "empire.completion-closure-reconciliation.v1"
CHECKLIST = Path("docs/MASTER_REMAINING_CHECKLIST.md")
CHECKPOINTS = Path("runtime/execution_plane/completion_checkpoints")
OUTPUT = Path(
    "runtime/execution_plane/completion_closure_reconciliation_latest.json"
)

CLOSURE_STAGES = {
    "LIVE_VERIFY_DONE",
    "LIVE_CLOSEOUT",
    "PRODUCTION_VERIFY_DONE",
}
CLOSURE_STATES = {
    "DONE",
    "VERIFIED_COMPLETE",
    "LIVE_VERIFIED",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _item_id(line: int, section: str, item: str) -> str:
    material = f"{line}|{section}|{item}".encode("utf-8")
    return "check_" + sha256(material).hexdigest()[:16]


def _verify_index(root: Path) -> dict[int, list[dict[str, Any]]]:
    index: dict[int, list[dict[str, Any]]] = {}
    jobs = root / "runtime/coder/jobs"
    for bucket in ("completed", "failed", "running", "pending"):
        directory = jobs / bucket
        for path in directory.glob("*.json"):
            packet = _read_json(path)
            if not packet or packet.get("kind") != "VERIFY":
                continue
            payload = packet.get("payload") or {}
            lines = payload.get("completion_checklist_lines") or ()
            if not isinstance(lines, list):
                continue
            result = packet.get("result") or {}
            verification = result.get("verification") or {}
            verdict = _text(
                verification.get("verdict") or result.get("verdict")
            ).upper()
            row = {
                "job_id": packet.get("id"),
                "bucket": bucket,
                "status": packet.get("status"),
                "verdict": verdict or None,
                "changed_files": list(payload.get("changed_files") or ()),
                "tests": list(payload.get("tests") or ()),
                "source_plan_job_id": payload.get("source_plan_job_id"),
            }
            for raw in lines:
                try:
                    line = int(raw)
                except (TypeError, ValueError):
                    continue
                index.setdefault(line, []).append(row)
    return index


def _checkpoint_bindings(
    root: Path,
) -> tuple[dict[str, list[str]], dict[int, list[str]], dict[str, list[str]]]:
    by_id: dict[str, list[str]] = {}
    by_line: dict[int, list[str]] = {}
    by_item: dict[str, list[str]] = {}

    for path in (root / CHECKPOINTS).glob("*.json"):
        packet = _read_json(path)
        if packet is None:
            continue
        stage = _text(packet.get("stage")).upper()
        state = _text(packet.get("state")).upper()
        explicit_live = (
            stage in CLOSURE_STAGES
            or state in CLOSURE_STATES
            or bool(packet.get("live_verified") is True)
        )
        if not explicit_live:
            continue

        ref = str(path.relative_to(root))
        for value in packet.get("completed_items") or ():
            key = _text(value)
            if key.startswith("check_"):
                by_id.setdefault(key, []).append(ref)

        for value in packet.get("checklist_lines") or ():
            try:
                line = int(value)
            except (TypeError, ValueError):
                continue
            by_line.setdefault(line, []).append(ref)

        for key in ("checklist_items", "items_closed"):
            for value in packet.get(key) or ():
                item = _text(value)
                if item:
                    by_item.setdefault(item, []).append(ref)

    return by_id, by_line, by_item


def _has_verify_pass(rows: list[dict[str, Any]]) -> bool:
    return any(
        row.get("bucket") == "completed"
        and _text(row.get("status")).upper() == "COMPLETED"
        and _text(row.get("verdict")).upper() == "PASS"
        for row in rows
    )


def _has_verify_failure(rows: list[dict[str, Any]]) -> bool:
    return any(
        _text(row.get("verdict")).upper() == "FAIL"
        or row.get("bucket") == "failed"
        for row in rows
    )


def _atomic_replace_checklist(path: Path, lines: list[str]) -> None:
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def reconcile_completion_closure(
    repo_root: str | Path,
    *,
    apply: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    checklist = root / CHECKLIST
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    if not checklist.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "canonical_checklist_missing",
            "execution_authority": "none",
        }

    verify_index = _verify_index(root)
    checkpoints_by_id, checkpoints_by_line, checkpoints_by_item = (
        _checkpoint_bindings(root)
    )
    ledger = parse_checklist(checklist)
    source_lines = checklist.read_text(encoding="utf-8").splitlines()

    rows: list[dict[str, Any]] = []
    close_lines: list[int] = []

    for item in ledger:
        if item.status != "PENDING":
            continue

        cid = _item_id(item.line, item.section, item.item)
        verifies = verify_index.get(item.line, [])
        refs = sorted(set(
            checkpoints_by_id.get(cid, [])
            + checkpoints_by_line.get(item.line, [])
            + checkpoints_by_item.get(item.item, [])
        ))
        verify_pass = _has_verify_pass(verifies)
        verify_failed = _has_verify_failure(verifies)

        if verify_pass and refs:
            state = "VERIFIED_DONE"
            blocker = None
            close_lines.append(item.line)
        elif verify_pass:
            state = "NEEDS_LIVE_PROOF"
            blocker = "exact_live_closure_checkpoint_required"
        elif verify_failed:
            state = "VERIFY_FAILED"
            blocker = "successful_verify_required"
        else:
            lower = f"{item.section} {item.item}".lower()
            if "founder gate" in lower or "founder approval" in lower:
                state = "FOUNDER_GATE"
                blocker = "explicit_founder_approval_required"
            elif any(term in lower for term in (
                "verified outcome",
                "real production evidence",
                "actual revenue",
                "realized gross profit",
                "live verification",
            )):
                state = "REAL_WORLD_EVIDENCE_REQUIRED"
                blocker = "real_world_evidence_required"
            else:
                state = "UNVERIFIED_PENDING"
                blocker = "verify_and_live_closure_evidence_required"

        rows.append({
            "check_id": cid,
            "line": item.line,
            "section": item.section,
            "item": item.item,
            "state": state,
            "blocker": blocker,
            "verify_jobs": verifies,
            "closure_checkpoint_refs": refs,
        })

    applied_lines: list[int] = []
    if apply and close_lines:
        mutable = list(source_lines)
        for line_no in sorted(set(close_lines)):
            index = line_no - 1
            if index < 0 or index >= len(mutable):
                continue
            raw = mutable[index]
            if not raw.startswith("- [ ] "):
                continue
            mutable[index] = raw.replace("- [ ] ", "- [x] ", 1)
            applied_lines.append(line_no)
        if applied_lines:
            _atomic_replace_checklist(checklist, mutable)

    counts: dict[str, int] = {}
    for row in rows:
        key = row["state"]
        counts[key] = counts.get(key, 0) + 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "generated_at": current.isoformat(),
        "apply_enabled": bool(apply),
        "pending_row_count_before_apply": len(rows),
        "eligible_exact_closure_count": len(set(close_lines)),
        "applied_closure_count": len(applied_lines),
        "applied_checklist_lines": applied_lines,
        "state_counts": dict(sorted(counts.items())),
        "rows": rows,
        "completion_rule": (
            "PASS VERIFY + exact live closure checkpoint bound to the same "
            "current checklist row; tests alone never close a checklist item."
        ),
        "synthetic_completion_evidence_used": False,
        "founder_approval_inferred": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }

    out = root / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(out)
    return payload
