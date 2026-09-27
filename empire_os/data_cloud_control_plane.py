"""Private-first Empire Data Cloud control-plane contracts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ProjectState(str, Enum):
    PLANNED = "planned"
    PROVISIONING = "provisioning"
    READY_PRIVATE = "ready_private"
    PUBLIC_API_APPROVED = "public_api_approved"
    SUSPENDED = "suspended"


@dataclass(frozen=True)
class DataCloudProject:
    project_id: str
    tenant_id: str
    state: ProjectState = ProjectState.PLANNED
    region: str = "eu"
    public_api_enabled: bool = False

    def validate(self) -> None:
        if not self.project_id.strip() or not self.tenant_id.strip():
            raise ValueError("project_id and tenant_id are required")
        if self.public_api_enabled and self.state is not ProjectState.PUBLIC_API_APPROVED:
            raise ValueError("public API requires approved project state")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload
