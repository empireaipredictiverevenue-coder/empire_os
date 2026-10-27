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

def test_switchboard_reuses_existing_analytics_and_explicit_current_pilot_architecture(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "PARKED")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "false")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "false")
    r = preview_pay_per_call_route(
        prospect(), qualification(), identity_link(), [buyer()]
    )
    stack = r["current_pilot_stack_migration_preview"]
    assert stack["scope"] == "LEAD_SMART_US_ROOFING_ONLY"
    assert stack["existing_telephony_observer"] == "ringba"
    assert stack["existing_first_party_database"] == "EmpireDB PostgreSQL"
    assert stack["legacy_policy_database"] == "supabase"
    assert stack["legacy_policy_transport"] == "vonage"
    assert not stack["legacy_stack_can_be_reused_as_live_executor"]
    assert not stack["live_ringba_buyer_leg_verified"]
    analytics = r["owned_analytics_reuse"]
    assert analytics["existing_event_contract"] == (
        "empire.analytics.first_party_event_contract.v1"
    )
    assert analytics["event_ingestion_mode"] == "DORMANT_OFFLINE_SIMULATION_ONLY"
    assert "organic_search" in analytics["existing_offline_channels"]
    assert "paid_search" not in analytics["existing_offline_channels"]
    assert "paid_search" in analytics["future_source_families_for_owner_review"]
    assert "phone_inbound" in analytics["future_source_families_for_owner_review"]
    assert analytics["channel_schema_extension_approved"] is False
    assert analytics["new_tracking_database_created"] is False
    assert not r["provider_call_created"] and not r["payment_action"]


def test_legacy_active_flags_cannot_claim_working_ppc_executor(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "ACTIVE")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "true")
    r = preview_pay_per_call_route(
        prospect(), qualification(), identity_link(), [buyer()]
    )
    assert r["underlying_allocation_decision"] == "ready"
    assert r["decision"] == "REVIEW_ONLY_EXECUTOR_NOT_IMPLEMENTED"
    assert r["reason"] == "legacy_flags_cannot_activate_canonical_ppc_executor"
    assert r["route_executed"] is False
    assert r["provider_call_created"] is False
    assert r["payment_action"] is False
    assert r["execution_authority"] == "none"
    with pytest.raises(RuntimeError, match="execution is parked"):
        execute_pay_per_call_route()
