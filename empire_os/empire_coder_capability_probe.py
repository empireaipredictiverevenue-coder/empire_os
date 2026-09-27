"""Isolated mutation-capability probe for Empire Coder.

This proves only the local structured-patch protocol. It never touches the
production working tree, never pushes a branch, and grants no production or
commercial authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from empire_os.builder_capabilities import record_builder_capability
from empire_os.coder.context import ContextPack
from empire_os.coder.llama_cpp_provider import LlamaCppProvider
from empire_os.coder.models import ModelRoute
from empire_os.coder.patch import PatchEngine
from empire_os.coder.structured_patch import (
    PatchOperation,
    StructuredPatchRefiner,
    StructuredPatchValidator,
)


MARKER_PATH = "tests/empire_coder_structured_patch_probe_marker.txt"
MARKER_TEXT = "EMPIRE_CODER_PATCH_OK\n"


@dataclass(frozen=True)
class EmpireCoderProbeResult:
    ok: bool
    reason: str
    model: str
    proposal_operation: str | None
    proposal_path: str | None
    exact_marker: bool
    changed_paths: tuple[str, ...]
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
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def probe_empire_coder_structured_patch(
    repo_root: str | Path = "/srv/empire_os",
    *,
    model: str = "qwen2.5-coder:1.5b",
    base_url: str = "http://127.0.0.1:11435",
    branch: str = "feature/revenue-intelligence-v2",
    work_root: str | Path = "/var/tmp/empire-coder-capability",
) -> EmpireCoderProbeResult:
    root = Path(repo_root).resolve()
    base = Path(work_root)
    base.mkdir(parents=True, exist_ok=True)
    clone = base / f"probe-{uuid4().hex}"

    result = EmpireCoderProbeResult(
        ok=False,
        reason="probe_not_completed",
        model=model,
        proposal_operation=None,
        proposal_path=None,
        exact_marker=False,
        changed_paths=(),
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
            result = EmpireCoderProbeResult(
                False,
                "clone_failed",
                model,
                None,
                None,
                False,
                (),
            )
            return result

        provider = LlamaCppProvider(
            base_url=base_url,
            timeout_seconds=90,
        )
        if not provider.health():
            result = EmpireCoderProbeResult(
                False,
                "llama_cpp_unhealthy",
                model,
                None,
                None,
                False,
                (),
            )
            return result

        objective = (
            "Create exactly one file at "
            f"{MARKER_PATH} containing exactly "
            "EMPIRE_CODER_PATCH_OK followed by one newline. "
            "Use create_file. Do not modify any other file."
        )
        context = ContextPack(
            objective=objective,
            task_state={
                "probe": True,
                "production_mutation": False,
                "execution_authority": "none",
            },
            documents=(),
            symbols=(),
            token_budget_chars=4000,
        )
        route = ModelRoute(
            provider="llama_cpp",
            model=model,
            reason="isolated_structured_patch_capability_probe",
            local=True,
            cost_tier=0,
        )
        candidate = StructuredPatchRefiner(
            provider,
            StructuredPatchValidator(clone),
        ).propose(
            task_id="empire_coder_capability_probe",
            objective=objective,
            context=context,
            route=route,
            max_output_chars=3200,
        )

        proposal = candidate.proposal
        exact = (
            candidate.eligible
            and proposal.operation is PatchOperation.CREATE_FILE
            and proposal.target_path == MARKER_PATH
            and proposal.new_text == MARKER_TEXT
        )
        if not exact:
            result = EmpireCoderProbeResult(
                False,
                "structured_patch_not_exact",
                model,
                proposal.operation.value,
                proposal.target_path,
                False,
                (),
            )
            return result

        patch = PatchEngine(
            clone,
            runtime_root=clone / "runtime/coder-capability-probe",
        )
        patch.create_file(
            "empire_coder_capability_probe",
            MARKER_PATH,
            MARKER_TEXT,
        )
        marker = clone / MARKER_PATH
        if marker.read_text(encoding="utf-8") != MARKER_TEXT:
            result = EmpireCoderProbeResult(
                False,
                "marker_verification_failed",
                model,
                proposal.operation.value,
                proposal.target_path,
                False,
                (),
            )
            return result

        status = _run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=clone,
        )
        changed = tuple(
            sorted(
                line[3:].strip()
                for line in status.stdout.splitlines()
                if len(line) >= 4
                and line[3:].strip()
                and not line[3:].strip().startswith("runtime/")
            )
        )
        ok = changed == (MARKER_PATH,)
        result = EmpireCoderProbeResult(
            ok,
            (
                "structured_patch_mutation_ready"
                if ok
                else "unexpected_changed_paths"
            ),
            model,
            proposal.operation.value,
            proposal.target_path,
            True,
            changed,
        )
        return result
    except Exception as exc:
        result = EmpireCoderProbeResult(
            False,
            f"probe_error:{type(exc).__name__}:{exc}"[:500],
            model,
            None,
            None,
            False,
            (),
        )
        return result
    finally:
        record_builder_capability(
            "empire_coder",
            "structured_patch_mutation",
            ready=result.ok,
            reason=result.reason,
            model=result.model,
            evidence={
                "proposal_operation": result.proposal_operation,
                "proposal_path": result.proposal_path,
                "exact_marker": result.exact_marker,
                "changed_paths": list(result.changed_paths),
                "production_mutation": False,
                "production_push": False,
            },
        )
        shutil.rmtree(clone, ignore_errors=True)
