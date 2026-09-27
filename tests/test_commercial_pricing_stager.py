from empire_os.commercial_pricing_policy import (
    build_launch_pricing_proposal,
)


def test_pricing_proposal_is_nonbinding_before_founder_approval():
    proposal = build_launch_pricing_proposal()

    assert proposal["founder_approval_required"] is True
    assert proposal["binding"] is False
    assert proposal["database_mutation_authorized"] is False
    assert proposal["product_count"] == 12


def test_stager_requires_explicit_founder_approval_before_apply():
    text = open(
        "scripts/stage_commercial_pricing_policy.py",
        encoding="utf-8",
    ).read()

    assert "--apply-pending" in text
    assert "--approval-reference" in text
    assert "founder_approval:" in text
    assert "PENDING_VERSIONS_STAGED" in text
    assert '"binding_terms_created": False' in text
    assert "decide_commercial_product_version" not in text
