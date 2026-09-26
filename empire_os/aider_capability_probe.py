"""Disposable-clone capability probe for the Empire Coder Aider backend."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from empire_os.aider_builder import (
    AiderMutationRequest,
    DEFAULT_MODEL,
    run_aider_mutation,
)
from empire_os.builder_capabilities import record_builder_capability


MARKER_PATH = "tests/empire_aider_mutation_probe_marker.txt"
MARKER_TEXT = "EMPIRE_AIDER_MUTATION_OK\n"


@dataclass(frozen=True)
class AiderProbeResult:
    ok: bool
    reason: str
    model: str
    status: str
    exact_marker: bool
    changed_paths: tuple[str, ...]
    returncode: int | None = None
    output_tail: str | None = None
    production_mutation: bool = False
    production_push: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict:
        return asdict(self)


def _run(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def probe_aider_mutation(
    repo_root: str | Path = "/srv/empire_os",
    *,
    branch: str = "feature/revenue-intelligence-v2",
    work_root: str | Path = "/var/tmp/empire-aider-capability",
    model: str | None = None,
) -> AiderProbeResult:
    root = Path(repo_root).resolve()
    base = Path(work_root)
    base.mkdir(parents=True, exist_ok=True)
    clone = base / f"probe-{uuid4().hex}"
    selected_model = (
        str(model or os.getenv("EMPIRE_AIDER_MODEL") or DEFAULT_MODEL)
        .strip()
        or DEFAULT_MODEL
    )
    result = AiderProbeResult(
        False,
        "probe_not_completed",
        selected_model,
        "UNAVAILABLE",
        False,
        (),
    )

    try:
        cloned = _run(
            [
                "git",
                "clone",
                "--no-hardlinks",
                "--single-branch",
                "--branch",
                branch,
                str(root),
                str(clone),
            ],
            cwd=base,
        )
        if cloned.returncode != 0:
            result = AiderProbeResult(
                False,
                "clone_failed",
                selected_model,
                "CLONE_FAILED",
                False,
                (),
            )
            return result

        mutation = run_aider_mutation(
            clone,
            AiderMutationRequest(
                objective=(
                    "Create exactly one file at "
                    f"{MARKER_PATH} containing exactly "
                    "EMPIRE_AIDER_MUTATION_OK followed by one newline. "
                    "Do not modify any other file."
                ),
                allowed_paths=(MARKER_PATH,),
                model=selected_model,
                max_runtime_seconds=180,
            ),
        )
        changed = tuple(mutation.get("changed_paths") or ())
        marker = clone / MARKER_PATH
        exact = (
            marker.is_file()
            and marker.read_text(encoding="utf-8") == MARKER_TEXT
        )
        ok = (
            mutation.get("status") == "EDITED"
            and changed == (MARKER_PATH,)
            and exact
        )
        result = AiderProbeResult(
            ok,
            (
                "aider_mutation_ready"
                if ok
                else str(
                    mutation.get("reason")
                    or mutation.get("status")
                    or "aider_probe_failed"
                )
            )[:500],
            selected_model,
            str(mutation.get("status") or "UNKNOWN"),
            exact,
            changed,
            (
                None
                if mutation.get("returncode") is None
                else int(mutation.get("returncode"))
            ),
            (
                str(mutation.get("output_tail") or "")[-4000:]
                or None
            ),
        )
        return result
    except Exception as exc:
        result = AiderProbeResult(
            False,
            f"probe_error:{type(exc).__name__}:{exc}"[:500],
            selected_model,
            "FAILED",
            False,
            (),
        )
        return result
    finally:
        record_builder_capability(
            "empire_coder",
            "aider_mutation",
            ready=result.ok,
            reason=result.reason,
            model=result.model,
            evidence={
                "status": result.status,
                "exact_marker": result.exact_marker,
                "changed_paths": list(result.changed_paths),
                "returncode": result.returncode,
                "output_tail": result.output_tail,
                "production_mutation": False,
                "production_push": False,
            },
        )
        shutil.rmtree(clone, ignore_errors=True)
