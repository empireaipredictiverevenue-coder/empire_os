"""Git/worktree awareness without destructive Git operations."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .policy import filtered_environment, resolve_workspace


_BRANCH_RE = re.compile(r"[^a-zA-Z0-9._/-]+")


@dataclass(frozen=True)
class WorktreeState:
    workspace: str
    branch: str
    head: str
    dirty: bool
    status: str


class WorktreeController:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = resolve_workspace(workspace)

    def inspect(self) -> WorktreeState:
        branch = self._git("branch", "--show-current").strip()
        head = self._git("rev-parse", "HEAD").strip()
        status = self._git("status", "--short")
        return WorktreeState(
            str(self.workspace),
            branch,
            head,
            bool(status.strip()),
            status,
        )

    def create_isolated(
        self,
        *,
        task_id: str,
        destination_root: str | Path,
        base_ref: str = "HEAD",
        approved: bool = False,
    ) -> WorktreeState:
        """Create a task worktree only after an explicit approval gate."""
        if not approved:
            raise PermissionError("worktree creation requires explicit approval")
        base = Path(destination_root).expanduser().resolve()
        base.mkdir(parents=True, exist_ok=True)
        if base == self.workspace or self.workspace in base.parents:
            raise ValueError("task worktrees must live outside source worktree")
        safe_id = _BRANCH_RE.sub("-", task_id).strip("-/.")
        if not safe_id:
            raise ValueError("invalid task id")
        destination = (base / safe_id).resolve()
        try:
            destination.relative_to(base)
        except ValueError as exc:
            raise ValueError("task worktree path escaped root") from exc
        if destination.exists():
            raise FileExistsError(destination)
        branch = f"coder/{safe_id}"
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(destination), base_ref],
            cwd=self.workspace,
            env=filtered_environment(),
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        return WorktreeController(destination).inspect()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.workspace,
            env=filtered_environment(),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout
