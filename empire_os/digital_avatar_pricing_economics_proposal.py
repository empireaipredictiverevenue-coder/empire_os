"""Founder pricing/economics proposal for Empire Digital Avatar.

All values in this module are non-binding policy proposals until explicitly
approved by the founder. Cost ceilings are policy guardrails, not observed
actual costs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from empire_os.digital_avatar_commercial_packaging import (
    get_avatar_commercial_package,
)


POLICY_REFERENCE = "founder_pricing_proposal:2026-10-02:digital_avatar:v1"
MARKET_OBSERVED_AT = "2026-10-02"
MINIMUM_MARGIN_BPS = 7000
TARGET_POLICY_MARGIN_BPS = 7500


@dataclass(frozen=True)
class AvatarPricingPolicyProposal:
    package_key: str
    product_code: str
    monthly_price_cents: int
    implementation_fee_cents: int
    included_active_avatars: int
    included_verified_meetings_per_month: int
    proposed_concurrency_entitlement: int
    overage_per_verified_meeting_cents: int
    acquisition_cost_ceiling_cents: int
    fulfilment_cost_ceiling_cents: int
    minimum_margin_bps: int = MINIMUM_MARGIN_BPS

    @property
    def policy_contribution_cents(self) -> int:
        return (
            self.monthly_price_cents
            - self.acquisition_cost_ceiling_cents
            - self.fulfilment_cost_ceiling_cents
        )

    @property
    def policy_margin_bps(self) -> int:
        return int(
            self.policy_contribution_cents
            * 10000
            / self.monthly_price_cents
        )

    def validate(self) -> None:
        package = get_avatar_commercial_package(self.package_key)
        if package.product_code != self.product_code:
            raise ValueError("pricing package/product mismatch")
        for label, value in (
            ("monthly_price_cents", self.monthly_price_cents),
            ("implementation_fee_cents", self.implementation_fee_cents),
            ("included_active_avatars", self.included_active_avatars),
            (
                "included_verified_meetings_per_month",
                self.included_verified_meetings_per_month,
            ),
            (
                "proposed_concurrency_entitlement",
                self.proposed_concurrency_entitlement,
            ),
            (
                "overage_per_verified_meeting_cents",
                self.overage_per_verified_meeting_cents,
            ),
        ):
            if int(value) <= 0:
                raise ValueError(f"{label} must be positive")
        if self.acquisition_cost_ceiling_cents < 0:
            raise ValueError("acquisition cost ceiling invalid")
        if self.fulfilment_cost_ceiling_cents < 0:
            raise ValueError("fulfilment cost ceiling invalid")
        if self.policy_contribution_cents <= 0:
            raise ValueError("positive policy contribution required")
        if self.policy_margin_bps < self.minimum_margin_bps:
            raise ValueError("minimum policy margin not satisfied")

    def as_proposal_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "package_key": self.package_key,
            "product_code": self.product_code,
            "billing_model": "monthly_subscription",
            "currency": "USD",
            "monthly_price_cents": self.monthly_price_cents,
            "implementation_fee_cents": self.implementation_fee_cents,
            "included_active_avatars": self.included_active_avatars,
            "included_verified_meetings_per_month": (
                self.included_verified_meetings_per_month
            ),
            "proposed_concurrency_entitlement": (
                self.proposed_concurrency_entitlement
            ),
            "overage_per_verified_meeting_cents": (
                self.overage_per_verified_meeting_cents
            ),
            "price_basis": {
                "state": "PROPOSED",
                "source_type": "founder_policy_proposal",
                "currency": "USD",
                "unit": "per_month",
                "amount_cents": self.monthly_price_cents,
                "proposal_reference": POLICY_REFERENCE,
                "observed_historical_transaction_price": False,
            },
            "acquisition_cost_basis": {
                "state": "PROPOSED",
                "basis_type": "policy_ceiling",
                "amount_cents": self.acquisition_cost_ceiling_cents,
                "currency": "USD",
                "observed_actual": False,
                "proposal_reference": POLICY_REFERENCE,
            },
            "fulfilment_cost_basis": {
                "state": "PROPOSED",
                "basis_type": "policy_ceiling",
                "amount_cents": self.fulfilment_cost_ceiling_cents,
                "currency": "USD",
                "observed_actual": False,
                "proposal_reference": POLICY_REFERENCE,
            },
            "margin_policy": {
                "state": "PROPOSED",
                "minimum_margin_bps": self.minimum_margin_bps,
                "target_policy_margin_bps": TARGET_POLICY_MARGIN_BPS,
                "policy_margin_bps": self.policy_margin_bps,
                "policy_contribution_cents": self.policy_contribution_cents,
                "proposal_reference": POLICY_REFERENCE,
            },
            "founder_approval_required": True,
            "binding": False,
            "catalog_mutation_authorized": False,
            "checkout_authorized": False,
            "payment_authority": "none",
            "actual_revenue": False,
            "execution_authority": "none",
        }

    def as_founder_approved_price_candidate(
        self,
        approval_reference: str,
    ) -> dict[str, Any]:
        self.validate()
        approval = str(approval_reference or "").strip()
        if not approval:
            raise ValueError("explicit founder pricing approval reference required")
        value = self.as_proposal_dict()
        value["price_basis"] = {
            **value["price_basis"],
            "state": "VERIFIED",
            "source_type": "founder_approved",
            "approval_reference": approval,
        }
        value["price_basis"].pop("proposal_reference", None)
        value["founder_approval_required"] = False
        value["founder_approval_reference"] = approval

        # Founder approval of price does not prove cost or margin evidence.
        value["acquisition_cost_basis"] = {
            **value["acquisition_cost_basis"],
            "state": "PROPOSED",
        }
        value["fulfilment_cost_basis"] = {
            **value["fulfilment_cost_basis"],
            "state": "PROPOSED",
        }
        value["margin_policy"] = {
            **value["margin_policy"],
            "state": "PROPOSED",
        }
        value["binding"] = False
        value["catalog_mutation_authorized"] = False
        value["checkout_authorized"] = False
        value["payment_authority"] = "none"
        value["actual_revenue"] = False
        value["execution_authority"] = "none"
        return value
DIGITAL_AVATAR_PRICING_PROPOSALS: tuple[AvatarPricingPolicyProposal, ...] = (
    AvatarPricingPolicyProposal(
        package_key="copilot",
        product_code="digital_avatar_copilot",
        monthly_price_cents=150_000,
        implementation_fee_cents=150_000,
        included_active_avatars=1,
        included_verified_meetings_per_month=40,
        proposed_concurrency_entitlement=1,
        overage_per_verified_meeting_cents=3_500,
        acquisition_cost_ceiling_cents=15_000,
        fulfilment_cost_ceiling_cents=22_500,
    ),
    AvatarPricingPolicyProposal(
        package_key="workforce",
        product_code="digital_avatar_workforce",
        monthly_price_cents=500_000,
        implementation_fee_cents=500_000,
        included_active_avatars=5,
        included_verified_meetings_per_month=150,
        proposed_concurrency_entitlement=3,
        overage_per_verified_meeting_cents=3_000,
        acquisition_cost_ceiling_cents=50_000,
        fulfilment_cost_ceiling_cents=75_000,
    ),
    AvatarPricingPolicyProposal(
        package_key="white_label_workforce",
        product_code="digital_avatar_white_label_workforce",
        monthly_price_cents=1_250_000,
        implementation_fee_cents=1_500_000,
        included_active_avatars=15,
        included_verified_meetings_per_month=400,
        proposed_concurrency_entitlement=10,
        overage_per_verified_meeting_cents=2_500,
        acquisition_cost_ceiling_cents=125_000,
        fulfilment_cost_ceiling_cents=187_500,
    ),
)


def build_digital_avatar_pricing_proposal() -> dict[str, Any]:
    rows = tuple(
        proposal.as_proposal_dict()
        for proposal in DIGITAL_AVATAR_PRICING_PROPOSALS
    )
    return {
        "schema_version": "empire.digital-avatar-pricing-proposal.v1",
        "policy_reference": POLICY_REFERENCE,
        "market_observed_at": MARKET_OBSERVED_AT,
        "currency": "USD",
        "settlement_target": "USDT_BSC",
        "products": rows,
        "product_count": len(rows),
        "custom_enterprise_recurring_floor_cents": 1_500_000,
        "custom_enterprise_floor_state": "PROPOSED",
        "market_anchor_note": (
            "Public 2026 avatar infrastructure, meeting-bot and AI-worker "
            "pricing informs positioning only. Empire prices are policy "
            "proposals, not observed transaction prices."
        ),
        "observed_costs_verified": False,
        "duration_cost_benchmark_required": True,
        "capacity_benchmark_required": True,
        "founder_approval_required": True,
        "database_mutation_authorized": False,
        "binding_terms_ready": False,
        "checkout_authorized": False,
        "payment_authority": "none",
        "actual_revenue": False,
        "execution_authority": "none",
    }
