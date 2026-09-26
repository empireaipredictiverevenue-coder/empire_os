"""Phase 16 developer/API access readiness preview."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.saas_scale import TenantMembership


ALLOWED_READ_SCOPES = frozenset({
    "read:predictions",
    "read:analytics",
    "read:crm",
    "read:search",
    "read:conversations",
})

ADMIN_ROLES = frozenset({"owner", "admin"})


@dataclass(frozen=True)
class ApiAccessEvidence:
    membership: TenantMembership
    active_subscription: bool
    tenant_isolation_verified: bool
    requested_scopes: tuple[str, ...]
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        self.membership.validate()
        if not self.requested_scopes:
            raise ValueError("at least one API scope required")
        if not self.evidence_refs:
            raise ValueError("API access readiness requires evidence")


@dataclass(frozen=True)
class ApiAccessReadiness:
    tenant_id: str
    user_id: str
    issuance_ready: bool
    approved_scopes: tuple[str, ...]
    rejected_scopes: tuple[str, ...]
    blockers: tuple[str, ...]
    approval_required: bool = True
    execution_authority: str = "none"
    api_key_issuance: bool = False
    api_key_revocation: bool = False
    secret_material_generated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_api_access_readiness(
    evidence: ApiAccessEvidence,
) -> ApiAccessReadiness:
    evidence.validate()
    membership = evidence.membership
    blockers: list[str] = []

    if membership.status != "active":
        blockers.append("membership_not_active")
    if membership.role not in ADMIN_ROLES:
        blockers.append("admin_role_required")
    if not evidence.active_subscription:
        blockers.append("active_subscription_required")
    if not evidence.tenant_isolation_verified:
        blockers.append("tenant_isolation_not_verified")

    approved = tuple(sorted(
        scope for scope in set(evidence.requested_scopes)
        if scope in ALLOWED_READ_SCOPES
    ))
    rejected = tuple(sorted(
        scope for scope in set(evidence.requested_scopes)
        if scope not in ALLOWED_READ_SCOPES
    ))
    if rejected:
        blockers.append("unsupported_or_mutating_scope_requested")
    if not approved:
        blockers.append("no_approved_read_scope")

    ordered = tuple(sorted(set(blockers)))
    return ApiAccessReadiness(
        tenant_id=membership.tenant_id,
        user_id=membership.user_id,
        issuance_ready=not ordered,
        approved_scopes=approved,
        rejected_scopes=rejected,
        blockers=ordered,
    )
