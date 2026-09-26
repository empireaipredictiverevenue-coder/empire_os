from empire_os.intelligence.features import extract_features


def test_empty_lead_produces_zeroed_features():
    features = extract_features({})

    assert features.has_identity is False
    assert features.has_phone is False
    assert features.has_email is False
    assert features.contactability == 0.0
    assert features.data_completeness == 0.0
    assert features.legacy_omega_score == 0.0
    assert features.legacy_omega_tier == "bronze"


def test_complete_lead_extracts_expected_features():
    features = extract_features({
        "business_name": "Example Roofing",
        "contact_name": "John Smith",
        "phone": "5551234567",
        "email": "john@example.com",
        "website": "https://example.com",
        "city": "Dallas",
        "state": "TX",
        "niche": "roofing",
        "sub_niche": "residential_roofing",
        "metro": "DFW",
        "status": "qualified",
        "source": "market_sweep",
        "omega_score": 82,
        "notes": "High intent roofing contractor.",
    })

    assert features.has_identity is True
    assert features.has_business_name is True
    assert features.has_contact_name is True
    assert features.has_phone is True
    assert features.has_email is True
    assert features.has_website is True
    assert features.has_location is True
    assert features.has_market is True
    assert features.has_description is True

    assert features.contactability == 1.0
    assert features.data_completeness == 1.0

    assert features.legacy_omega_score == 82.0
    assert features.legacy_omega_tier == "gold"

    assert features.status == "qualified"
    assert features.source == "market_sweep"
    assert features.niche == "roofing"
    assert features.sub_niche == "residential_roofing"
    assert features.metro == "DFW"


def test_invalid_legacy_score_is_safe():
    features = extract_features({
        "omega_score": "not-a-number",
    })

    assert features.legacy_omega_score == 0.0
    assert features.legacy_omega_tier == "bronze"


def test_legacy_score_is_clamped():
    assert extract_features({"omega_score": -50}).legacy_omega_score == 0.0
    assert extract_features({"omega_score": 150}).legacy_omega_score == 100.0
