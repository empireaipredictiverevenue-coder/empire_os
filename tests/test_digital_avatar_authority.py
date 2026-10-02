import pytest

from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
    assess_avatar_commercial_authority,
)


def policy():
    return AvatarCommercialAuthorityPolicy(
        allowed_product_codes=("predictive-revenue-pilot",),
        approved_terms_refs=("terms:pilot:v1",),
        allowed_currencies=("USD",),
        max_discount_bps=1000,
        max_contract_months=3,
    )


def proposal(**overrides):
    values = {
        "product_code": "predictive-revenue-pilot",
        "list_price_cents": 500000,
        "proposed_price_cents": 475000,
        "currency": "USD",
        "contract_months": 1,
        "terms_ref": "terms:pilot:v1",
        "evidence_refs": ("catalog:pilot:v1", "pricing:pilot:v1"),
    }
    values.update(overrides)
    return AvatarCloseProposal(**values)


def test_within_policy_is_eligible_but_not_executable_in_observe():
    decision = assess_avatar_commercial_authority(
        policy=policy(),
        proposal=proposal(),
    )
    assert decision.policy_eligible is True
    assert decision.execution_allowed is False
    assert decision.human_takeover_required is False
    assert decision.discount_bps == 500
    assert decision.blockers == ("runtime_observe_only",)


def test_discount_outside_limit_requires_takeover():
    decision = assess_avatar_commercial_authority(
        policy=policy(),
        proposal=proposal(proposed_price_cents=400000),
    )
    assert decision.policy_eligible is False
    assert decision.human_takeover_required is True
    assert "discount_exceeds_delegated_limit" in decision.blockers


def test_unapproved_terms_require_takeover():
    decision = assess_avatar_commercial_authority(
        policy=policy(),
        proposal=proposal(terms_ref="terms:custom:buyer"),
    )
    assert decision.policy_eligible is False
    assert decision.human_takeover_required is True
    assert "terms_outside_delegated_authority" in decision.blockers


def test_missing_commercial_evidence_fails_closed():
    decision = assess_avatar_commercial_authority(
        policy=policy(),
        proposal=proposal(evidence_refs=()),
    )
    assert decision.policy_eligible is False
    assert "commercial_evidence_missing" in decision.blockers


def test_v1_rejects_runtime_authority_expansion():
    with pytest.raises(ValueError, match="OBSERVE only"):
        assess_avatar_commercial_authority(
            policy=policy(),
            proposal=proposal(),
            runtime_authority="governed_external",
        )
