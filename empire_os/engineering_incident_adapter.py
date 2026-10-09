"""Fail-closed engineering regression incident adapter.

Transforms retained pytest output into reportable incidents. Never executes repairs.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re


@dataclass(frozen=True)
class RegressionIncident:
    code: str
    severity: str
    component: str
    summary: str
    repairable: bool = False
    commercial_priority: int = 65
    execution_authority: str = "none"

    def as_dict(self) -> dict:
        return asdict(self)


def inspect_pytest_log(path: str | Path) -> dict:
    """Report PASS/FAIL/INCOMPLETE without treating partial logs as success."""
    path = Path(path)
    if not path.is_file():
        return {"status": "MISSING", "incidents": [
            RegressionIncident("regression_evidence_missing", "warning",
                               "engineering_tests", "Regression log missing").as_dict()
        ]}
    text = path.read_text(encoding="utf-8", errors="replace")
    failure = re.search(r"(?m)^=+ .*?failed.*?=+$", text)
    passed = re.search(r"(?m)^(?:=+ )?\d+ passed(?:, .*?)? in [\d.]+s(?: \([^\n)]*\))?(?: =+)?$", text)
    if failure or re.search(r"(?m)^FAILED \S+", text):
        cases = re.findall(r"(?m)^FAILED (\S+)", text)
        return {"status": "FAILED", "failed_cases": cases,
                "incidents": [RegressionIncident(
                    "engineering_regression_failed", "warning", "engineering_tests",
                    "Regression failure requires code/test triage; no automatic production repair"
                ).as_dict()]}
    if passed:
        return {"status": "PASSED", "incidents": []}
    return {"status": "INCOMPLETE", "incidents": [
        RegressionIncident("regression_evidence_incomplete", "warning",
                           "engineering_tests", "No final pytest summary").as_dict()
    ]}
