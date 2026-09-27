"""Restricted subprocess execution for Empire Coder."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

from .models import ToolDecision, ToolRunResult, utc_now
from .security import scrub_text
from .policy import (
    classify_command,
    filtered_environment,
    resolve_path,
    resolve_runtime_root,
    resolve_workspace,
)


class SafeCommandRunner:
    def __init__(
        self,
        workspace: str | Path,
        *,
        runtime_root: str | Path | None = None,
        max_output_chars: int = 20_000,
    ) -> None:
        self.workspace = resolve_workspace(workspace)
        self.runtime_root = resolve_runtime_root(
            self.workspace, runtime_root
        )
        self.logs = self.runtime_root / "tool_runs"
        self.logs.mkdir(parents=True, exist_ok=True)
        os.chmod(self.logs, 0o700)
        self.max_output_chars = max_output_chars

    def run(
        self,
        argv: Iterable[str],
        *,
        task_id: str,
        cwd: str | Path | None = None,
        timeout: int = 120,
        approved: bool = False,
    ) -> ToolRunResult:
        args = tuple(str(item) for item in argv)
        decision = classify_command(args)
        if decision is ToolDecision.DENY:
            result = ToolRunResult(
                "subprocess", args, decision, None,
                stderr="command denied by Empire Coder policy",
            )
            self._record(task_id, result)
            return result
        if decision is ToolDecision.REQUIRE_APPROVAL and not approved:
            result = ToolRunResult(
                "subprocess", args, decision, None,
                stderr="explicit approval required",
            )
            self._record(task_id, result)
            return result

        run_cwd = (
            self.workspace
            if cwd is None
            else resolve_path(self.workspace, cwd)
        )
        env = filtered_environment()
        try:
            proc = subprocess.run(
                list(args),
                cwd=run_cwd,
                env=env,
                shell=False,
                capture_output=True,
                text=True,
                timeout=max(1, min(int(timeout), 900)),
                check=False,
            )
            result = ToolRunResult(
                "subprocess",
                args,
                decision,
                proc.returncode,
                stdout=scrub_text(proc.stdout[-self.max_output_chars:]),
                stderr=scrub_text(proc.stderr[-self.max_output_chars:]),
                mutation_occurred=(
                    decision is ToolDecision.REQUIRE_APPROVAL
                ),
            )
        except subprocess.TimeoutExpired as exc:
            result = ToolRunResult(
                "subprocess",
                args,
                decision,
                None,
                stdout=scrub_text((exc.stdout or "")[-self.max_output_chars:]),
                stderr=scrub_text((exc.stderr or "")[-self.max_output_chars:]),
                timed_out=True,
            )
        self._record(task_id, result)
        return result

    def _record(self, task_id: str, result: ToolRunResult) -> None:
        safe = "".join(
            ch for ch in task_id if ch.isalnum() or ch in "_-"
        )
        path = self.logs / f"{safe}.jsonl"
        record = {
            "ts": utc_now(),
            "task_id": task_id,
            **result.as_dict(),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        os.chmod(path, 0o600)
