"""Deterministic delegated commercial authority for Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AvatarCommercialAuthorityPolicy:
    allowed_product_codes: tuple[str, ...]
    approved_terms_refs: tuple[str, ...]
    allowed_currencies: tuple[str, ...] = ("USD",)
    max_discount_bps: int = 0
    max_contract_months: int = 1

    def validate(self) -> None:
        if not self.allowed_product_codes:
            raise ValueError("at least one delegated product required")
        if not self.approved_terms_refs:
            raise ValueError("at least one approved terms ref required")
        if not self.allowed_currencies:
            raise ValueError("at least one allowed currency required")
        if not 0 <= self.max_discount_bps <= 10_000:
            raise ValueError("max_discount_bps must be between 0 and 10000")
        if self.max_contract_months <= 0:
            raise ValueError("max_contract_months must be positive")


@dataclass(frozen=True)
class AvatarCloseProposal:
    product_code: str
    list_price_cents: int
    proposed_price_cents: int
    currency: str
    contract_months: int
    terms_ref: str
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.product_code.strip():
            raise ValueError("product_code required")
        if self.list_price_cents <= 0 or self.proposed_price_cents <= 0:
            raise ValueError("proposal prices must be positive")
        if self.proposed_price_cents > self.list_price_cents:
            raise ValueError("proposed price cannot exceed evidenced list price")
        if not self.currency.strip():
            raise ValueError("currency required")
        if self.contract_months <= 0:
            raise ValueError("contract_months must be positive")
        if not self.terms_ref.strip():
            raise ValueError("terms_ref required")


@dataclass(frozen=True)
class AvatarCommercialAuthorityDecision:
    policy_eligible: bool
    execution_allowed: bool
    human_takeover_required: bool
    discount_bps: int
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    side_effects: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _discount_bps(list_price_cents: int, proposed_price_cents: int) -> int:
    discount = list_price_cents - proposed_price_cents
    return round((discount / list_price_cents) * 10_000)


def assess_avatar_commercial_authority(
    *,
    policy: AvatarCommercialAuthorityPolicy,
    proposal: AvatarCloseProposal,
    runtime_authority: str = "observe",
) -> AvatarCommercialAuthorityDecision:
    policy.validate()
    proposal.validate()
    if runtime_authority.strip().lower() != "observe":
        raise ValueError("Digital Avatar close authority V1 is OBSERVE only")

    blockers: list[str] = []
    discount_bps = _discount_bps(
        proposal.list_price_cents,
        proposal.proposed_price_cents,
    )

    if proposal.product_code not in set(policy.allowed_product_codes):
        blockers.append("product_outside_delegated_authority")
    if proposal.terms_ref not in set(policy.approved_terms_refs):
        blockers.append("terms_outside_delegated_authority")
    if proposal.currency.upper() not in {
        item.upper() for item in policy.allowed_currencies
    }:
        blockers.append("currency_outside_delegated_authority")
    if proposal.contract_months > policy.max_contract_months:
        blockers.append("contract_duration_exceeds_delegated_limit")
    if discount_bps > policy.max_discount_bps:
        blockers.append("discount_exceeds_delegated_limit")
    if not proposal.evidence_refs:
        blockers.append("commercial_evidence_missing")


    policy_blockers = tuple(sorted(set(blockers)))
    policy_eligible = not policy_blockers
    human_takeover_required = not policy_eligible

    execution_blockers = list(policy_blockers)
    execution_blockers.append("runtime_observe_only")

    return AvatarCommercialAuthorityDecision(
        policy_eligible=policy_eligible,
        execution_allowed=False,
        human_takeover_required=human_takeover_required,
        discount_bps=discount_bps,
        blockers=tuple(sorted(set(execution_blockers))),
    )
