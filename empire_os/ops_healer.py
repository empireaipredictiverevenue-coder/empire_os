"""Allowlisted reversible healer for EmpireOS reliability incidents."""
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.ops_sentinel import REPAIRABLE_UNITS


ROOT = Path("/srv/empire_os")
SAFE_JOBS = {
    "source_health_refresh": [
        str(ROOT / "scripts/run_source_health_observer_cron.sh"),
    ],
    "buyer_review_materializer": [
        str(ROOT / ".venv/bin/python"),
        str(ROOT / "scripts/run_buyer_review_materializer.py"),
        "--scan-limit", "40",
        "--proposal-limit", "10",
        "--max-offset", "500",
        "--probe-workers", "8",
    ],
}


def _run(command: list[str], timeout: int = 180) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    return {
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-1200:],
        "stderr_tail": (result.stderr or "")[-1200:],
    }


def execute_action(
    action: Mapping[str, Any],
    *,
    runner: Callable[[list[str], int], dict[str, Any]] = _run,
) -> dict[str, Any]:
    kind = str(action.get("action") or "")
    target = str(action.get("target") or "")
    if str(action.get("authority") or "") != "internal_write":
        return {"ok": False, "decision": "BLOCKED", "reason": "authority_not_internal_write"}

    if kind == "restart_unit":
        if target not in REPAIRABLE_UNITS:
            return {"ok": False, "decision": "BLOCKED", "reason": "unit_not_allowlisted"}
        result = runner(["systemctl", "restart", target], 60)
    elif kind == "run_safe_job":
        command = SAFE_JOBS.get(target)
        if command is None:
            return {"ok": False, "decision": "BLOCKED", "reason": "job_not_allowlisted"}
        result = runner(command, 300)
    else:
        return {"ok": False, "decision": "BLOCKED", "reason": "action_not_allowlisted"}

    ok = result.get("returncode") == 0
    return {
        "ok": ok,
        "decision": "EXECUTED" if ok else "FAILED",
        "action": kind,
        "target": target,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }


def execute_plan(plan: list[Mapping[str, Any]], *, max_actions: int = 3) -> list[dict[str, Any]]:
    results = []
    for action in plan[: max(0, min(int(max_actions), 5))]:
        results.append(execute_action(action))
    return results
