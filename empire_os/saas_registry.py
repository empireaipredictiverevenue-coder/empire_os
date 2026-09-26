"""Governed Phase 16 SaaS/network-scale readiness registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from empire_os.saas_readiness import SaasScaleReadiness, SaasScaleSnapshot


@dataclass(frozen=True)
class SaasReadinessRecord:
    readiness_key: str
    snapshot: SaasScaleSnapshot
    readiness: SaasScaleReadiness
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        if not str(self.readiness_key or "").strip():
            raise ValueError("readiness_key required")
        self.snapshot.validate()
        if self.readiness.tenant_id != self.snapshot.tenant_id:
            raise ValueError("SaaS readiness tenant mismatch")
        if self.readiness.execution_authority != "none":
            raise ValueError("SaaS registry cannot grant execution")
        if self.readiness.provisioning_execution is not False:
            raise ValueError("provisioning execution must remain disabled")
        if self.readiness.billing_execution is not False:
            raise ValueError("billing execution must remain disabled")
        if self.readiness.approval_required is not True:
            raise ValueError("SaaS scale review requires approval")
        if not self.readiness.ready_for_review:
            raise ValueError("only review-ready tenants may be registered")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("SaaS registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "readiness_key": self.readiness_key,
            "tenant_id": self.snapshot.tenant_id,
            "snapshot": {
                "active_members": self.snapshot.active_members,
                "observed_monthly_usage": self.snapshot.observed_monthly_usage,
                "observed_usage_limit": self.snapshot.observed_usage_limit,
                "active_subscription": self.snapshot.active_subscription,
                "tenant_isolation_verified": (
                    self.snapshot.tenant_isolation_verified
                ),
                "white_label_requested": self.snapshot.white_label_requested,
                "white_label_configured": self.snapshot.white_label_configured,
                "evidence_refs": list(self.snapshot.evidence_refs),
            },
            "readiness": self.readiness.as_dict(),
            "evidence": dict(self.evidence),
            "mode": "OBSERVE",
            "execution_authority": "none",
            "provisioning_execution": False,
            "billing_execution": False,
            "api_key_issuance": False,
            "subscription_mutation": False,
        }
