import pytest

from empire_os.ppc_switchboard_adapter import (
    execute_pay_per_call_route,
    preview_pay_per_call_route,
)


PROSPECT_ID = "11111111-1111-4111-8111-111111111111"
ENTITY_ID = "22222222-2222-4222-8222-222222222222"


def prospect():
    return {
        "id": PROSPECT_ID,
        "business_name": "Austin Roof Co",
        "niche": "roofing",
        "metro": "Austin, TX",
    }


def qualification():
    return {
        "prospect_id": PROSPECT_ID,
        "entity_id": ENTITY_ID,
        "score": 82,
        "tier": "hot",
        "status": "scored",
        "scoring_version": "v2",
        "evidence_confidence": 0.75,
    }


def identity_link():
    return {
        "prospect_id": PROSPECT_ID,
        "entity_id": ENTITY_ID,
        "match_score": 1.0,
        "active": True,
        "created_at": "2026-09-22T10:00:00Z",
    }


def buyer():
    return {
        "id": "buyer-1",
        "buyer_name": "Austin Buyer",
        "niche": "roofing",
        "metro": "Austin, TX",
        "is_active": True,
        "status": "active",
        "daily_cap": 10,
        "calls_today": 0,
        "priority": 50,
        "per_lead_rate": 75,
        "base_payout": None,
        "commercial_activation_state": "activated",
        "reviewed_at": "2026-09-22T10:00:00Z",
        "commercial_activated_at": "2026-09-22T10:01:00Z",
        "commercial_terms_source": "signed_agreement",
        "commercial_terms_reference": "agreement:buyer-1",
        "commercial_terms_verified_at": "2026-09-22T10:02:00Z",
        "capacity_verified_at": "2026-09-22T10:03:00Z",
        "delivery_verified_at": "2026-09-22T10:04:00Z",
        "destination_phone": "+15126401234",
        "webhook_url": None,
    }


def test_switchboard_preview_uses_canonical_buyer_truth_but_stays_parked(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "PARKED")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "false")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "false")

    result = preview_pay_per_call_route(
        prospect(),
        qualification(),
        identity_link(),
        [buyer()],
    )

    assert result["decision"] == "PARKED"
    assert result["underlying_allocation_decision"] == "ready"
    assert result["selected_candidate"]["buyer_id"] == "buyer-1"
    assert result["selected_candidate"]["delivery_channel"] == "phone"
    assert result["route_executed"] is False
    assert result["payment_action"] is False
    assert result["payment_rail"] == "usdt_bsc"
    assert result["actual_revenue"] is False
    assert result["execution_authority"] == "none"


def test_switchboard_executor_is_hard_stopped():
    with pytest.raises(RuntimeError, match="execution is parked"):
        execute_pay_per_call_route()
