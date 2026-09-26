"""Phase 16 append-only API access review history contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.saas_api_access_freshness import ApiAccessFreshnessReview


@dataclass(frozen=True)
class ApiAccessReviewRecord:
    review_key: str
    freshness: ApiAccessFreshnessReview
    evidence: Mapping[str, Any]
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    approval_required: bool = True
    execution_authority: str = "none"
    api_key_issuance: bool = False
    api_key_revocation: bool = False
    secret_material_generated: bool = False
    subscription_mutation: bool = False
    provisioning_execution: bool = False

    def validate(self) -> None:
        if not str(self.review_key or "").strip():
            raise ValueError("api access review_key required")
        if self.freshness.execution_authority != "none":
            raise ValueError("API access review cannot grant execution")
        if (
            self.api_key_issuance
            or self.api_key_revocation
            or self.secret_material_generated
            or self.subscription_mutation
            or self.provisioning_execution
        ):
            raise ValueError("API access review cannot mutate or issue")
        if not isinstance(self.evidence, Mapping) or not self.evidence:
            raise ValueError("API access review registry requires evidence")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "review_key": self.review_key,
            "freshness": self.freshness.as_dict(),
            "evidence": dict(self.evidence),
            "eligible_for_manual_issuance_review": (
                self.freshness.fresh_for_issuance_review
            ),
            **{
                key: value
                for key, value in asdict(self).items()
                if key not in {"review_key", "freshness", "evidence"}
            },
        }
