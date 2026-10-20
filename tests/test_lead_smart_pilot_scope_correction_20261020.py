"""Founder corrected Lead Smart scope to a 10–20-minute supervised pilot."""
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from empire_os.lead_smart_site_handoff import CAMPAIGN, NUMBER, SCHEMA, _control, HandoffHeld
from scripts.activate_lead_smart_supervised_retry import revised_control, window
from scripts.materialize_lead_smart_launch_readiness import (
    founder_full_campaign_approved, founder_launch_approved
)

ROOT = Path(__file__).resolve().parents[1]

def old_campaign():
    return {
        "schema_version": SCHEMA,
        "campaign_id": CAMPAIGN,
        "tracking_number": NUMBER,
        "mode": "FULL_CAMPAIGN",
        "enabled": False,
        "starts_at": "2026-10-20T13:00:00+00:00",
        "ends_at": "2026-10-27T13:00:00+00:00",
        "max_site_handoffs": 140,
        "max_daily_site_handoffs": 20,
        "buyer_live_authorization_ref":"gmail:1a1551ac7204ff8a",
        "founder_authority_ref":"docs/evidence/lead_smart_full_campaign_founder_directive_20261020.json",
        "traffic_source":"EMPIRE_FIRST_PARTY_ORGANIC",
        "stop_method":"atomic_site_handoff_gate",
    }

def test_founder_correction_supersedes_old_full_directive():
    correction = json.loads((ROOT/"docs/evidence/lead_smart_full_campaign_scope_correction_20261020.json").read_text())
    assert correction["founder_scope"]=="SUPERVISED_PILOT_ONLY"
    assert correction["seven_day_live_campaign_authorized"] is False
    assert correction["future_pilot_automatically_authorized"] is False
    assert founder_full_campaign_approved(root=ROOT) is False
    assert founder_launch_approved(root=ROOT) is True

def test_seven_day_runtime_revoke_blocks_even_if_already_enabled():
    control = {**old_campaign(), "enabled": True, "full_campaign_scope_revoked": True}
    with pytest.raises(HandoffHeld):
        _control(control, datetime(2026,10,20,18,10,tzinfo=timezone.utc))

def test_new_pilot_drops_seven_day_authority():
    start,end=window("2026-10-21T10:00",15)
    candidate=revised_control(old_campaign(),start,end,5)
    assert candidate["mode"]=="SUPERVISED_PILOT"
    assert candidate["enabled"] is False
    assert candidate["max_site_handoffs"]==5
    assert "max_daily_site_handoffs" not in candidate
    assert candidate["founder_authority_ref"]=="docs/evidence/lead_smart_founder_launch_intent_20261011.json"
    assert (end-start).total_seconds()==900

@pytest.mark.parametrize("minutes",[0,9,21,60,10080])
def test_pilot_duration_is_10_to_20_minutes(minutes):
    with pytest.raises(ValueError):
        window("2026-10-21T10:00",minutes)
