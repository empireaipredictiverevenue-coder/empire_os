"""Recover existing PPC switchboard/hub architecture without execution."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_intelligence_feed import (
    _existing_ppc_switchboard_hub_readiness, build_feed_runtime,
)
from empire_os.ppc_switchboard_adapter import execute_pay_per_call_route

ROOT = Path(__file__).resolve().parents[1]


def test_reuses_existing_switchboard_and_hubs_not_new_services(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "PARKED")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "false")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "false")
    r = _existing_ppc_switchboard_hub_readiness(ROOT)
    assert r["canonical_switchboard_adapter_present"]
    assert r["legacy_agent_switchboard_present"]
    assert r["legacy_ppc_router_present"]
    assert r["existing_central_hub_source_present"]
    assert r["existing_buyer_marketplace_present"]
    assert r["existing_call_manager_present"]
    assert r["existing_voice_gateway_present"]
    assert r["status"] == "EXISTING_ADAPTER_PARKED_PREVIEW_ONLY"
    assert r["voice_switchboard_policy_mode"] == "PARKED"
    assert r["current_policy_legacy_transport"] == "vonage"
    assert r["current_policy_legacy_database"] == "supabase"
    assert r["hub_source_presence_is_not_live_service_proof"]
    assert r["legacy_executor_must_not_be_activated"]
    first_party = r["existing_empire_analytics"]
    assert first_party["event_contract"] == "empire.analytics.first_party_event_contract.v1"
    assert first_party["staged_analytics054_source_present"]
    assert first_party["existing_dormant_ingress_source_present"]
    assert "organic_search" in first_party["offline_channel_classes"]
    assert "paid_search" not in first_party["offline_channel_classes"]
    assert "cta_click" in first_party["offline_event_types"]
    assert first_party["production_collection_authorized"] is False
    assert first_party["real_sessions_verified"] is False
    assert first_party["commercial_call_attribution_verified"] is False
    assert first_party["new_tracking_platform_created"] is False
    assert r["routing_authorized"] is False
    assert r["execution_authority"] == "none"
    with pytest.raises(RuntimeError, match="execution is parked"):
        execute_pay_per_call_route()


def test_legacy_flags_do_not_grant_executor(monkeypatch):
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "ACTIVE")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "true")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "true")
    r = _existing_ppc_switchboard_hub_readiness(ROOT)
    assert r["voice_policy_flags_request_execution"] is True
    assert r["status"] == "LEGACY_FLAG_CONFLICT_NEEDS_OWNER_REVIEW"
    assert r["routing_authorized"] is False
    assert r["provider_route_verified"] is False
    assert r["settled_cash_verified"] is False
    with pytest.raises(RuntimeError, match="execution is parked"):
        execute_pay_per_call_route()


def test_original_competitor_reader_surfaces_existing_infrastructure(tmp_path, monkeypatch):
    from empire_os.competitor_call_channel_atlas import SOURCE, build_atlas

    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_MODE", "PARKED")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_ROUTE_ENABLED", "false")
    monkeypatch.setenv("EMPIRE_PPC_SWITCHBOARD_CANONICAL_READY", "false")
    dest = tmp_path / "runtime/competitive_intelligence"
    dest.mkdir(parents=True)
    (dest / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14}')
    original = json.loads((ROOT / SOURCE).read_text())
    atlas = build_atlas(original, now=datetime(2026, 10, 27, 14, tzinfo=timezone.utc))
    (dest / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    existing = build_feed_runtime(tmp_path)
    overlay = existing["call_acquisition_intelligence"]["existing_switchboard_and_hubs"]
    assert existing["canonical_company_count"] == 14
    assert overlay["schema_version"] == "empire.ppc.existing_switchboard_hub_readiness.v1"
    assert overlay["new_hub_or_switchboard_created"] is False
    assert overlay["hub_live_service_verified"] is False
    assert overlay["execution_authority"] == "none"
