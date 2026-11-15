"""Independent verification stage for Empire Coder."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Iterable

from .models import (
    VerificationCheck,
    VerificationReport,
    VerificationVerdict,
)
from .policy import PolicyError, resolve_path, resolve_workspace
from .runner import SafeCommandRunner
from .security import scan_paths


def _is_substantive_check(argv: tuple[str, ...]) -> bool:
    """Do not confuse a successful Git status with behavioural validation."""
    if not argv:
        return False
    exe = Path(argv[0]).name.lower()
    if exe in {"pytest", "ruff", "mypy", "pyright"}:
        return True
    if exe in {"python", "python3"}:
        return len(argv) >= 3 and argv[1] == "-m" and argv[2] in {
            "pytest", "py_compile", "compileall",
        }
    if exe == "node":
        return len(argv) >= 2 and argv[1] == "--check"
    if exe in {"npm", "pnpm", "yarn"}:
        return (len(argv) >= 2 and argv[1] == "test") or (
            len(argv) >= 3 and argv[1] == "run" and argv[2] in {
                "test", "test:unit", "test:integration", "lint",
                "typecheck", "check", "build:check",
            }
        )
    return False


class Verifier:
    def __init__(self, workspace: str | Path) -> None:
        self.workspace = resolve_workspace(workspace)
        self.runner = SafeCommandRunner(self.workspace)

    def verify(
        self,
        *,
        task_id: str,
        changed_files: Iterable[str],
        commands: Iterable[Iterable[str]] = (),
        objective_terms: Iterable[str] = (),
    ) -> VerificationReport:
        files = tuple(dict.fromkeys(str(p).strip() for p in changed_files if str(p).strip()))
        steps = tuple(tuple(str(arg) for arg in command) for command in commands)
        checks: list[VerificationCheck] = []
        reasons: list[str] = []
        warnings: list[str] = []
        safe_files: list[str] = []

        # A successful Git command does not prove that an agent changed anything.
        # Check every claimed file against this worktree, not an unrelated diff.
        if not files:
            checks.append(VerificationCheck("claimed_changes_present", False,
                                            output="no changed files supplied"))
        for file in files:
            try:
                raw = Path(file)
                if raw.is_absolute() or ".." in raw.parts or not raw.parts:
                    raise PolicyError("expected a repository-relative file path")
                target = resolve_path(self.workspace, raw, allow_missing=True)
                if target == self.workspace or target.is_dir():
                    raise PolicyError("expected a file, not a directory")
                relative = target.relative_to(self.workspace).as_posix()
            except (PolicyError, ValueError, OSError, RuntimeError) as exc:
                checks.append(VerificationCheck(
                    f"changed_file:{file}", False, output=f"invalid claimed file: {exc}",
                ))
                continue
            safe_files.append(relative)
            status = self.runner.run(
                ("git", "status", "--porcelain=v1", "--untracked-files=all", "--", relative),
                task_id=task_id,
            )
            changed = status.returncode == 0 and bool(status.stdout.strip())
            digest = "deleted_or_missing"
            if target.is_file():
                try:
                    digest = sha256(target.read_bytes()).hexdigest()
                except OSError:
                    changed = False
                    digest = "unreadable"
            checks.append(VerificationCheck(
                f"changed_file:{relative}", changed, status.argv, status.returncode,
                f"git_status={status.stdout.strip()}; sha256={digest}",
            ))

        # Verification of a candidate requires observed test/check execution;
        # an empty command list cannot advance a task to approval.
        checks.append(VerificationCheck(
            "verification_commands_present", bool(steps),
            output=f"{len(steps)} explicit verification command(s)",
        ))
        checks.append(VerificationCheck(
            "substantive_validation_present",
            any(_is_substantive_check(command) for command in steps),
            output="tests, lint, typecheck or syntax verification required",
        ))

        security = scan_paths(self.workspace, safe_files)
        critical = [f for f in security if f.severity in {"critical", "high"}]
        checks.append(VerificationCheck(
            "security_scan",
            not critical,
            output="; ".join(f"{f.kind}:{f.path or '-'}" for f in security),
        ))
        if critical:
            reasons.append("security scan found high-severity candidate changes")

        status = self.runner.run(
            ("git", "status", "--short"),
            task_id=task_id,
        )
        checks.append(VerificationCheck(
            "git_status",
            status.returncode == 0,
            status.argv,
            status.returncode,
            status.stdout or status.stderr,
        ))

        diff = self.runner.run(
            ("git", "diff", "--check", "--", *safe_files),
            task_id=task_id,
        )
        checks.append(VerificationCheck(
            "git_diff_check",
            diff.returncode == 0,
            diff.argv,
            diff.returncode,
            diff.stdout or diff.stderr,
        ))
        staged_diff = self.runner.run(
            ("git", "diff", "--cached", "--check", "--", *safe_files),
            task_id=task_id,
        )
        checks.append(VerificationCheck(
            "git_staged_diff_check", staged_diff.returncode == 0,
            staged_diff.argv, staged_diff.returncode,
            staged_diff.stdout or staged_diff.stderr,
        ))

        for command in steps:
            result = self.runner.run(
                tuple(command),
                task_id=task_id,
            )
            checks.append(VerificationCheck(
                "command:" + " ".join(result.argv[:3]),
                result.returncode == 0,
                result.argv,
                result.returncode,
                result.stdout or result.stderr,
            ))

        if objective_terms:
            joined = "\n".join(files).lower()
            missing = [
                term for term in objective_terms
                if str(term).lower() not in joined
            ]
            if missing:
                warnings.append(
                    "objective terms not reflected in changed file names: "
                    + ", ".join(missing)
                )

        failed = [check for check in checks if not check.passed]
        if failed:
            verdict = VerificationVerdict.FAIL
            reasons.append(
                f"{len(failed)} verification check(s) failed"
            )
        elif warnings:
            verdict = VerificationVerdict.PASS_WITH_WARNINGS
        else:
            verdict = VerificationVerdict.PASS

        return VerificationReport(
            verdict,
            tuple(checks),
            tuple(reasons),
            tuple(warnings),
        )
