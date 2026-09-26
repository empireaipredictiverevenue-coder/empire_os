"""Phase 16 tenant-isolation access checks."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.saas_scale import TenantMembership


@dataclass(frozen=True)
class TenantResourceRef:
    tenant_id: str
    resource_type: str
    resource_id: str

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("resource tenant_id required")
        if not self.resource_type.strip() or not self.resource_id.strip():
            raise ValueError("resource identity required")


@dataclass(frozen=True)
class TenantAccessDecision:
    allowed: bool
    reason: str
    tenant_id: str | None
    user_id: str | None
    permission: str
    cross_tenant: bool
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def authorize_tenant_resource(
    *,
    membership: TenantMembership,
    resource: TenantResourceRef,
    permission: str,
) -> TenantAccessDecision:
    membership.validate()
    resource.validate()
    requested = str(permission or "").strip()
    if not requested:
        raise ValueError("permission required")

    cross_tenant = membership.tenant_id != resource.tenant_id
    if cross_tenant:
        return TenantAccessDecision(
            allowed=False,
            reason="cross_tenant_access_denied",
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            permission=requested,
            cross_tenant=True,
        )

    if not membership.can(requested):
        return TenantAccessDecision(
            allowed=False,
            reason="membership_permission_denied",
            tenant_id=membership.tenant_id,
            user_id=membership.user_id,
            permission=requested,
            cross_tenant=False,
        )

    return TenantAccessDecision(
        allowed=True,
        reason="tenant_membership_authorized",
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        permission=requested,
        cross_tenant=False,
    )
