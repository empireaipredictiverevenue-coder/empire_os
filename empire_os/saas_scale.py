"""Phase 16 SaaS / Network Scale access and usage foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ROLE_PERMISSIONS = {
    "owner": frozenset({"read", "admin", "manage_members"}),
    "admin": frozenset({"read", "admin", "manage_members"}),
    "operator": frozenset({"read", "operate"}),
    "analyst": frozenset({"read"}),
    "viewer": frozenset({"read"}),
}


@dataclass(frozen=True)
class TenantMembership:
    tenant_id: str
    user_id: str
    role: str
    status: str = "active"

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.user_id.strip():
            raise ValueError("tenant_id and user_id are required")
        if self.role not in ROLE_PERMISSIONS:
            raise ValueError("unsupported tenant role")
        if self.status not in {"active", "disabled"}:
            raise ValueError("unsupported membership status")

    def can(self, permission: str) -> bool:
        self.validate()
        if self.status != "active":
            return False
        return permission in ROLE_PERMISSIONS[self.role]

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class UsageObservation:
    tenant_id: str
    metric: str
    value: int
    period: str
    source: str

    def validate(self) -> None:
        if not self.tenant_id.strip() or not self.metric.strip():
            raise ValueError("tenant_id and metric are required")
        if self.value < 0:
            raise ValueError("usage value must be nonnegative")
        if not self.period.strip() or not self.source.strip():
            raise ValueError("usage period and source are required")
