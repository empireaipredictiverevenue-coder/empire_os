"""Typed records for the Empire Coder control plane."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class TaskStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    BLOCKED = "blocked"
    VERIFYING = "verifying"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPhase(str, Enum):
    UNDERSTAND = "UNDERSTAND"
    SEARCH_REPO = "SEARCH_REPO"
    PLAN = "PLAN"
    PATCH = "PATCH"
    RUN = "RUN"
    TEST = "TEST"
    DIAGNOSE = "DIAGNOSE"
    REPAIR = "REPAIR"
    VERIFY = "VERIFY"
    DIFF = "DIFF"
    APPROVAL = "APPROVAL"


class ToolDecision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class VerificationVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"


@dataclass
class CoderTask:
    id: str
    objective: str
    workspace: str
    blueprint_path: str
    status: TaskStatus = TaskStatus.PLANNED
    phase: TaskPhase = TaskPhase.UNDERSTAND
    plan: list[str] = field(default_factory=list)
    plan_steps: list[dict[str, Any]] = field(default_factory=list)
    completed_steps: list[str] = field(default_factory=list)
    unresolved_issues: list[str] = field(default_factory=list)
    discovered_files: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    tests_required: list[str] = field(default_factory=list)
    verification_status: VerificationVerdict | None = None
    pending_approval: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["phase"] = self.phase.value
        data["verification_status"] = (
            self.verification_status.value if self.verification_status else None
        )
        return data


@dataclass(frozen=True)
class ToolRunResult:
    tool: str
    argv: tuple[str, ...]
    decision: ToolDecision
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    mutation_occurred: bool = False
    timed_out: bool = False
    redacted: bool = True

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["decision"] = self.decision.value
        return data


@dataclass(frozen=True)
class RepoHit:
    path: str
    line: int | None
    text: str
    kind: str = "text"


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reason: str
    local: bool = False
    cost_tier: int = 0


@dataclass(frozen=True)
class VerificationCheck:
    name: str
    passed: bool
    command: tuple[str, ...] = ()
    returncode: int | None = None
    output: str = ""


@dataclass(frozen=True)
class VerificationReport:
    verdict: VerificationVerdict
    checks: tuple[VerificationCheck, ...]
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "checks": [asdict(check) for check in self.checks],
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }
