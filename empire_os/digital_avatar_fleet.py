"""Tenant-scoped control plane for Digital Avatar clone fleets.

This module grants no meeting, speech, commercial, payment or revenue authority.
It reuses authenticated tenant membership and the existing single-avatar runtime.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.saas_scale import TenantMembership
from empire_os.tenant_isolation import (
    TenantResourceRef,
    authorize_tenant_resource,
)


class AvatarFleetOperation(str, Enum):
    READ = "read"
    PREPARE_RUNTIME = "prepare_runtime"
    MANAGE_BINDING = "manage_binding"


_PERMISSION = {
    AvatarFleetOperation.READ: "read",
    AvatarFleetOperation.PREPARE_RUNTIME: "operate",
    AvatarFleetOperation.MANAGE_BINDING: "admin",
}
@dataclass(frozen=True)
class AvatarFleetBinding:
    tenant_id: str
    avatar_id: str
    owner_ref: str
    owner_name: str
    owner_consent_evidence_ref: str
    capability_labels: tuple[str, ...] = ()
    status: str = "active"

    def validate(self) -> None:
        required = (
            self.tenant_id,
            self.avatar_id,
            self.owner_ref,
            self.owner_name,
            self.owner_consent_evidence_ref,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("fleet tenant/avatar/owner consent binding required")
        if self.status not in {"active", "disabled"}:
            raise ValueError("unsupported fleet binding status")
        clean = tuple(str(value).strip() for value in self.capability_labels)
        if any(not value for value in clean):
            raise ValueError("fleet capability labels must be non-empty")
        if len(clean) != len(set(clean)):
            raise ValueError("fleet capability labels must be unique")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
@dataclass(frozen=True)
class AvatarFleetAccessDecision:
    allowed: bool
    reason: str
    tenant_id: str | None
    avatar_id: str
    user_id: str | None
    operation: AvatarFleetOperation
    cross_tenant: bool
    execution_authority: str = "none"
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["operation"] = self.operation.value
        return value


@dataclass(frozen=True)
class AvatarFleetRuntimeBinding:
    tenant_id: str
    avatar_id: str
    owner_ref: str
    owner_name: str
    capability_labels: tuple[str, ...]
    membership_user_id: str
    membership_role: str
    owner_consent_evidence_ref: str
    runtime_authority: str = "observe"
    execution_authority: str = "none"
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
def authorize_avatar_fleet_access(
    *,
    membership: TenantMembership,
    binding: AvatarFleetBinding,
    operation: AvatarFleetOperation,
) -> AvatarFleetAccessDecision:
    binding.validate()
    permission = _PERMISSION[operation]
    access = authorize_tenant_resource(
        membership=membership,
        resource=TenantResourceRef(
            tenant_id=binding.tenant_id,
            resource_type="digital_avatar",
            resource_id=binding.avatar_id,
        ),
        permission=permission,
    )
    if not access.allowed:
        return AvatarFleetAccessDecision(
            allowed=False,
            reason=access.reason,
            tenant_id=access.tenant_id,
            avatar_id=binding.avatar_id,
            user_id=access.user_id,
            operation=operation,
            cross_tenant=access.cross_tenant,
        )
    if binding.status != "active":
        return AvatarFleetAccessDecision(
            allowed=False,
            reason="avatar_binding_disabled",
            tenant_id=membership.tenant_id,
            avatar_id=binding.avatar_id,
            user_id=membership.user_id,
            operation=operation,
            cross_tenant=False,
        )
    return AvatarFleetAccessDecision(
        allowed=True,
        reason="tenant_avatar_access_authorized",
        tenant_id=membership.tenant_id,
        avatar_id=binding.avatar_id,
        user_id=membership.user_id,
        operation=operation,
        cross_tenant=False,
    )
def prepare_avatar_fleet_runtime(
    *,
    membership: TenantMembership,
    binding: AvatarFleetBinding,
    identity: DigitalAvatarIdentity,
) -> AvatarFleetRuntimeBinding:
    decision = authorize_avatar_fleet_access(
        membership=membership,
        binding=binding,
        operation=AvatarFleetOperation.PREPARE_RUNTIME,
    )
    if not decision.allowed:
        raise PermissionError(decision.reason)

    identity.validate()
    if identity.avatar_id != binding.avatar_id:
        raise PermissionError("avatar_identity_binding_mismatch")
    if identity.owner_name.strip() != binding.owner_name.strip():
        raise PermissionError("avatar_owner_binding_mismatch")
    if (
        identity.owner_consent_evidence_ref.strip()
        != binding.owner_consent_evidence_ref.strip()
    ):
        raise PermissionError("avatar_owner_consent_binding_mismatch")

    return AvatarFleetRuntimeBinding(
        tenant_id=binding.tenant_id,
        avatar_id=binding.avatar_id,
        owner_ref=binding.owner_ref,
        owner_name=binding.owner_name,
        capability_labels=binding.capability_labels,
        membership_user_id=membership.user_id,
        membership_role=membership.role,
        owner_consent_evidence_ref=binding.owner_consent_evidence_ref,
    )
def normalize_avatar_fleet_bindings(
    bindings: Iterable[AvatarFleetBinding],
) -> tuple[AvatarFleetBinding, ...]:
    """Dedupe identical bindings and reject ambiguous tenant/avatar ownership."""
    by_key: dict[tuple[str, str], AvatarFleetBinding] = {}
    tenant_by_avatar: dict[str, str] = {}

    for binding in bindings:
        binding.validate()
        tenant = binding.tenant_id.strip()
        avatar = binding.avatar_id.strip()
        prior_tenant = tenant_by_avatar.get(avatar)
        if prior_tenant is not None and prior_tenant != tenant:
            raise ValueError("avatar_id_cross_tenant_binding_conflict")
        tenant_by_avatar[avatar] = tenant

        key = (tenant, avatar)
        current = by_key.get(key)
        if current is None:
            by_key[key] = binding
            continue
        if current != binding:
            raise ValueError("avatar_binding_conflict")

    return tuple(
        by_key[key]
        for key in sorted(by_key)
    )
