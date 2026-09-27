from empire_os.outreach_quality import build_message_brief, review_deliverability


def test_deliverability_requires_complete_observed_health_for_send_review():
    unknown = review_deliverability({})
    assert unknown["ready_for_send_review"] is False
    assert "sending_domain_verified_unknown" in unknown["unknowns"]
    assert unknown["execution_authority"] == "none"

    ready = review_deliverability({
        "sending_domain_verified": True,
        "spf_verified": True,
        "dkim_verified": True,
        "dmarc_verified": True,
        "bounce_rate": 0.01,
        "complaint_rate": 0.0002,
        "provider_ready": True,
    })
    assert ready["ready_for_send_review"] is True
    assert ready["dns_mutation"] is False
    assert ready["provider_mutation"] is False


def test_deliverability_blocks_bad_observed_rates():
    result = review_deliverability({
        "sending_domain_verified": True,
        "spf_verified": True,
        "dkim_verified": True,
        "dmarc_verified": True,
        "bounce_rate": 0.10,
        "complaint_rate": 0.01,
        "provider_ready": True,
    })
    assert result["ready_for_send_review"] is False
    assert "bounce_rate_above_internal_policy" in result["blockers"]
    assert "complaint_rate_above_internal_policy" in result["blockers"]


def test_message_brief_forbids_fake_revenue_claims():
    brief = build_message_brief(
        business_name="Northstar Roofing",
        contact_name="Jane Smith",
        contact_title="Owner",
        play_type="new_buyer",
        offer_key="territory-seat",
        corridor_key="roofing:manchester:exclusive",
        territory="Manchester",
        reason_now="Observed demand increased.",
        evidence_refs=["market:1"],
        predicted_economics={
            "prediction_ref": "pred-1",
            "expected_gross_profit_cents": 300000,
        },
    )
    assert brief["drafting_only"] is True
    assert brief["send_enabled"] is False
    assert "prediction represented as actual revenue" in brief["forbidden_claims"]
    assert "actual revenue" in brief["economics_rule"]
