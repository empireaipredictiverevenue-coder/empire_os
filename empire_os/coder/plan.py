"""Durable dependency-aware task planning."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Iterable

from .models import TaskPhase


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class PlanStep:
    id: str
    name: str
    phase: TaskPhase
    depends_on: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: str = ""

    def as_dict(self) -> dict:
        data = asdict(self)
        data["phase"] = self.phase.value
        data["status"] = self.status.value
        return data


@dataclass
class TaskPlan:
    steps: list[PlanStep] = field(default_factory=list)

    def validate(self) -> None:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step ids must be unique")
        known = set(ids)
        for step in self.steps:
            unknown = set(step.depends_on) - known
            if unknown:
                raise ValueError(
                    f"step {step.id} has unknown dependencies: {sorted(unknown)}"
                )
        self._ensure_acyclic()

    def ready(self) -> list[PlanStep]:
        completed = {
            step.id for step in self.steps
            if step.status is PlanStepStatus.COMPLETED
        }
        return [
            step for step in self.steps
            if step.status is PlanStepStatus.PENDING
            and set(step.depends_on).issubset(completed)
        ]

    def parallel_groups(self) -> list[list[PlanStep]]:
        """Group ready steps that do not claim the same files."""
        groups: list[list[PlanStep]] = []
        for step in self.ready():
            placed = False
            owned = set(step.files)
            for group in groups:
                group_files = {
                    path for member in group for path in member.files
                }
                if owned.isdisjoint(group_files):
                    group.append(step)
                    placed = True
                    break
            if not placed:
                groups.append([step])
        return groups

    def mark(
        self,
        step_id: str,
        status: PlanStepStatus,
        *,
        result: str = "",
    ) -> None:
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                step.result = result
                return
        raise KeyError(step_id)

    def _ensure_acyclic(self) -> None:
        graph = {s.id: set(s.depends_on) for s in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise ValueError("task plan contains a cycle")
            visiting.add(node)
            for parent in graph[node]:
                visit(parent)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)
