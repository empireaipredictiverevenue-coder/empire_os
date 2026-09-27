"""Least-privilege capability contracts for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    EVENT_APPEND = "event_append"
    VECTOR_SEARCH = "vector_search"
    MIGRATE_SCHEMA = "migrate_schema"
    PLATFORM_ADMIN = "platform_admin"


CONSEQUENTIAL_CAPABILITIES = frozenset({
    Capability.MIGRATE_SCHEMA,
    Capability.PLATFORM_ADMIN,
})


@dataclass(frozen=True)
class ServiceIdentity:
    identity_id: str
    capabilities: frozenset[Capability]
    tenant_id: str | None = None

    def validate(self) -> None:
        if not self.identity_id.strip():
            raise ValueError("identity_id required")
        if Capability.PLATFORM_ADMIN in self.capabilities and self.tenant_id is not None:
            raise ValueError("platform admin identity cannot masquerade as tenant identity")


def require_capability(identity: ServiceIdentity, capability: Capability) -> None:
    identity.validate()
    if capability not in identity.capabilities:
        raise PermissionError(f"capability denied: {capability.value}")


def autonomous_capability_allowed(capability: Capability) -> bool:
    return capability not in CONSEQUENTIAL_CAPABILITIES
