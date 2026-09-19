"""Phase 16 evidence-backed SaaS/network scale readiness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SaasScaleSnapshot:
    tenant_id: str
    active_members: int
    observed_monthly_usage: int
    observed_usage_limit: int | None
    active_subscription: bool
    tenant_isolation_verified: bool
    white_label_requested: bool
    white_label_configured: bool
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id required")
        if self.active_members < 0 or self.observed_monthly_usage < 0:
            raise ValueError("members and usage must be nonnegative")
        if self.observed_usage_limit is not None and self.observed_usage_limit < 0:
            raise ValueError("usage limit must be nonnegative")
        if not self.evidence_refs:
            raise ValueError("scale readiness requires evidence")


@dataclass(frozen=True)
class SaasScaleReadiness:
    tenant_id: str
    ready_for_review: bool
    utilization_ratio: float | None
    missing_evidence: tuple[str, ...]
    reason: str
    execution_authority: str = "none"
    provisioning_execution: bool = False
    billing_execution: bool = False
    approval_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_saas_scale_readiness(
    snapshot: SaasScaleSnapshot,
) -> SaasScaleReadiness:
    snapshot.validate()
    missing: list[str] = []
    if snapshot.observed_usage_limit is None:
        missing.append("observed_usage_limit")
    if not snapshot.active_subscription:
        missing.append("active_subscription")
    if not snapshot.tenant_isolation_verified:
        missing.append("tenant_isolation_verified")
    if snapshot.white_label_requested and not snapshot.white_label_configured:
        missing.append("white_label_configured")

    utilization = None
    if snapshot.observed_usage_limit not in (None, 0):
        utilization = round(
            snapshot.observed_monthly_usage / snapshot.observed_usage_limit,
            4,
        )

    ready = not missing
    reason = (
        "evidence_sufficient_for_scale_review"
        if ready
        else "required_scale_evidence_missing"
    )
    return SaasScaleReadiness(
        tenant_id=snapshot.tenant_id,
        ready_for_review=ready,
        utilization_ratio=utilization,
        missing_evidence=tuple(missing),
        reason=reason,
    )
