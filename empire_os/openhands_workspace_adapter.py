"""Optional OpenHands workspace readiness contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SCHEMA_VERSION = "empire.openhands-workspace.v1"


@dataclass(frozen=True)
class OpenHandsWorkspaceRequest:
    job_id: str
    objective: str
    allowed_paths: tuple[str, ...]
    workspace_mode: str = "ephemeral"

    def validate(self) -> None:
        if not self.job_id.strip():
            raise ValueError("job_id required")
        if not self.objective.strip():
            raise ValueError("objective required")
        if not self.allowed_paths:
            raise ValueError("allowed_paths required")
        if self.workspace_mode not in {"ephemeral", "disposable_clone"}:
            raise ValueError("unsupported workspace_mode")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_openhands_workspace_contract(
    packet: OpenHandsWorkspaceRequest,
) -> dict[str, Any]:
    packet.validate()
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": packet.job_id,
        "objective": packet.objective,
        "workspace_mode": packet.workspace_mode,
        "allowed_paths": list(packet.allowed_paths),
        "disposable": True,
        "production_repo_writable": False,
        "workspace_contract_ready": True,
        "mutation_capability_proven": False,
        "mutation_probe_required": True,
        "independent_verification_required": True,
        "production_deploy": False,
        "execution_authority": "none",
    }
