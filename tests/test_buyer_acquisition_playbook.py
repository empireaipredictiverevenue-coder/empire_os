import pytest

from empire_os.buyer_acquisition_playbook import review_buyer_offer


GATES = (
    "buyer_identity_verified", "commercial_need_evidenced",
    "offer_scope_documented", "contact_suppression_cleared",
    "contact_permission_cleared", "terms_accepted",
    "buyer_capacity_verified", "conversion_tracking_verified",
)


def test_unknown_evidence_holds_everything():
    result = review_buyer_offer(buyer_label="Example Buyer", evidence={})
    assert result["outreach_review_status"] == "HOLD"
    assert result["pilot_review_status"] == "HOLD"
    assert set(result["missing_evidence"]) == set(GATES)
    assert result["realised_revenue"] is None


def test_only_literal_true_counts():
    result = review_buyer_offer(
        buyer_label="Example Buyer", evidence={key: "true" for key in GATES})
    assert result["outreach_review_status"] == "HOLD"


def test_contact_gate_prevents_outreach_even_with_terms():
    facts = dict.fromkeys(GATES, True)
    facts["contact_suppression_cleared"] = False
    result = review_buyer_offer(buyer_label="Example Buyer", evidence=facts)
    assert result["outreach_review_status"] == "HOLD"
    assert result["pilot_review_status"] == "HOLD"


def test_full_evidence_only_yields_review_not_execution():
    result = review_buyer_offer(
        buyer_label="Example Buyer", evidence=dict.fromkeys(GATES, True))
    assert result["outreach_review_status"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert result["pilot_review_status"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert result["outbound_authorized"] is False
    assert result["pilot_activated"] is False
    assert result["crm_writes"] is False
    assert result["payment_execution"] is False
    assert result["revenue_verified"] is False


def test_bad_inputs_rejected():
    with pytest.raises(ValueError):
        review_buyer_offer(buyer_label="", evidence={})
    with pytest.raises(ValueError):
        review_buyer_offer(buyer_label="Buyer", evidence=None)
