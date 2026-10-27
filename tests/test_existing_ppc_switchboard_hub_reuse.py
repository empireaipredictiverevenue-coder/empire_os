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

def _original_launch_fixture():
    return {
        "schema_version": "empire.lead_smart.launch_readiness.v1",
        "mode": "PREACTIVATION",
        "launch_ready": False,
        "blockers": [
            "recording_notice_and_retention_verified", "pilot_stop_verified",
            "operating_hours_verified", "caller_id_pass_through_verified",
            "routing_runtime_verified",
        ],
        "call_cta_enabled": False,
        "organic_traffic_authorized": False,
        "provider_route_mutation": False,
        "deployment_performed": False,
        "execution_authority": "NONE",
        # Never copy these original-owner details into public research.
        "commercial_truth": {"private_recipient_id": "TEST-PRIVATE"},
        "recording_details": {"recording_url": "https://example.invalid/private"},
    }


def test_original_owner_source_readiness_projects_all_five_blockers_without_details():
    from empire_os.competitor_intelligence_feed import (
        _original_pilot_readiness_projection,
    )
    r = _original_pilot_readiness_projection(_original_launch_fixture())
    assert r["schema_version"] == "empire.ppc.original_pilot_preflight_overlay.v1"
    assert r["available"] is True and r["mode"] == "OBSERVE"
    assert r["blocker_count"] == 5
    assert len(r["owner_actions"]) == 5
    assert r["owner_actions"][0]["original_owner"] == "ORIGINAL_PRIVACY_AND_RECORDING_OWNER"
    assert r["owner_actions"][-1]["original_owner"] == "ORIGINAL_RINGBA_ROUTE_OWNER"
    assert not r["original_owner_reports_ready"]
    assert not r["this_feed_can_activate_traffic"]
    assert not r["this_feed_can_authorize_calls"]
    assert not r["this_feed_can_settle_revenue"]
    assert r["execution_authority"] == "none"
    assert "private_recipient_id" not in repr(r)
    assert "TEST-PRIVATE" not in repr(r)
    assert "recording_url" not in repr(r)


@pytest.mark.parametrize("modify", [
    lambda r: r.update(execution_authority="RUN"),
    lambda r: r.update(provider_route_mutation=True),
    lambda r: r.update(deployment_performed=True),
    lambda r: r.update(blockers=[]),
    lambda r: r.update(blockers=["recording_notice_and_retention_verified"] * 2),
    lambda r: r.update(blockers=["caller ANI +1888"]),
    lambda r: r.update(launch_ready=True),
    lambda r: r.update(mode="INVALID"),
    lambda r: r.update(call_cta_enabled="false"),
])
def test_pilot_projection_rejects_untrusted_or_unsafe_review(modify):
    from empire_os.competitor_intelligence_feed import (
        _original_pilot_readiness_projection,
    )
    r = _original_launch_fixture()
    modify(r)
    with pytest.raises(ValueError):
        _original_pilot_readiness_projection(r)


def test_pilot_overlay_without_original_control_is_unknown(tmp_path):
    from empire_os.competitor_intelligence_feed import (
        _original_pilot_readiness_overlay,
    )
    report = _original_pilot_readiness_overlay(tmp_path)
    assert report["available"] is False
    assert report["status"] == "ORIGINAL_PILOT_SOURCE_NOT_PRESENT"
    assert report["execution_authority"] == "none"


def test_pilot_overlay_reuses_original_review_not_stale_snapshots(tmp_path, monkeypatch):
    from empire_os.competitor_intelligence_feed import (
        _original_pilot_readiness_overlay,
    )
    from scripts import materialize_lead_smart_launch_readiness as original
    p = tmp_path / "runtime/revenue/lead_smart/pilot/approved_control.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    called = []
    def original_review(*, repo_root, evidence_root):
        called.append((repo_root, evidence_root))
        return _original_launch_fixture()
    monkeypatch.setattr(original, "compute_live_launch_readiness", original_review)
    report = _original_pilot_readiness_overlay(tmp_path)
    assert report["available"] is True and report["blocker_count"] == 5
    assert len(called) == 1 and called[0][0] == tmp_path
    assert called[0][1] == tmp_path / "runtime/revenue/lead_smart"


def test_bad_original_owner_review_is_unknown_not_granted(tmp_path, monkeypatch):
    from empire_os.competitor_intelligence_feed import (
        _original_pilot_readiness_overlay,
    )
    from scripts import materialize_lead_smart_launch_readiness as original
    p = tmp_path / "runtime/revenue/lead_smart/pilot/approved_control.json"
    p.parent.mkdir(parents=True)
    p.write_text("{}")
    monkeypatch.setattr(original, "compute_live_launch_readiness",
                        lambda **_kwargs: {"execution_authority": "LIVE"})
    report = _original_pilot_readiness_overlay(tmp_path)
    assert report["available"] is False
    assert report["status"] == "ORIGINAL_OWNER_READINESS_UNVERIFIED"
    assert report["execution_authority"] == "none"
