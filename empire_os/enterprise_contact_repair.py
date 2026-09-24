"""Bounded self-resolution for Enterprise Contact Intelligence.

Known transient/runtime faults are retried deterministically. Code/test defects
may be repaired only in an isolated git worktree by Empire Coder, with a narrow
file allowlist, deterministic verification, compare-and-swap integration, and
no production/commercial authority expansion.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Mapping

from empire_os.coder.orchestrator import EmpireCoder
from empire_os.coder.worktree import WorktreeController


ROOT = Path("/srv/empire_os")
RUNTIME = ROOT / "runtime" / "predictive_revenue"
INCIDENT_PATH = RUNTIME / "enterprise_contact_repair_incident.json"
STATE_PATH = RUNTIME / "enterprise_contact_repair_state.json"
LATEST_PATH = RUNTIME / "enterprise_contact_repair_latest.json"
WORKTREE_ROOT = Path("/home/ubuntu/empire_os_repair_worktrees")

ALLOWED_REPAIR_PATHS = frozenset({
    "empire_os/buyer_discovery.py",
    "empire_os/buyer_probe_worker.py",
    "empire_os/buyer_deferred_enrichment.py",
    "empire_os/enterprise_contact_intelligence.py",
    "scripts/run_buyer_deferred_enrichment.py",
    "scripts/run_enterprise_contact_intelligence.py",
    "tests/test_buyer_discovery.py",
    "tests/test_buyer_probe_worker.py",
    "tests/test_enterprise_contact_intelligence.py",
    "tests/test_enterprise_targeted_retry.py",
})
CORE_TESTS = (
    "tests/test_buyer_discovery.py",
    "tests/test_buyer_probe_worker.py",
    "tests/test_enterprise_contact_intelligence.py",
    "tests/test_enterprise_targeted_retry.py",
)
TRANSIENT_TOKENS = (
    "timeout",
    "timed out",
    "http 502",
    "http 503",
    "http 504",
    "connection reset",
    "connection refused",
    "temporarily unavailable",
    "thread killed by timeout",
)
DATA_QUALITY_TOKENS = (
    "no_bound_contact",
    "no_contact_evidence",
    "target_identity_mismatch",
    "target_contact_not_verified",
    "site_unavailable",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o640)
    tmp.replace(path)
    os.chmod(path, 0o640)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def classify_failure(text: str) -> str:
    value = str(text or "").lower()
    if any(
        token in value
        for token in (
            "assertionerror",
            "typeerror",
            "keyerror",
            "attributeerror",
            "syntaxerror",
            "nameerror",
            "failed tests/",
        )
    ):
        return "CODE_DEFECT"
    if any(token in value for token in DATA_QUALITY_TOKENS):
        return "DATA_QUALITY"
    if any(token in value for token in TRANSIENT_TOKENS):
        return "TRANSIENT_INFRA"
    return "UNKNOWN"


def _failing_tests(log_text: str) -> list[str]:
    found = []
    for match in re.findall(
        r"FAILED\s+(tests/[^\s]+)",
        str(log_text or ""),
    ):
        value = match.strip()
        if value and value not in found:
            found.append(value)
    return found[:8]


def record_incident(
    *,
    kind: str,
    log_text: str,
    command: str,
    returncode: int,
    base_head: str | None = None,
) -> dict[str, Any]:
    tail = str(log_text or "")[-16000:]
    signature = hashlib.sha256(
        (str(kind) + "\n" + tail).encode("utf-8")
    ).hexdigest()
    payload = {
        "schema_version": "empire.enterprise-contact-repair-incident.v1",
        "fingerprint": signature,
        "kind": str(kind),
        "classification": classify_failure(tail),
        "command": str(command),
        "returncode": int(returncode),
        "base_head": str(base_head or "").strip() or None,
        "failing_tests": _failing_tests(tail),
        "log_tail": tail,
        "status": "OPEN",
        "created_at": _now(),
        "live_outbound_send": False,
        "payment_action": False,
        "actual_revenue": False,
    }
    _atomic_json(INCIDENT_PATH, payload)
    return payload


def _run(argv: list[str], *, cwd: Path = ROOT, timeout: int = 300):
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env={**os.environ, "PYTHONPATH": str(cwd)},
    )


def _git(*args: str, cwd: Path = ROOT, timeout: int = 60):
    return _run(["git", *args], cwd=cwd, timeout=timeout)


def _main_state() -> tuple[str, str, bool]:
    branch = _git("branch", "--show-current").stdout.strip()
    head = _git("rev-parse", "HEAD").stdout.strip()
    dirty = bool(_git("status", "--porcelain").stdout.strip())
    return branch, head, dirty


def _validate_changed_paths(worktree: Path) -> list[str]:
    raw = _git("status", "--porcelain", cwd=worktree).stdout
    paths = []
    for line in raw.splitlines():
        candidate = line[3:].strip()
        if " -> " in candidate:
            candidate = candidate.split(" -> ", 1)[1].strip()
        if candidate:
            paths.append(candidate)
    paths = list(dict.fromkeys(paths))
    if not paths:
        raise RuntimeError("coder repair produced no changed files")
    if len(paths) > 2:
        raise RuntimeError("coder repair exceeded two-file change budget")
    denied = [path for path in paths if path not in ALLOWED_REPAIR_PATHS]
    if denied:
        raise RuntimeError(
            "coder repair touched non-allowlisted paths:" + ",".join(denied)
        )
    return paths


def _guard_candidate_diff(worktree: Path, changed: list[str]) -> None:
    diff = _git("diff", "--", *changed, cwd=worktree).stdout
    lower = diff.lower()
    if any(
        token in lower
        for token in (
            "pytest.skip",
            "@pytest.mark.skip",
            "@pytest.mark.xfail",
            "unittest.skip",
        )
    ):
        raise RuntimeError("coder repair attempted to suppress tests")
    risky_additions = (
        "live_outbound_send = true",
        '"live_outbound_send": true',
        "outreach_authorized = true",
        '"outreach_authorized": true',
        "payment_action = true",
        '"payment_action": true',
        "actual_revenue = true",
        '"actual_revenue": true',
        "reviews_approved = 1",
        "empire_autonomous_mode=execute",
    )
    for line in diff.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("+") and any(
            token in stripped for token in risky_additions
        ):
            raise RuntimeError(
                "coder repair attempted authority expansion"
            )

    if any(path.startswith("tests/") for path in changed):
        for line in diff.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("-") and "assert " in stripped:
                raise RuntimeError(
                    "coder repair attempted to remove a test assertion"
                )


def _verify(worktree: Path, tests: list[str]) -> tuple[bool, str]:
    command = [
        str(ROOT / ".venv/bin/python"),
        "-m",
        "pytest",
        "-q",
        *(tests or list(CORE_TESTS)),
    ]
    result = _run(command, cwd=worktree, timeout=240)
    output = ((result.stdout or "") + "\n" + (result.stderr or ""))[-12000:]
    return result.returncode == 0, output


def _repair_code_incident(incident: Mapping[str, Any]) -> dict[str, Any]:
    branch, base_head, dirty = _main_state()
    if branch != "feature/revenue-intelligence-v2":
        raise RuntimeError(f"unexpected_main_branch:{branch}")
    if dirty:
        raise RuntimeError("main_checkout_dirty")
    recorded_head = str(incident.get("base_head") or "").strip()
    if recorded_head and recorded_head != base_head:
        raise RuntimeError("incident_base_head_changed")

    fingerprint = str(incident["fingerprint"])[:12]
    worktree_id = (
        f"contact-repair-{fingerprint}-{int(time.time())}"
    )
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)

    state = WorktreeController(ROOT).create_isolated(
        task_id=worktree_id,
        destination_root=WORKTREE_ROOT,
        base_ref=base_head,
        approved=True,
    )
    worktree = Path(state.workspace)

    coder = EmpireCoder(worktree)
    objective = (
        "Repair this Enterprise Contact Intelligence test/code defect. "
        "Make the smallest safe patch. Do not modify systemd, deployment "
        "authority, Supabase migrations, outbound, payments, credentials, "
        "commercial truth, recovery, toop, or unrelated modules. "
        "Failure evidence:\n" + str(incident.get("log_tail") or "")[-7000:]
    )
    task = coder.create_task(objective)
    context = coder.build_context(
        task.id,
        terms=(
            "enterprise contact intelligence",
            "buyer discovery",
            "buyer probe",
            "deferred enrichment",
        ),
        symbols=(),
        budget_chars=8000,
    )
    candidate = coder.propose_structured_patch(
        task.id,
        (
            "Apply one minimal development repair for the supplied failing "
            "test. The target file must be one of the relevant contact "
            "intelligence source/test files already present in context. "
            "Preserve fail-closed governance and truth boundaries."
        ),
        context,
    )
    if not candidate.eligible:
        raise RuntimeError(
            "coder_candidate_ineligible:"
            + ",".join(candidate.validation.reasons)
        )
    target = candidate.proposal.target_path
    if target not in ALLOWED_REPAIR_PATHS:
        raise RuntimeError(f"coder_target_not_allowlisted:{target}")

    coder.apply_structured_patch(task.id, candidate)
    changed = _validate_changed_paths(worktree)
    _guard_candidate_diff(worktree, changed)
    tests = list(incident.get("failing_tests") or [])
    verify_tests = list(dict.fromkeys(tests + list(CORE_TESTS)))
    passed, verification_output = _verify(worktree, verify_tests)
    if not passed:
        coder.patch.rollback(task.id)
        raise RuntimeError(
            "coder_repair_verification_failed:"
            + verification_output[-3000:]
        )

    add = _git("add", "--", *changed, cwd=worktree)
    if add.returncode != 0:
        raise RuntimeError("git_add_failed:" + add.stderr[-500:])
    commit = _git(
        "-c",
        "user.name=EmpireOS Repair Controller",
        "-c",
        "user.email=repair@empire-ai.local",
        "commit",
        "-m",
        f"repair: auto enterprise contact {fingerprint}",
        cwd=worktree,
    )
    if commit.returncode != 0:
        raise RuntimeError("git_commit_failed:" + commit.stderr[-800:])
    repair_head = _git("rev-parse", "HEAD", cwd=worktree).stdout.strip()

    current_branch, current_head, current_dirty = _main_state()
    if (
        current_branch != branch
        or current_head != base_head
        or current_dirty
    ):
        return {
            "status": "QUARANTINED_HEAD_MOVED",
            "worktree": str(worktree),
            "repair_head": repair_head,
            "changed_files": changed,
            "tests": verify_tests,
        }

    merge = _git("merge", "--ff-only", repair_head, cwd=ROOT)
    if merge.returncode != 0:
        raise RuntimeError("ff_merge_failed:" + merge.stderr[-1000:])

    passed_main, main_output = _verify(ROOT, verify_tests)
    if not passed_main:
        revert = _git(
            "-c",
            "user.name=EmpireOS Repair Controller",
            "-c",
            "user.email=repair@empire-ai.local",
            "revert",
            "--no-edit",
            repair_head,
            cwd=ROOT,
        )
        if revert.returncode != 0:
            raise RuntimeError(
                "post_merge_verification_failed_and_revert_failed:"
                + main_output[-1800:]
                + ":"
                + revert.stderr[-800:]
            )
        raise RuntimeError(
            "post_merge_verification_failed_reverted:"
            + main_output[-2400:]
        )

    push = _git(
        "push",
        "origin",
        "feature/revenue-intelligence-v2",
        cwd=ROOT,
        timeout=120,
    )
    return {
        "status": (
            "RESOLVED_AND_PUSHED"
            if push.returncode == 0
            else "MERGED_LOCAL_PUSH_FAILED"
        ),
        "worktree": str(worktree),
        "repair_head": repair_head,
        "changed_files": changed,
        "tests": verify_tests,
        "push_error": (
            None if push.returncode == 0 else push.stderr[-1000:]
        ),
    }


def _retry_branch_push() -> dict[str, Any]:
    branch, _head, dirty = _main_state()
    if branch != "feature/revenue-intelligence-v2" or dirty:
        return {
            "status": "PUSH_RETRY_BLOCKED",
            "reason": (
                f"branch={branch};dirty={dirty}"
            ),
        }
    push = _git(
        "push",
        "origin",
        "feature/revenue-intelligence-v2",
        cwd=ROOT,
        timeout=120,
    )
    return {
        "status": (
            "RESOLVED_AND_PUSHED"
            if push.returncode == 0
            else "MERGED_LOCAL_PUSH_FAILED"
        ),
        "push_error": (
            None if push.returncode == 0 else push.stderr[-1000:]
        ),
    }


def _retry_runtime_sync() -> dict[str, Any]:
    command = [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_enterprise_contact_intelligence.py"),
    ]
    last = None
    for attempt in range(1, 4):
        last = _run(command, cwd=ROOT, timeout=120)
        if last.returncode == 0:
            return {
                "status": "RESOLVED_RUNTIME_RETRY",
                "attempts": attempt,
                "output": (last.stdout or "")[-4000:],
            }
        time.sleep(2 ** (attempt - 1))
    assert last is not None
    return {
        "status": "RUNTIME_RETRY_EXHAUSTED",
        "attempts": 3,
        "output": (
            (last.stdout or "") + "\n" + (last.stderr or "")
        )[-5000:],
    }


def run_repair_cycle() -> dict[str, Any]:
    incident = _load(INCIDENT_PATH)
    state = _load(STATE_PATH)
    intel = _load(RUNTIME / "enterprise_contact_intelligence_latest.json")

    if incident.get("status") == "RESOLVED":
        incident = {}

    classification = str(incident.get("classification") or "")
    if not incident and int(intel.get("error_count") or 0) > 0:
        error_text = json.dumps(intel.get("errors") or [])
        classification = classify_failure(error_text)
        incident = record_incident(
            kind="runtime_sync_failure",
            log_text=error_text,
            command="run_enterprise_contact_intelligence.py",
            returncode=1,
            base_head=_git("rev-parse", "HEAD").stdout.strip(),
        )

    if not incident or incident.get("status") == "RESOLVED":
        result = {
            "status": "HEALTHY",
            "classification": None,
            "action": "none",
        }
    elif classification == "TRANSIENT_INFRA":
        result = _retry_runtime_sync()
        result["classification"] = classification
    elif classification == "DATA_QUALITY":
        result = {
            "status": "RESOLVED_DEFERRED_TO_TARGETED_ENRICHMENT",
            "classification": classification,
            "action": "existing_deferred_enrichment_loop",
        }
    elif classification == "CODE_DEFECT":
        fingerprint = str(incident.get("fingerprint") or "")
        same_incident = (
            fingerprint
            and state.get("last_fingerprint") == fingerprint
        )
        repair_attempts = (
            int(state.get("repair_attempts") or 0)
            if same_incident
            else 0
        )
        if (
            same_incident
            and state.get("last_status") == "MERGED_LOCAL_PUSH_FAILED"
        ):
            result = _retry_branch_push()
            result["classification"] = classification
        elif (
            same_incident
            and state.get("last_status") in {
                "RESOLVED_AND_PUSHED",
                "QUARANTINED_HEAD_MOVED",
                "QUARANTINED_REPAIR_EXHAUSTED",
            }
        ):
            result = {
                "status": str(state["last_status"]),
                "classification": classification,
                "action": "already_processed",
            }
        elif repair_attempts >= 3:
            result = {
                "status": "QUARANTINED_REPAIR_EXHAUSTED",
                "classification": classification,
                "action": "repair_budget_exhausted",
                "repair_attempts": repair_attempts,
            }
        else:
            try:
                result = _repair_code_incident(incident)
                result["classification"] = classification
                result["repair_attempts"] = repair_attempts + 1
            except Exception as exc:
                result = {
                    "status": "CODER_REPAIR_FAILED",
                    "classification": classification,
                    "action": "retry_on_next_cycle",
                    "repair_attempts": repair_attempts + 1,
                    "error": f"{type(exc).__name__}:{str(exc)[:1800]}",
                }
    else:
        result = {
            "status": "OBSERVE_ONLY_UNKNOWN",
            "classification": classification or "UNKNOWN",
            "action": "none",
        }

    if str(result.get("status") or "").startswith("RESOLVED"):
        incident = dict(incident)
        incident["status"] = "RESOLVED"
        incident["resolved_at"] = _now()
        incident["resolution"] = result
        _atomic_json(INCIDENT_PATH, incident)

    previous_attempts = (
        int(state.get("repair_attempts") or 0)
        if (
            incident
            and state.get("last_fingerprint")
            == incident.get("fingerprint")
        )
        else 0
    )
    state = {
        "updated_at": _now(),
        "last_fingerprint": incident.get("fingerprint") if incident else None,
        "last_status": result.get("status"),
        "last_classification": result.get("classification"),
        "repair_attempts": int(
            result.get("repair_attempts")
            if result.get("repair_attempts") is not None
            else previous_attempts
        ),
    }
    _atomic_json(STATE_PATH, state)

    payload = {
        "schema_version": "empire.enterprise-contact-repair.v1",
        "updated_at": _now(),
        **result,
        "live_outbound_send": False,
        "payment_action": False,
        "actual_revenue": False,
    }
    _atomic_json(LATEST_PATH, payload)
    return payload
