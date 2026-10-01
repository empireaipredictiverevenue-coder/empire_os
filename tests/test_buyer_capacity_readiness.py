from datetime import datetime, timezone

from empire_os.buyer_capacity_readiness import summarize_buyer_capacity

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def discovered_buyer():
    return {
        "id": "b1",
        "buyer_name": "Observed Roofing",
        "status": "ACTIVE",
        "is_active": True,
        "commercial_activation_state": "discovered",
        "reviewed_at": None,
        "commercial_activated_at": None,
        "commercial_terms_source": None,
        "commercial_terms_reference": None,
        "commercial_terms_verified_at": None,
        "capacity_verified_at": None,
        "delivery_verified_at": None,
        "niche": "Roofing",
        "metro": "DFW",
        "destination_phone": "+12145550100",
        "webhook_url": None,
        "daily_cap": 50,
        "calls_today": 0,
    }


def activated_buyer():
    row = discovered_buyer()
    row.update({
        "commercial_activation_state": "activated",
        "reviewed_at": "2026-09-21T10:00:00Z",
        "commercial_activated_at": "2026-09-21T10:01:00Z",
        "commercial_terms_source": "signed_agreement",
        "commercial_terms_reference": "agreement:1",
        "commercial_terms_verified_at": "2026-09-21T10:02:00Z",
        "capacity_verified_at": "2026-09-21T10:03:00Z",
        "delivery_verified_at": "2026-09-21T10:04:00Z",
    })
    return row


def test_active_flag_is_not_activation_truth():
    result = summarize_buyer_capacity([discovered_buyer()], observed_at=NOW)
    assert result["status_active"] == 1
    assert result["is_active_true"] == 1
    assert result["fully_activated"] == 0
    assert result["terms_verified"] == 0
    assert result["allocation_ready"] is False
    assert result["highest_priority_blocker"] == "verified_commercial_terms"
    assert result["allocation_executed"] is False


def test_verified_buyer_passes_existing_activation_gate():
    result = summarize_buyer_capacity([activated_buyer()], observed_at=NOW)
    assert result["fully_activated"] == 1
    assert result["terms_verified"] == 1
    assert result["capacity_verified"] == 1
    assert result["delivery_verified"] == 1
    assert result["allocation_ready"] is True
    assert result["highest_priority_blocker"] is None


def test_no_buyers_stays_not_ready():
    result = summarize_buyer_capacity([], observed_at=NOW)
    assert result["buyers_seen"] == 0
    assert result["fully_activated"] == 0
    assert result["allocation_ready"] is False
    assert result["highest_priority_blocker"] == "verified_commercial_terms"


def test_quality_holds_exclude_populated_commercial_fields():
    from empire_os.buyer_allocation import buyer_activation_decision
    for change in (
        {"buyer_name": "Test Buyer"},
        {"buyer_name": "test_buyer"},
        {"buyer_name": "Demo Buyer"},
        {"id": "fixture:buyer"},
        {"status": "non_buyer"},
        {"webhook_url": "https://routing.example.invalid/hook"},
        {"webhook_url": "https://example.com/hook"},
    ):
        row = {**activated_buyer(), **change}
        assert buyer_activation_decision(row)[0] is False
        result = summarize_buyer_capacity([row], observed_at=NOW)
        assert result["identity_quality_held"] == 1
        assert result["fully_activated"] == 0
        assert result["terms_verified"] == 0
        assert result["capacity_verified"] == 0
        assert result["delivery_verified"] == 0
        assert result["allocation_ready"] is False


def test_classification_does_not_promote_discovery_or_reply_to_terms():
    from empire_os.buyer_allocation import buyer_evidence_classification
    row = discovered_buyer()
    assert buyer_evidence_classification(row) == "unreviewed_identity"
    row.update(reviewed_at="2026-09-21T10:00:00Z", reply="Interested, send details")
    assert buyer_evidence_classification(row) == "reviewed_commercial_facts_unknown"
    result = summarize_buyer_capacity([row], observed_at=NOW)
    assert result["terms_verified"] == 0
    assert result["allocation_ready"] is False
    assert result["classification_establishes_commercial_verification"] is False


def test_identity_marker_detection_is_not_arbitrary_substring_matching():
    from empire_os.buyer_allocation import buyer_identity_quality_hold
    row = activated_buyer()
    row.update(buyer_name="Latest Roofing", commercial_terms_reference="contract:test-reference")
    assert buyer_identity_quality_hold(row) is None
