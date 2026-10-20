import json
from datetime import datetime, timezone
import pytest

from empire_os.agents.meta_market_validation_agent import (
    AGENT_SCHEMA, DEFAULT_LANES, run_agent,
)
from empire_os.meta_social_opportunity_research import SCHEMA as EVIDENCE_SCHEMA

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)


def observation(platform, kind, url, niche="hvac", us_zip="85001"):
    return {
        "platform": platform, "kind": kind,
        "source_url": url, "niche": niche, "us_zip": us_zip,
        "rights_status": "verified_permitted",
        "access_method": "authorised_manual_review",
        "subject_type": "business" if kind == "business_supply" else "aggregated",
        "observed_at": NOW.isoformat(),
    }


def test_agent_without_input_works_and_queues_research_not_revenue():
    report = run_agent(now=NOW)
    assert report["schema_version"] == AGENT_SCHEMA
    assert report["status"] == "PENDING_REAL_AUTHORISED_EVIDENCE"
    assert len(report["lanes"]) == 2
    assert report["research_task_count"] == 12
    assert all(lane["phase"] == "RESEARCH_HOLD" for lane in report["lanes"])
    assert all(lane["verified_payers"] == 0 for lane in report["lanes"])
    assert not report["authority"]["crm_writes"]
    assert not report["authority"]["publish_or_send"]
    assert not report["authority"]["ad_spend"]


def test_authorised_market_match_still_cannot_activate_or_infer_revenue():
    packet = {
        "schema_version": EVIDENCE_SCHEMA,
        "observations": [
            observation("facebook_group", "aggregate_demand",
                        "https://facebook.com/groups/one/posts/101"),
            observation("facebook_group", "aggregate_demand",
                        "https://facebook.com/groups/two/posts/102"),
            observation("instagram", "business_supply",
                        "https://instagram.com/approved_pro_business/"),
        ],
    }
    report = run_agent(evidence_packet=packet, now=NOW)
    lane = report["lanes"][0]
    assert lane["hypothesis_present"]
    assert lane["independent_demand_sources_observed"] == 2
    assert lane["business_supply_evidence_observed"] == 1
    assert lane["next_step"] == "VERIFY_PROVIDER_WILLINGNESS_AND_PAYER_TERMS"
    assert lane["verified_willing_providers"] == 0
    assert lane["independently_reconciled_purchases"] == 0
    assert lane["traffic_activation_authorized"] is False


def test_synthetic_packets_are_never_treated_as_verified_market_evidence():
    packet = {"schema_version": EVIDENCE_SCHEMA, "synthetic": True,
              "observations": [
                  observation("facebook_group", "aggregate_demand",
                              "https://facebook.com/groups/test/posts/1"),
                  observation("instagram", "business_supply",
                              "https://instagram.com/test_business/"),
              ]}
    report = run_agent(evidence_packet=packet, now=NOW)
    assert report["status"] == "SYNTHETIC_TEST_ONLY"
    assert report["source_review"]["accepted"] == 0
    assert not any(lane["hypothesis_present"] for lane in report["lanes"])


def test_unsupported_evidence_and_lanes_are_rejected():
    with pytest.raises(ValueError):
        run_agent(evidence_packet={"schema_version": "bad", "observations": []}, now=NOW)
    with pytest.raises(ValueError):
        run_agent(lanes=({"id": "x", "niche": "hvac", "city": "Test", "us_zip": "bad"},), now=NOW)
    with pytest.raises(ValueError):
        run_agent(lanes=(DEFAULT_LANES[0], DEFAULT_LANES[0]), now=NOW)


def test_serialisation_is_deterministic_given_same_time():
    x = run_agent(now=NOW)
    y = run_agent(now=NOW)
    assert json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True)
