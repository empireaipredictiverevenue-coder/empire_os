"""Verification planning for execution-plane candidate work."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from empire_os.coder import EmpireCoder
from empire_os.coder.jobs import JobKind, LocalJobQueue
from empire_os.swarm_v6 import LANES


@dataclass(frozen=True)
class VerificationPlan:
    request_id: str
    swarm_lanes: tuple[str, ...]
    pytest_targets: tuple[str, ...]
    promptfoo_required: bool
    promptfoo_config: str | None
    independent_verification_required: bool = True
    production_promotion_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _path_matches_scope(path: str, scope: str) -> bool:
    a = str(path or "").strip().replace("\\", "/").rstrip("/")
    b = str(scope or "").strip().replace("\\", "/").rstrip("/")
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def plan_candidate_verification(
    *,
    request_id: str,
    allowed_paths: tuple[str, ...],
    required_tests: tuple[str, ...],
    ai_behavior_change: bool = False,
) -> VerificationPlan:
    lanes: list[str] = []
    for lane in LANES:
        if any(
            _path_matches_scope(changed, scope)
            for changed in lane.changed_files
            for scope in allowed_paths
        ):
            lanes.append(lane.key)

    if not lanes:
        lanes.append("integration_qa")

    return VerificationPlan(
        request_id=request_id,
        swarm_lanes=tuple(dict.fromkeys(lanes)),
        pytest_targets=tuple(dict.fromkeys(required_tests)),
        promptfoo_required=bool(ai_behavior_change),
        promptfoo_config=(
            "evals/empire_core_policy/promptfooconfig.yaml"
            if ai_behavior_change
            else None
        ),
    )


def enqueue_swarm_verification(
    repo_root: str | Path,
    plan: VerificationPlan,
) -> list[dict[str, str]]:
    root = Path(repo_root).resolve()
    runtime = root / "runtime/coder"
    coder = EmpireCoder(root, runtime_root=runtime)
    queue = LocalJobQueue(root, runtime_root=runtime)
    by_key = {lane.key: lane for lane in LANES}
    queued: list[dict[str, str]] = []

    for lane_key in plan.swarm_lanes:
        lane = by_key.get(lane_key)
        tests = (
            plan.pytest_targets
            if plan.pytest_targets
            else tuple(lane.tests if lane is not None else ())
        )
        task = coder.create_task(
            (
                f"Execution-plane independent verification for {plan.request_id}. "
                f"Lane={lane_key}. Verify repository evidence only. "
                "Do not mutate production or expand authority."
            ),
            blueprint_path="docs/BLUEPRINT_V6.md",
        )
        job = queue.enqueue(
            task_id=task.id,
            kind=JobKind.VERIFY,
            payload={
                "execution_plane_request_id": plan.request_id,
                "swarm_lane": lane_key,
                "tests": list(tests),
                "production_mutation": False,
                "execution_authority": "none",
            },
            priority=90,
        )
        queued.append({
            "lane": lane_key,
            "task_id": task.id,
            "job_id": job.id,
        })
    return queued
