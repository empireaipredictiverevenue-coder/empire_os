from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.digital_avatar_close_readiness import (
    assess_canonical_avatar_close_readiness,
)
from empire_os.digital_avatar_evidence_resolver import (
    MappingAvatarEvidenceResolver,
)


TERMS_REF = (
    "commercial_terms_review:"
    "22222222-2222-4222-8222-222222222222"
)
PRICE_REF = (
    "commercial_evidence:"
    "11111111-1111-4111-8111-111111111111"
)
PRODUCT_REF = "commercial_product_code:PREDICTIVE-REVENUE-PILOT"


def policy():
    return AvatarCommercialAuthorityPolicy(
        allowed_product_codes=("PREDICTIVE-REVENUE-PILOT",),
        approved_terms_refs=(TERMS_REF,),
        allowed_currencies=("USD",),
        max_discount_bps=1000,
        max_contract_months=3,
    )


def proposal(**overrides):
    values = {
        "product_code": "PREDICTIVE-REVENUE-PILOT",
        "list_price_cents": 500000,
        "proposed_price_cents": 475000,
        "currency": "USD",
        "contract_months": 1,
        "terms_ref": TERMS_REF,
        "evidence_refs": (PRODUCT_REF, PRICE_REF),
    }
    values.update(overrides)
    return AvatarCloseProposal(**values)


def resolver(**overrides):
    values = {
        TERMS_REF: {
            "evidence_ref": TERMS_REF,
            "content": "Approved terms.",
            "truth_class": "VERIFIED",
            "source_kind": "approved_commercial_terms",
            "provenance": "terms:test",
            "verified": True,
            "facts": {
                "status": "approved",
                "product_code": "PREDICTIVE-REVENUE-PILOT",
                "currency": "USD",
                "price_cents": 475000,
                "verified_price_evidence_ref": PRICE_REF,
                "commercial_terms_sha256": "a" * 64,
            },
        },
        PRICE_REF: {
            "evidence_ref": PRICE_REF,
            "content": "Verified list price.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_price",
            "provenance": "price:test",
            "verified": True,
            "facts": {
                "amount_cents": 500000,
                "currency": "USD",
                "unit": "flat",
                "source_type": "founder_approved",
            },
        },
        PRODUCT_REF: {
            "evidence_ref": PRODUCT_REF,
            "content": "Verified product.",
            "truth_class": "VERIFIED",
            "source_kind": "commercial_product_catalog",
            "provenance": "catalog:test",
            "verified": True,
            "facts": {
                "product_code": "PREDICTIVE-REVENUE-PILOT",
                "product_name": "Predictive Revenue Pilot",
                "product_family": "predictive_revenue",
                "currency": "USD",
                "binding_terms_ready": True,
                "price": {
                    "amount_cents": 500000,
                    "currency": "USD",
                    "unit": "flat",
                },
            },
        },
    }
    values.update(overrides)
    return MappingAvatarEvidenceResolver(values)


def test_canonical_close_can_advance_conversation_but_not_bind():
    result = assess_canonical_avatar_close_readiness(
        policy=policy(),
        proposal=proposal(),
        resolver=resolver(),
    )
    assert result.policy_eligible is True
    assert result.canonical_grounded is True
    assert result.conversational_close_ready is True
    assert result.binding_execution_allowed is False
    assert result.human_takeover_required is False
    assert result.discount_bps == 500
    assert set(result.canonical_evidence_refs) == {
        TERMS_REF,
        PRODUCT_REF,
        PRICE_REF,
    }
    assert "runtime_observe_only" in result.blockers
    assert "binding_acceptance_not_activated" in result.blockers


def test_terms_price_mismatch_blocks_close_conversation():
    bad_terms = {
        "evidence_ref": TERMS_REF,
        "content": "Approved terms.",
        "truth_class": "VERIFIED",
        "source_kind": "approved_commercial_terms",
        "provenance": "terms:test",
        "verified": True,
        "facts": {
            "status": "approved",
            "product_code": "PREDICTIVE-REVENUE-PILOT",
            "currency": "USD",
            "price_cents": 450000,
            "verified_price_evidence_ref": PRICE_REF,
            "commercial_terms_sha256": "a" * 64,
        },
    }
    result = assess_canonical_avatar_close_readiness(
        policy=policy(),
        proposal=proposal(),
        resolver=resolver(**{TERMS_REF: bad_terms}),
    )
    assert result.canonical_grounded is False
    assert result.conversational_close_ready is False
    assert result.human_takeover_required is True
    assert "proposal_price_mismatch_approved_terms" in result.blockers


def test_agent_cannot_substitute_uncited_price_evidence():
    result = assess_canonical_avatar_close_readiness(
        policy=policy(),
        proposal=proposal(evidence_refs=(PRODUCT_REF,)),
        resolver=resolver(),
    )
    assert result.conversational_close_ready is False
    assert "proposal_does_not_cite_verified_price" in result.blockers


def test_product_catalog_price_mismatch_blocks_close():
    bad_product = {
        "evidence_ref": PRODUCT_REF,
        "content": "Verified product.",
        "truth_class": "VERIFIED",
        "source_kind": "commercial_product_catalog",
        "provenance": "catalog:test",
        "verified": True,
        "facts": {
            "product_code": "PREDICTIVE-REVENUE-PILOT",
            "currency": "USD",
            "binding_terms_ready": True,
            "price": {
                "amount_cents": 600000,
                "currency": "USD",
            },
        },
    }
    result = assess_canonical_avatar_close_readiness(
        policy=policy(),
        proposal=proposal(),
        resolver=resolver(**{PRODUCT_REF: bad_product}),
    )
    assert result.conversational_close_ready is False
    assert "proposal_list_price_mismatch_catalog" in result.blockers


def test_discount_outside_policy_requires_human_takeover_even_if_grounded():
    result = assess_canonical_avatar_close_readiness(
        policy=policy(),
        proposal=proposal(proposed_price_cents=400000),
        resolver=resolver(),
    )
    assert result.policy_eligible is False
    assert result.conversational_close_ready is False
    assert result.human_takeover_required is True
    assert "discount_exceeds_delegated_limit" in result.blockers
