"""Canonical completion-program progress reconciliation."""
from __future__ import annotations
import json, os, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def checklist_counts(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    done = text.count("- [x]") + text.count("- [X]")
    pending = text.count("- [ ]")
    return {"master_checklist_done": done, "master_checklist_pending": pending, "master_checklist_total": done + pending}

def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

def reconcile_completion_progress(*, repo: Path, progress_path: Path, checklist_path: Path, leases_path: Path) -> dict[str, Any]:
    current = json.loads(progress_path.read_text(encoding="utf-8"))
    if not isinstance(current, dict): raise ValueError("completion progress must be an object")
    leases = json.loads(leases_path.read_text(encoding="utf-8"))
    if not isinstance(leases, list): raise ValueError("leases must be a list")
    current["branch"] = _git(repo, "branch", "--show-current")
    current["head"] = _git(repo, "rev-parse", "--short", "HEAD")
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    current["active_atomic_builders"] = {str(x.get("lease_id") or x.get("id")): str(x.get("owner") or "UNKNOWN") for x in leases if isinstance(x, dict) and (x.get("lease_id") or x.get("id"))}
    diagram = current.setdefault("diagram_evidence", {})
    if not isinstance(diagram, dict):
        raise ValueError("diagram_evidence must be an object")
    counts = checklist_counts(checklist_path)
    diagram.update(counts)
    current["master_checklist"] = {
        "done": counts["master_checklist_done"],
        "pending": counts["master_checklist_pending"],
        "total": counts["master_checklist_total"],
    }
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=progress_path.name + ".", dir=progress_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(current, handle, indent=2, sort_keys=True); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, progress_path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return current


DEFAULT_PROGRESS_PATH = Path(
    "runtime/execution_plane/empire_completion_program_progress.json"
)
DEFAULT_CHECKLIST_PATH = Path("docs/MASTER_REMAINING_CHECKLIST.md")
DEFAULT_LEASES_PATH = Path("runtime/execution_plane/leases.json")


def refresh_completion_progress(repo: str | Path) -> dict[str, Any]:
    """Refresh canonical checklist counts and active leases in one local pass."""
    root = Path(repo).resolve()
    progress = root / DEFAULT_PROGRESS_PATH
    checklist = root / DEFAULT_CHECKLIST_PATH
    leases = root / DEFAULT_LEASES_PATH
    missing = [
        str(path.relative_to(root))
        for path in (progress, checklist, leases)
        if not path.exists()
    ]
    if missing:
        return {
            "schema_version": "empire.completion-progress-refresh.v1",
            "status": "UNAVAILABLE",
            "reason": "completion_progress_input_missing",
            "missing": missing,
            "execution_authority": "none",
        }
    packet = reconcile_completion_progress(
        repo=root,
        progress_path=progress,
        checklist_path=checklist,
        leases_path=leases,
    )
    checklist_truth = dict(packet.get("master_checklist") or {})
    return {
        "schema_version": "empire.completion-progress-refresh.v1",
        "status": "AVAILABLE",
        "updated_at": packet.get("updated_at"),
        "branch": packet.get("branch"),
        "head": packet.get("head"),
        "master_checklist": checklist_truth,
        "active_atomic_builder_count": len(
            packet.get("active_atomic_builders") or {}
        ),
        "active_atomic_builders": dict(
            packet.get("active_atomic_builders") or {}
        ),
        "execution_authority": "none",
    }
