"""Small deterministic benchmark harness for Empire Coder."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import VerificationCheck
from .runner import SafeCommandRunner


@dataclass(frozen=True)
class BenchmarkResult:
    passed: int
    failed: int
    checks: tuple[VerificationCheck, ...]


class BenchmarkHarness:
    def __init__(self, runner: SafeCommandRunner) -> None:
        self.runner = runner

    def run(
        self,
        *,
        task_id: str,
        commands: Iterable[Iterable[str]],
    ) -> BenchmarkResult:
        checks: list[VerificationCheck] = []
        for command in commands:
            result = self.runner.run(
                tuple(command),
                task_id=task_id,
            )
            checks.append(VerificationCheck(
                "benchmark:" + " ".join(result.argv[:3]),
                result.returncode == 0,
                result.argv,
                result.returncode,
                result.stdout or result.stderr,
            ))
        passed = sum(check.passed for check in checks)
        return BenchmarkResult(
            passed,
            len(checks) - passed,
            tuple(checks),
        )
