"""Promptfoo verification worker for execution-plane AI behavior changes."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any


REQUEST_ROOT = Path("runtime/execution_plane/promptfoo_requests")
RESULT_ROOT = Path("runtime/execution_plane/promptfoo_results")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in tuple(env):
        upper = key.upper()
        if any(token in upper for token in (
            "SUPABASE_SERVICE",
            "RESEND",
            "SENDGRID",
            "BREVO",
            "PRIVATE_KEY",
            "PASSWORD",
            "COOKIE",
        )):
            env.pop(key, None)
    env["PROMPTFOO_DISABLE_TELEMETRY"] = "1"
    env["PROMPTFOO_DISABLE_UPDATE"] = "1"
    return env


def run_promptfoo_request(
    repo_root: str | Path,
    request_path: str | Path,
    *,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    path = Path(request_path).resolve()
    request_root = (root / REQUEST_ROOT).resolve()
    try:
        path.relative_to(request_root)
    except ValueError as exc:
        raise ValueError("request must live under promptfoo request root") from exc

    raw = json.loads(path.read_text(encoding="utf-8"))
    request_id = str(raw.get("request_id") or "").strip()
    config = str(raw.get("config") or "").strip()
    if not request_id:
        raise ValueError("promptfoo request_id required")
    if config != "evals/empire_core_policy/promptfooconfig.yaml":
        raise ValueError("unsupported Promptfoo config")

    result_dir = root / RESULT_ROOT
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{request_id}.json"

    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            return existing

    command = [
        "npm",
        "run",
        "eval:empire",
        "--",
        "--no-cache",
    ]
    started = _now()
    try:
        completed = subprocess.run(
            command,
            cwd=str(root),
            env=_safe_env(),
            capture_output=True,
            text=True,
            timeout=max(60, min(int(timeout_seconds), 1800)),
            check=False,
        )
        returncode = completed.returncode
        output_tail = (
            (completed.stdout or "") + "\n" + (completed.stderr or "")
        )[-12_000:]
        status = "PASSED" if returncode == 0 else "FAILED"
        error = None
    except subprocess.TimeoutExpired as exc:
        returncode = None
        output_tail = (
            (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        )[-6000:]
        status = "TIMED_OUT"
        error = "PromptfooTimeout"

    result = {
        "schema_version": "empire.execution-plane-promptfoo-result.v1",
        "request_id": request_id,
        "candidate_ref": str(raw.get("candidate_ref") or "").strip(),
        "config": config,
        "started_at": started,
        "completed_at": _now(),
        "status": status,
        "passed": status == "PASSED",
        "returncode": returncode,
        "output_tail": output_tail,
        "error": error,
        "production_promotion_allowed": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }
    tmp = result_path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(result_path)
    return result


def run_pending_promptfoo(
    repo_root: str | Path,
    *,
    max_items: int = 4,
    timeout_seconds: int = 900,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    requests = root / REQUEST_ROOT
    requests.mkdir(parents=True, exist_ok=True)
    results = root / RESULT_ROOT
    results.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    bounded = max(1, min(int(max_items), 20))
    for path in sorted(requests.glob("*.json")):
        result_path = results / path.name
        if result_path.exists():
            continue
        rows.append(
            run_promptfoo_request(
                root,
                path,
                timeout_seconds=timeout_seconds,
            )
        )
        if len(rows) >= bounded:
            break

    return {
        "schema_version": "empire.execution-plane-promptfoo-worker.v1",
        "processed_count": len(rows),
        "passed_count": sum(row.get("passed") is True for row in rows),
        "failed_count": sum(row.get("passed") is False for row in rows),
        "results": rows,
        "production_promotion_allowed": False,
        "execution_authority": "none",
    }
