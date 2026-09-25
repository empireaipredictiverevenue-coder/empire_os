"""Canonical Agent & Tool Execution Plane for EmpireOS.

Architecture:
docs/AGENT_TOOL_EXECUTION_PLANE_ARCHITECTURE.md

This module is routing/governance state only. It does not execute tools, grant
commercial authority, move funds, send outbound, mutate canonical data, or
recognize revenue.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


AUTHORITY_LEVELS = (
    "observe",
    "internal_write",
    "governed_external",
    "founder_gate",
)

WORKER_KINDS = (
    "builder",
    "workspace",
    "sensor",
    "verifier",
    "router",
    "specialist",
)


@dataclass(frozen=True)
class WorkerSpec:
    key: str
    name: str
    kind: str
    capabilities: tuple[str, ...]
    max_authority: str
    isolation: str
    mutates_repo: bool = False
    mutates_canonical_data: bool = False
    sends_external: bool = False
    moves_funds: bool = False
    recognizes_revenue: bool = False
    production_deploy: bool = False
    preferred_for: tuple[str, ...] = ()
    fallback_for: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.key.strip():
            raise ValueError("worker key required")
        if self.kind not in WORKER_KINDS:
            raise ValueError("unsupported worker kind")
        if self.max_authority not in AUTHORITY_LEVELS:
            raise ValueError("unsupported worker authority")
        if not self.capabilities:
            raise ValueError("worker capabilities required")
        if (
            self.mutates_canonical_data
            or self.sends_external
            or self.moves_funds
            or self.recognizes_revenue
            or self.production_deploy
        ):
            raise ValueError(
                "execution-plane workers cannot hold consequential authority"
            )

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class ExecutionJob:
    job_id: str
    capability: str
    department: str
    risk_class: str = "low"
    authority: str = "observe"
    source_ref: str = ""
    allowed_paths: tuple[str, ...] = ()
    evidence_domains: tuple[str, ...] = ()
    success_condition: str = ""
    required_tests: tuple[str, ...] = ()
    traceparent: str | None = None

    def validate(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id required")
        if not self.capability.strip():
            raise ValueError("capability required")
        if not self.department.strip():
            raise ValueError("department required")
        if self.risk_class not in {
            "low",
            "medium",
            "high",
            "consequential",
        }:
            raise ValueError("unsupported risk_class")
        if self.authority not in AUTHORITY_LEVELS:
            raise ValueError("unsupported authority")
        if self.authority in {"governed_external", "founder_gate"}:
            raise ValueError(
                "execution plane accepts observe/internal_write jobs only"
            )

    @property
    def requires_mutation_lease(self) -> bool:
        return self.authority == "internal_write" and bool(self.allowed_paths)


@dataclass(frozen=True)
class RouteDecision:
    job_id: str
    worker_key: str | None
    capability: str
    eligible: bool
    reason: str
    requires_mutation_lease: bool
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_worker_registry() -> tuple[WorkerSpec, ...]:
    """Evidence-backed roles from the canonical architecture."""
    workers = (
        WorkerSpec(
            key="hermes",
            name="Hermes Governed Coder",
            kind="builder",
            capabilities=(
                "backend_code",
                "api_integration",
                "refactor",
                "tests",
                "documentation",
            ),
            max_authority="internal_write",
            isolation="isolated_git_worktree",
            mutates_repo=True,
            preferred_for=(
                "backend_code",
                "api_integration",
                "refactor",
            ),
        ),
        WorkerSpec(
            key="pi",
            name="Pi Sandboxed Coder",
            kind="builder",
            capabilities=(
                "backend_code",
                "parallel_backend_code",
                "frontend_code",
                "refactor",
                "tests",
                "documentation",
            ),
            max_authority="internal_write",
            isolation="ephemeral_worktree_sandbox",
            mutates_repo=True,
            preferred_for=(
                "parallel_backend_code",
                "frontend_code",
                "tests",
                "documentation",
            ),
            fallback_for=("backend_code", "refactor"),
        ),
        WorkerSpec(
            key="empire_coder",
            name="Empire Coder",
            kind="builder",
            capabilities=(
                "backend_code",
                "tests",
                "documentation",
                "verification",
            ),
            max_authority="internal_write",
            isolation="governed_local_queue",
            mutates_repo=True,
            preferred_for=("verification",),
            fallback_for=("backend_code", "tests", "documentation"),
        ),
        WorkerSpec(
            key="space_agent",
            name="Space Agent Workspace Builder",
            kind="workspace",
            capabilities=(
                "founder_workspace",
                "department_workspace",
                "internal_ui",
            ),
            max_authority="internal_write",
            isolation="separate_workspace_service",
            mutates_repo=False,
            preferred_for=(
                "founder_workspace",
                "department_workspace",
                "internal_ui",
            ),
        ),
        WorkerSpec(
            key="agent_reach",
            name="Agent Reach Sensor",
            kind="sensor",
            capabilities=(
                "public_research",
                "social_research",
                "youtube_research",
                "github_research",
                "source_health",
            ),
            max_authority="observe",
            isolation="dedicated_read_search_runtime",
            preferred_for=(
                "public_research",
                "social_research",
                "youtube_research",
                "github_research",
            ),
        ),
        WorkerSpec(
            key="swarm_v6",
            name="Swarm V6",
            kind="verifier",
            capabilities=("verification", "integration_qa"),
            max_authority="observe",
            isolation="deterministic_verify_queue",
            preferred_for=("integration_qa",),
        ),
        WorkerSpec(
            key="needle",
            name="Needle Router",
            kind="router",
            capabilities=("tool_routing",),
            max_authority="observe",
            isolation="shadow_router",
            preferred_for=("tool_routing",),
        ),
        WorkerSpec(
            key="laya",
            name="Laya Specialist",
            kind="specialist",
            capabilities=("reply_negative_unsubscribe_shadow",),
            max_authority="observe",
            isolation="loopback_onnx_sidecar",
            preferred_for=("reply_negative_unsubscribe_shadow",),
        ),
    )
    for worker in workers:
        worker.validate()
    return workers


def worker_registry_snapshot() -> dict[str, Any]:
    workers = default_worker_registry()
    return {
        "schema_version": "empire.agent-tool-execution-plane.v1",
        "workers": [worker.as_dict() for worker in workers],
        "worker_count": len(workers),
        "authority": {
            "external_send": False,
            "fund_movement": False,
            "payment_confirmation": False,
            "revenue_recognition": False,
            "production_deploy": False,
            "authority_expansion": False,
        },
        "canonical_authority_remains": (
            "Empire Control Fabric / governed domain systems"
        ),
    }


def route_execution_job(
    job: ExecutionJob,
    *,
    registry: tuple[WorkerSpec, ...] | None = None,
    unavailable_workers: frozenset[str] = frozenset(),
    leased_worker_keys: frozenset[str] = frozenset(),
) -> RouteDecision:
    job.validate()
    workers = registry or default_worker_registry()

    candidates: list[tuple[int, str, WorkerSpec]] = []
    for worker in workers:
        worker.validate()
        if worker.key in unavailable_workers:
            continue
        if job.capability not in worker.capabilities:
            continue
        if job.authority == "internal_write" and worker.max_authority != "internal_write":
            continue
        if job.requires_mutation_lease and worker.key in leased_worker_keys:
            continue

        score = 0
        if job.capability in worker.preferred_for:
            score += 100
        if job.capability in worker.fallback_for:
            score += 25
        if job.authority == "internal_write" and worker.mutates_repo:
            score += 10
        if worker.kind == "verifier" and job.capability == "verification":
            score += 20
        candidates.append((-score, worker.key, worker))

    if not candidates:
        return RouteDecision(
            job_id=job.job_id,
            worker_key=None,
            capability=job.capability,
            eligible=False,
            reason="no_policy_eligible_worker",
            requires_mutation_lease=job.requires_mutation_lease,
        )

    _, _, selected = sorted(candidates)[0]
    return RouteDecision(
        job_id=job.job_id,
        worker_key=selected.key,
        capability=job.capability,
        eligible=True,
        reason="capability_policy_match",
        requires_mutation_lease=(
            job.requires_mutation_lease and selected.mutates_repo
        ),
    )


def execution_plane_authority_contract() -> Mapping[str, bool]:
    return {
        "worker_can_send_outbound": False,
        "worker_can_accept_terms": False,
        "worker_can_move_funds": False,
        "worker_can_confirm_payment": False,
        "worker_can_recognize_revenue": False,
        "worker_can_expand_authority": False,
        "worker_can_deploy_production_directly": False,
        "canonical_truth_remains_empire": True,
    }
