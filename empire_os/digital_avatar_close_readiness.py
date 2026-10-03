"""Canonical commercial grounding for Digital Avatar close conversations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
    assess_avatar_commercial_authority,
)
from empire_os.digital_avatar_evidence_pack import AvatarEvidenceResolver


@dataclass(frozen=True)
class AvatarCanonicalCloseReadiness:
    product_code: str
    terms_ref: str
    verified_price_evidence_ref: str | None
    policy_eligible: bool
    canonical_grounded: bool
    conversational_close_ready: bool
    binding_execution_allowed: bool
    human_takeover_required: bool
    discount_bps: int
    canonical_evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    execution_authority: str = "none"
    side_effects: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _facts(
    resolver: AvatarEvidenceResolver,
    evidence_ref: str,
    *,
    expected_kind: str,
) -> Mapping[str, Any] | None:
    value = resolver.resolve(evidence_ref)
    if not isinstance(value, Mapping):
        return None
    if value.get("verified") is not True:
        return None
    if str(value.get("truth_class") or "") != "VERIFIED":
        return None
    if str(value.get("source_kind") or "") != expected_kind:
        return None
    facts = value.get("facts")
    return facts if isinstance(facts, Mapping) else None


def assess_canonical_avatar_close_readiness(
    *,
    policy: AvatarCommercialAuthorityPolicy,
    proposal: AvatarCloseProposal,
    resolver: AvatarEvidenceResolver,
) -> AvatarCanonicalCloseReadiness:
    authority = assess_avatar_commercial_authority(
        policy=policy,
        proposal=proposal,
        runtime_authority="observe",
    )
    blockers: list[str] = []
    refs: list[str] = []

    terms = _facts(
        resolver,
        proposal.terms_ref,
        expected_kind="approved_commercial_terms",
    )
    price_ref: str | None = None
    if terms is None:
        blockers.append("approved_canonical_terms_unresolved")
    else:
        refs.append(proposal.terms_ref)
        if str(terms.get("status") or "").lower() != "approved":
            blockers.append("commercial_terms_not_approved")
        if str(terms.get("product_code") or "") != proposal.product_code:
            blockers.append("proposal_product_mismatch_approved_terms")
        if str(terms.get("currency") or "").upper() != proposal.currency.upper():
            blockers.append("proposal_currency_mismatch_approved_terms")
        try:
            terms_price = int(terms.get("price_cents") or 0)
        except (TypeError, ValueError):
            terms_price = 0
        if terms_price != proposal.proposed_price_cents:
            blockers.append("proposal_price_mismatch_approved_terms")
        price_ref = str(
            terms.get("verified_price_evidence_ref") or ""
        ).strip() or None
        if price_ref is None:
            blockers.append("approved_terms_price_evidence_missing")
        elif price_ref not in set(proposal.evidence_refs):
            blockers.append("proposal_does_not_cite_verified_price")

    product_ref = f"commercial_product_code:{proposal.product_code}"
    product = _facts(
        resolver,
        product_ref,
        expected_kind="commercial_product_catalog",
    )
    if product is None:
        blockers.append("verified_product_catalog_unresolved")
    else:
        refs.append(product_ref)
        if str(product.get("product_code") or "") != proposal.product_code:
            blockers.append("proposal_product_mismatch_catalog")
        if product.get("binding_terms_ready") is not True:
            blockers.append("product_binding_terms_not_ready")
        if str(product.get("currency") or "").upper() != proposal.currency.upper():
            blockers.append("proposal_currency_mismatch_catalog")
        price = product.get("price")
        if not isinstance(price, Mapping):
            blockers.append("verified_product_price_missing")
        else:
            try:
                catalog_price = int(price.get("amount_cents") or 0)
            except (TypeError, ValueError):
                catalog_price = 0
            if catalog_price != proposal.list_price_cents:
                blockers.append("proposal_list_price_mismatch_catalog")
            price_currency = str(
                price.get("currency") or product.get("currency") or ""
            ).upper()
            if price_currency != proposal.currency.upper():
                blockers.append("proposal_price_currency_mismatch_catalog")

    if price_ref is not None:
        price = _facts(
            resolver,
            price_ref,
            expected_kind="commercial_price",
        )
        if price is None:
            blockers.append("verified_price_evidence_unresolved")
        else:
            refs.append(price_ref)
            try:
                evidence_price = int(price.get("amount_cents") or 0)
            except (TypeError, ValueError):
                evidence_price = 0
            if evidence_price != proposal.list_price_cents:
                blockers.append("proposal_list_price_mismatch_evidence")
            if str(price.get("currency") or "").upper() != proposal.currency.upper():
                blockers.append("proposal_currency_mismatch_price_evidence")

    if product_ref not in set(proposal.evidence_refs):
        blockers.append("proposal_does_not_cite_product_catalog")

    canonical_blockers = tuple(sorted(set(blockers)))
    canonical_grounded = not canonical_blockers
    conversational_ready = authority.policy_eligible and canonical_grounded
    human_takeover = not conversational_ready

    execution_blockers = set(canonical_blockers)
    execution_blockers.update(authority.blockers)
    execution_blockers.add("binding_acceptance_not_activated")

    return AvatarCanonicalCloseReadiness(
        product_code=proposal.product_code,
        terms_ref=proposal.terms_ref,
        verified_price_evidence_ref=price_ref,
        policy_eligible=authority.policy_eligible,
        canonical_grounded=canonical_grounded,
        conversational_close_ready=conversational_ready,
        binding_execution_allowed=False,
        human_takeover_required=human_takeover,
        discount_bps=authority.discount_bps,
        canonical_evidence_refs=tuple(dict.fromkeys(refs)),
        blockers=tuple(sorted(execution_blockers)),
    )
