"""Redacted tenant-scoped read model for Digital Avatar Clone Fleet."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from empire_os.digital_avatar_fleet import (
    AvatarFleetBinding,
    normalize_avatar_fleet_bindings,
)
from empire_os.saas_scale import TenantMembership


@dataclass(frozen=True)
class AvatarFleetReadItem:
    avatar_id: str
    owner_name: str
    capability_labels: tuple[str, ...]
    status: str
    consent_verified: bool
    runtime_authority: str = "observe"
    execution_authority: str = "none"
    speech_execution_allowed: bool = False
    commercial_execution_allowed: bool = False
    payment_execution_allowed: bool = False
    revenue_recognition_allowed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
@dataclass(frozen=True)
class AvatarFleetReadSnapshot:
    tenant_id: str
    user_id: str
    role: str
    avatars: tuple[AvatarFleetReadItem, ...]
    execution_authority: str = "none"
    mutation_allowed: bool = False
    meeting_execution_allowed: bool = False
    cross_tenant_metadata_included: bool = False

    @property
    def avatar_count(self) -> int:
        return len(self.avatars)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["avatar_count"] = self.avatar_count
        return value


def build_avatar_fleet_read_snapshot(
    *,
    membership: TenantMembership,
    bindings: Iterable[AvatarFleetBinding],
) -> AvatarFleetReadSnapshot:
    membership.validate()
    if not membership.can("read"):
        raise PermissionError("membership_read_permission_denied")

    normalized = normalize_avatar_fleet_bindings(bindings)
    own = [
        binding
        for binding in normalized
        if binding.tenant_id == membership.tenant_id
    ]
    items = tuple(
        AvatarFleetReadItem(
            avatar_id=binding.avatar_id,
            owner_name=binding.owner_name,
            capability_labels=binding.capability_labels,
            status=binding.status,
            consent_verified=bool(
                binding.owner_consent_evidence_ref.strip()
            ),
        )
        for binding in sorted(
            own,
            key=lambda value: (value.avatar_id, value.owner_name),
        )
    )
    return AvatarFleetReadSnapshot(
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        role=membership.role,
        avatars=items,
    )


def get_avatar_fleet_read_item(
    *,
    membership: TenantMembership,
    bindings: Iterable[AvatarFleetBinding],
    avatar_id: str,
) -> AvatarFleetReadItem | None:
    clean = str(avatar_id or "").strip()
    if not clean:
        raise ValueError("avatar_id required")
    snapshot = build_avatar_fleet_read_snapshot(
        membership=membership,
        bindings=bindings,
    )
    for item in snapshot.avatars:
        if item.avatar_id == clean:
            return item
    return None
