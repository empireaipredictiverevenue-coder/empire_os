from uuid import uuid4

from empire_os.omega_buyer_readiness import (
    assess_omega_buyer_readiness,
    omega_readiness_decision,
)


def fixture_rows():
    prospect_id = str(uuid4())
    entity_id = str(uuid4())
    qualification_id = str(uuid4())
    prospect = {
        "id": prospect_id,
        "business_name": "Real Roofing Co",
        "niche": "roofing",
        "metro": "Austin, TX",
        "status": "qualified",
    }
    qualification = {
        "id": qualification_id,
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "score": 82.0,
        "tier": "hot",
        "status": "scored",
        "scoring_engine": "empire_os.lead_scoring",
        "scoring_version": "v2",
        "evidence_confidence": 0.60,
    }
    identity = {
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "match_score": 1.0,
        "active": True,
    }
    omega = {
        "entity_id": entity_id,
        "score_type": "omega_opportunity",
        "score": 81.2,
        "confidence": 0.60,
        "model_key": "omega-2.0-baseline",
        "features": {
            "prospect_id": prospect_id,
            "qualification_id": qualification_id,
            "expected_revenue": None,
            "expected_gross_profit": None,
        },
    }
    return prospect, qualification, identity, omega


def activated_buyer(**overrides):
    row = {
        "id": str(uuid4()),
        "buyer_name": "Verified Austin Buyer",
        "niche": "roofing",
        "metro": "Austin, TX",
        "is_active": True,
        "status": "active",
        "daily_cap": 10,
        "calls_today": 0,
        "priority": 80,
        "per_lead_rate": 100,
        "base_payout": None,
        "commercial_activation_state": "activated",
        "reviewed_at": "2026-09-20T10:00:00Z",
        "commercial_activated_at": "2026-09-20T10:01:00Z",
        "commercial_terms_source": "manual_contract",
        "commercial_terms_reference": "contract:verified",
        "commercial_terms_verified_at": "2026-09-20T10:01:00Z",
        "capacity_verified_at": "2026-09-20T10:01:00Z",
        "delivery_verified_at": "2026-09-20T10:01:00Z",
        "destination_phone": "+15125550123",
        "webhook_url": None,
    }
    row.update(overrides)
    return row


def test_omega_readiness_requires_evidence_floor():
    _, qualification, identity, omega = fixture_rows()
    omega["confidence"] = 0.49

    allowed, reason = omega_readiness_decision(
        omega,
        qualification,
        identity,
    )

    assert allowed is False
    assert reason == "omega_confidence_below_floor"


def test_omega_readiness_fails_closed_on_identity_mismatch():
    _, qualification, identity, omega = fixture_rows()
    identity["entity_id"] = str(uuid4())

    allowed, reason = omega_readiness_decision(
        omega,
        qualification,
        identity,
    )

    assert allowed is False
    assert reason == "identity_entity_mismatch"


def test_verified_buyer_capacity_is_observed_without_allocating():
    prospect, qualification, identity, omega = fixture_rows()

    result = assess_omega_buyer_readiness(
        prospect=prospect,
        qualification=qualification,
        identity_link=identity,
        omega_score=omega,
        buyers=[activated_buyer()],
    )

    assert result["decision"] == "buyer_capacity_ready"
    assert result["buyer_capacity_ready"] is True
    assert result["candidate_count"] == 1
    assert result["allocation_executed"] is False
    assert result["recognized_revenue_written"] is False
    assert result["expected_revenue"] is None
    assert result["expected_gross_profit"] is None


def test_missing_verified_buyer_capacity_is_explicit_blocker():
    prospect, qualification, identity, omega = fixture_rows()

    result = assess_omega_buyer_readiness(
        prospect=prospect,
        qualification=qualification,
        identity_link=identity,
        omega_score=omega,
        buyers=[activated_buyer(commercial_terms_verified_at=None)],
    )

    assert result["decision"] == "no_verified_buyer_capacity"
    assert result["reason"] == "no_eligible_buyer_capacity"
    assert result["buyer_capacity_ready"] is False
    assert result["candidate_count"] == 0
    assert result["allocation_executed"] is False
