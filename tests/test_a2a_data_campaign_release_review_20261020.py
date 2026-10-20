"""Verify all A2A commercial campaign drafts remain release-gated."""
from datetime import datetime, timezone
import pytest

from empire_os.a2a_commercial_signal_miner import mine_signals
from empire_os.a2a_data_campaign_experiments import build_data_campaign_experiments
from empire_os.a2a_data_campaign_release_review import assess_campaign_readiness
from empire_os.a2a_nyc_commercial_evidence_gate import inspect_nyc_pilot
from tests.test_a2a_commercial_signal_miner_20261020 import community, gps
from tests.test_a2a_nyc_commercial_evidence_gate_20261020 import inputs


def build():
    now = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)
    signals = mine_signals(community=community(), revenue_gps=gps(), now=now)
    campaigns = build_data_campaign_experiments(signals)
    evidence = inspect_nyc_pilot(**inputs())
    return campaigns, evidence


def test_nyc_release_is_held():
    campaigns, evidence = build()
    result = assess_campaign_readiness(campaigns, evidence)
    assert result["reviewed_campaign_count"] == 2
    assert result["launch_ready_campaign_count"] == 0
    assert all(not item["live_campaign_authorized"] for item in result["campaigns"])
    assert "NO_APPROVED_NYC_BUYERS_IN_SOURCE_SNAPSHOT" in result["campaigns"][0]["hold_reasons"]


def test_elevated_permissions_not_allowed():
    campaigns, evidence = build()
    campaigns["campaigns"][0]["publishing_authorised"] = True
    with pytest.raises(ValueError):
        assess_campaign_readiness(campaigns, evidence)


def test_claimed_buyers_cannot_authorise_campaigns():
    campaigns, evidence = build()
    evidence["market"]["approved_buyers_reported_by_source"] = 5
    evidence["hold_reasons"] = []
    result = assess_campaign_readiness(campaigns, evidence)
    assert result["launch_ready_campaign_count"] == 0
    assert not result["campaigns"][0]["live_campaign_authorized"]
