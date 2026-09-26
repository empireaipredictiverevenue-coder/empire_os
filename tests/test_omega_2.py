from empire_os.intelligence.features import LeadFeatures
from empire_os.intelligence.omega import MODEL_VERSION, analyze, analyze_many


def test_model_version():
    result = analyze({})
    assert result.model_version == MODEL_VERSION


def test_empty_lead_is_conservative():
    result = analyze({})

    assert 0.0 <= result.quality_probability <= 1.0
    assert 0.0 <= result.buyer_fit_probability <= 1.0
    assert 0.0 <= result.engagement_probability <= 1.0
    assert 0.0 <= result.conversion_probability <= 1.0
    assert 0.0 <= result.payment_probability <= 1.0
    assert 0.0 <= result.opportunity_score <= 100.0
    assert 0.0 <= result.confidence <= 1.0
    assert result.legacy_omega_score >= 0.0
    assert result.legacy_omega_tier in {
        "bronze",
        "silver",
        "gold",
        "platinum",
    }


def test_complete_business_lead_scores_above_empty_lead():
    empty = analyze({})

    complete = analyze({
        "business_name": "Example Roofing",
        "phone": "5551234567",
        "email": "owner@example.com",
        "website": "https://example.com",
        "city": "Dallas",
        "state": "TX",
        "niche": "roofing",
        "status": "raw",
    })

    assert complete.quality_probability > empty.quality_probability
    assert complete.buyer_fit_probability > empty.buyer_fit_probability
    assert complete.engagement_probability > empty.engagement_probability
    assert complete.opportunity_score > empty.opportunity_score
    assert complete.confidence > empty.confidence


def test_explicit_revenue_value_changes_expected_revenue():
    result = analyze({
        "business_name": "High Value Roofing",
        "phone": "5551234567",
        "email": "owner@example.com",
        "niche": "roofing",
        "expected_revenue": 100.0,
    })

    assert result.expected_revenue is not None
    assert result.expected_revenue > 0.0
    assert result.expected_gross_profit is None


def test_unknown_commercial_value_stays_unknown():
    result = analyze({
        "business_name": "Unknown Value Roofing",
        "niche": "roofing",
    })

    assert result.expected_revenue is None
    assert result.expected_gross_profit is None


def test_gp_requires_explicit_cost_or_gp_evidence():
    result = analyze({
        "business_name": "Costed Roofing",
        "niche": "roofing",
        "expected_revenue": 100.0,
        "expected_cost": 40.0,
    })

    assert result.expected_revenue is not None
    assert result.expected_gross_profit is not None
    assert result.expected_gross_profit > 0.0


def test_legacy_score_is_always_in_valid_range():
    for legacy_score in (0, 20, 50, 75, 95, 100):
        result = analyze({
            "business_name": "Legacy Score Test",
            "omega_score": legacy_score,
        })

        assert 0.0 <= result.legacy_omega_score <= 100.0
        assert result.legacy_omega_tier in {
            "bronze",
            "silver",
            "gold",
            "platinum",
        }


def test_analyze_many_ranks_by_commercial_value():
    leads = [
        {
            "business_name": "Small",
            "niche": "roofing",
        },
        {
            "business_name": "Strong Roofing",
            "phone": "5551234567",
            "email": "owner@example.com",
            "website": "https://example.com",
            "city": "Dallas",
            "state": "TX",
            "niche": "roofing",
            "expected_revenue": 500.0,
            "expected_cost": 100.0,
        },
    ]

    results = analyze_many(leads)

    assert len(results) == 2
    assert results[0].expected_gross_profit is not None
    assert results[1].expected_gross_profit is None


def test_legacy_omega_score_does_not_change_omega_2_prediction():
    lead = {
        "business_name": "Example Roofing",
        "phone": "+1 555 0100",
        "email": "owner@example.com",
        "website": "https://example.com",
        "city": "Dallas",
        "state": "TX",
        "niche": "roofing",
        "status": "qualified",
        "details": "Commercial roofing replacement opportunity.",
    }

    low_legacy = analyze({**lead, "omega_score": 0})
    high_legacy = analyze({**lead, "omega_score": 100})

    assert low_legacy.quality_probability == high_legacy.quality_probability
    assert low_legacy.buyer_fit_probability == high_legacy.buyer_fit_probability
    assert low_legacy.engagement_probability == high_legacy.engagement_probability
    assert low_legacy.conversion_probability == high_legacy.conversion_probability
    assert low_legacy.payment_probability == high_legacy.payment_probability
    assert low_legacy.expected_revenue == high_legacy.expected_revenue
    assert low_legacy.expected_gross_profit == high_legacy.expected_gross_profit
    assert low_legacy.opportunity_score == high_legacy.opportunity_score
    assert low_legacy.confidence == high_legacy.confidence
    assert low_legacy.next_best_action == high_legacy.next_best_action
    assert low_legacy.reasons == high_legacy.reasons

    # The compatibility score is generated from the new Omega 2.0
    # prediction, not copied from the caller's legacy score.
    assert low_legacy.legacy_omega_score == high_legacy.legacy_omega_score


def test_analyze_uses_canonical_feature_extractor(monkeypatch):
    canonical = LeadFeatures(
        has_identity=True,
        has_phone=True,
        has_email=True,
        has_website=True,
        has_location=True,
        has_market=True,
        has_description=True,
        contactability=1.0,
        data_completeness=1.0,
        legacy_omega_score=88.0,
        legacy_omega_tier="gold",
        status="qualified",
        source="canonical-test",
        niche="roofing",
        metro="DFW",
        text_length=64,
    )

    calls = []

    def fake_extract_features(lead):
        calls.append(lead)
        return canonical

    monkeypatch.setattr(
        "empire_os.intelligence.omega.extract_features",
        fake_extract_features,
    )

    result = analyze({"completely": "different raw input"})

    assert calls == [{"completely": "different raw input"}]
    assert result.quality_probability == 1.0
    assert 90.0 <= result.legacy_omega_score <= 100.0
    assert result.legacy_omega_tier == "platinum"
    assert result.next_best_action == "offer"
