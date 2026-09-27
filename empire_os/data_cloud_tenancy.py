"""Tenant identity and isolation contracts for Empire Data Cloud."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str
    project_id: str

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id required")
        if not self.actor_id.strip():
            raise ValueError("actor_id required")
        if not self.project_id.strip():
            raise ValueError("project_id required")


def same_tenant(left: TenantContext, right: TenantContext) -> bool:
    left.validate()
    right.validate()
    return (
        left.tenant_id == right.tenant_id
        and left.project_id == right.project_id
    )


def require_same_tenant(left: TenantContext, right: TenantContext) -> None:
    if not same_tenant(left, right):
        raise PermissionError("cross-tenant access denied")
