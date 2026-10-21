"""Read the CURRENT EmpireOS worker's declared adapters without executing it.

This is a no-progress retry guard for the pre-existing department dispatchers,
NOT a new agent or permission grant. Unknown or unverifiable targets fail closed.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


MISSING_SPECIALIST = "specialist_adapter_required"
WORKER_HANDLER = "_run_one_department_work_impl"


def _worker_capabilities(root: str | Path) -> tuple[frozenset[str], dict[str, tuple[str, str]]]:
    """Extract only statically declared capabilities from the existing worker.

    Read source as DATA. Never import, eval, execute or trust embedded instructions.
    Reads both committed handlers and live owners' additions without modifying
    their worker file. A handler branch is not itself evidence of correctness.
    """
    repo = Path(root).resolve()
    source = (repo / "empire_os" / "department_worker.py").resolve()
    if not source.is_relative_to(repo) or not source.is_file():
        return frozenset(), {}
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError):
        return frozenset(), {}

    branches: set[str] = set()
    commands: dict[str, tuple[str, str]] = {}
    for stmt in tree.body:
        # The existing work handler owns exact target branches.
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == WORKER_HANDLER:
            for node in ast.walk(stmt):
                if not isinstance(node, ast.If):
                    continue
                test = node.test
                if (
                    isinstance(test, ast.Compare)
                    and len(test.ops) == len(test.comparators) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and isinstance(test.left, ast.Attribute)
                    and test.left.attr == "target_component"
                    and isinstance(test.left.value, ast.Name)
                    and test.left.value.id == "item"
                    and isinstance(test.comparators[0], ast.Constant)
                    and type(test.comparators[0].value) is str
                ):
                    branches.add(test.comparators[0].value)
        # Extract only the literal SAFE_COMMANDS mapping used by this worker.
        target_names = []
        if isinstance(stmt, ast.Assign):
            target_names = [node.id for node in stmt.targets if isinstance(node, ast.Name)]
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            target_names = [stmt.target.id]
        if "SAFE_COMMANDS" not in target_names:
            continue
        try:
            raw: Any = ast.literal_eval(stmt.value)
        except (ValueError, TypeError, RecursionError, MemoryError):
            continue
        if not isinstance(raw, dict):
            continue
        for key, spec in raw.items():
            if (
                isinstance(key, str) and key
                and isinstance(spec, (list, tuple)) and len(spec) == 2
                and all(isinstance(value, str) for value in spec)
            ):
                commands[key] = (spec[0], spec[1])
    return frozenset(branches), commands


def has_existing_department_adapter(root: str | Path, target_component: str) -> bool:
    """May this previously blocked target be retried? NOT an execution grant."""
    if not isinstance(target_component, str) or not target_component:
        return False
    repo = Path(root).resolve()
    direct, commands = _worker_capabilities(repo)
    if target_component in direct:
        return True
    spec = commands.get(target_component)
    if spec is None:
        return False
    # Keep scripts inside the current repo and only accept actual files.
    script = (repo / spec[0]).resolve()
    return script.is_relative_to(repo) and script.is_file()


def eligible_specialist_reopen_reasons(
    root: str | Path, target_component: str,
) -> tuple[str, ...]:
    """Circuit-break unproductive existing queue retries until support exists."""
    return (MISSING_SPECIALIST,) if has_existing_department_adapter(
        root, target_component
    ) else ()
