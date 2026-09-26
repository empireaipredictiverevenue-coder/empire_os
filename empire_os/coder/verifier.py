"""Independent verification stage for Empire Coder."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import (
    VerificationCheck,
    VerificationReport,
    VerificationVerdict,
)
from .policy import resolve_workspace
from .runner import SafeCommandRunner
from .security import scan_paths


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
        files = tuple(dict.fromkeys(str(p) for p in changed_files))
        checks: list[VerificationCheck] = []
        reasons: list[str] = []
        warnings: list[str] = []

        security = scan_paths(self.workspace, files)
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
            ("git", "diff", "--check"),
            task_id=task_id,
        )
        checks.append(VerificationCheck(
            "git_diff_check",
            diff.returncode == 0,
            diff.argv,
            diff.returncode,
            diff.stdout or diff.stderr,
        ))

        for command in commands:
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
