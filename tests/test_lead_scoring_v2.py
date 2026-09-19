import pytest

from empire_os.lead_scoring_v2 import (
    LeadScoringV2Error,
    compute_lead_score_v2,
)


def test_unknown_dimensions_remain_none_not_zero():
    result = compute_lead_score_v2({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "buy_signal_score": 0,
        "enrichment_score": 0,
    })

    assert result["dimensions"]["market_fit"] == 100.0
    assert result["dimensions"]["engagement_potential"] is None
    assert result["dimensions"]["enrichment_quality"] is None
    assert result["quality_score"] == 100.0
    assert result["evidence_confidence"] == 0.15
    assert result["decision_tier"] == "insufficient_evidence"


def test_observed_zero_is_real_zero():
    result = compute_lead_score_v2(
        {
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "buy_signal_score": 0,
        },
        buy_signal_observed=True,
    )

    assert result["dimensions"]["engagement_potential"] == 0.0
    assert "engagement_potential" in result["observed_dimensions"]
    assert "enrichment_quality" in result["unknown_dimensions"]


def test_strong_evidence_can_reach_hot_decision():
    result = compute_lead_score_v2(
        {
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "email": "owner@example.com",
            "phone": "+442000000000",
            "website": "https://example.com",
            "street": "1 Test Street",
            "city": "London",
            "state": "London",
            "zip": "SW1A 1AA",
            "contact_name": "Alex Smith",
        },
        business_presence_checked=True,
    )

    assert result["quality_score"] > 75
    assert result["evidence_confidence"] == 0.75
    assert result["decision_tier"] == "hot"


def test_low_confidence_never_uses_quality_band_as_decision():
    result = compute_lead_score_v2({
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "website": "https://example.com",
    })

    assert result["quality_band"] == "hot"
    assert result["evidence_confidence"] < 0.50
    assert result["decision_tier"] == "insufficient_evidence"


def test_observed_signal_requires_a_value():
    with pytest.raises(
        LeadScoringV2Error,
        match="observed buy_signal_score is missing",
    ):
        compute_lead_score_v2(
            {
                "business_name": "Acme",
                "niche": "roofing",
            },
            buy_signal_observed=True,
        )


def test_enrichment_signal_is_bounded():
    with pytest.raises(
        LeadScoringV2Error,
        match="between 0 and 100",
    ):
        compute_lead_score_v2(
            {
                "business_name": "Acme",
                "niche": "roofing",
                "enrichment_score": 120,
            },
            enrichment_observed=True,
        )


def test_no_quality_evidence_is_insufficient():
    result = compute_lead_score_v2({})

    assert result["quality_score"] is None
    assert result["quality_band"] == "unknown"
    assert result["evidence_confidence"] == 0
    assert result["decision_tier"] == "insufficient_evidence"
