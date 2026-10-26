"""Prevent public call-market research from becoming fabricated traffic/terms."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_call_channel_atlas import SOURCE, SCHEMA, build_atlas, refresh
from empire_os.competitor_intelligence_feed import build_feed_runtime


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)


def evidence():
    return json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))


def test_five_real_operator_research_profiles_and_provenance():
    report = build_atlas(evidence(), now=NOW)
    assert report["schema_version"] == SCHEMA
    assert report["operator_count"] == 5
    assert report["source_count"] == 9
    assert report["channel_evidence_edge_count"] > 50
    assert len(report["next_research_actions"]) == 5
    assert any(item["id"] == "chicago_permit_data"
               for item in report["demand_sensor_catalog"])
    assert any(p["operator_id"] == "modernize"
               and "publisher_partners" in p["channels"]
               and "cpl" in p["payment_models"]
               for p in report["operator_profiles"])
    assert any(x["from"] == "elocal" and x["to"] == "qualification:ivr"
               and x["source_url"].startswith("https://www.elocal.com/")
               for x in report["evidence_graph_edges"])
    assert all(edge["independently_measured"] is False
               for edge in report["evidence_graph_edges"])


def test_never_infer_traffic_volume_local_geo_or_revenue():
    report = build_atlas(evidence(), now=NOW)
    assert report["actual_channel_traffic_mix_verified"] is False
    assert report["competitor_search_rank_verified"] is False
    assert report["competitor_keywords_verified"] is False
    assert report["payable_lead_or_revenue_verified"] is False
    assert report["buyer_intent_inferred"] is False
    assert report["market_share_inferred"] is False
    assert report["prospect_created"] is False
    assert report["outreach_enabled"] is False
    assert report["execution_authority"] == "none"
    assert report["new_database_or_agent"] is False
    assert all(r["geo_scope_verified"] is False for r in report["operator_profiles"])
    assert all(r["publisher_eligibility_for_empire_verified"] is False
               for r in report["operator_profiles"])


@pytest.mark.parametrize("mutator", [
    lambda x: x["operators"][0]["observations"][0].update(
        {"url": "http://modernize.com/affiliates"}),
    lambda x: x["operators"][0]["observations"][0].update(
        {"url": "https://localhost/internal"}),
    lambda x: x["operators"][0]["observations"][0]["channels"].append("unknown_paid_secret"),
    lambda x: x["operators"][1].update({"id": "modernize"}),
    lambda x: x["operators"][2]["observations"][0].update(
        {"url": "https://attacker.example/"}),
    lambda x: x.update({"researched_at_utc": "2027-01-01T00:00:00+00:00"}),
])
def test_bad_evidence_fails_closed(mutator):
    record = copy.deepcopy(evidence())
    mutator(record)
    with pytest.raises((ValueError, TypeError)):
        build_atlas(record, now=NOW)


def test_original_feed_consumes_atlas_without_changing_local_competitors(tmp_path):
    atlas = tmp_path / "runtime/competitive_intelligence"
    atlas.mkdir(parents=True)
    existing = {
        "schema_version": "empire.competitor_intelligence_feed.v1",
        "canonical_company_count": 14,
        "niche": "roofing",
        "metro": "denver, co",
        "outreach_enabled": False,
        "execution_authority": "none",
    }
    (atlas / "competitor_intelligence_feed_latest.json").write_text(
        json.dumps(existing))
    (atlas / "call_acquisition_atlas_latest.json").write_text(
        json.dumps(build_atlas(evidence(), now=NOW)))
    runtime = build_feed_runtime(tmp_path)
    assert runtime["available"] is True
    assert runtime["canonical_company_count"] == 14
    assert runtime["metro"] == "denver, co"
    overlay = runtime["call_acquisition_intelligence"]
    assert overlay["available"] is True
    assert overlay["operator_count"] == 5
    assert overlay["national_operator_roster_distinct_from_local_contractors"]
    assert overlay["outreach_enabled"] is False


def test_original_feed_does_not_trust_unvalidated_overlay(tmp_path):
    atlas = tmp_path / "runtime/competitive_intelligence"
    atlas.mkdir(parents=True)
    (atlas / "competitor_intelligence_feed_latest.json").write_text("{}")
    (atlas / "call_acquisition_atlas_latest.json").write_text(
        json.dumps({"schema_version": SCHEMA, "mode": "READY",
                    "outreach_enabled": True, "execution_authority": "live"}))
    r = build_feed_runtime(tmp_path)
    assert r["call_acquisition_intelligence"]["available"] is False
