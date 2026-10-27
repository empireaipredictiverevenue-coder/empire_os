"""Free/paid acquisition research remains evidence-only in original feed."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_call_traffic_sources import (
    SOURCE, SCHEMA, build_registry,
)
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def source():
    return json.loads((ROOT / SOURCE).read_text(encoding="utf-8"))


def test_fifteen_source_inventory_uses_no_made_up_performance():
    result = build_registry(source(), now=NOW)
    assert result["schema_version"] == SCHEMA
    assert result["source_count"] == 15
    assert result["organic_earned_count"] == 7
    assert result["paid_candidate_count"] == 7
    assert result["policy_excluded_count"] == 1
    assert result["free_or_earned"][0]["id"] == "organic_search"
    assert result["paid_research_only"][0]["id"] == "google_search_ads"
    assert [x["id"] for x in result["excluded"]] == ["google_lsa"]
    assert all(x["actual_traffic_volume"] is None for x in (
        result["free_or_earned"] + result["paid_research_only"] + result["excluded"]
    ))
    assert all(x["actual_paid_call_cpa_usd"] is None for x in result["paid_research_only"])
    assert all(value is None for value in result["outcome_measurement_contract"].values())


def test_paid_unfunded_and_lsa_resale_never_activates():
    result = build_registry(source(), now=NOW)
    assert not result["media_spend_authorized"]
    assert not result["ad_account_mutation"]
    assert not result["site_publication_authorized"]
    assert not result["outbound_authorized"]
    assert not result["provider_route_mutation"]
    assert not result["consumer_leads_inferred"]
    assert not result["buyer_acceptance_verified"]
    assert not result["settled_revenue_verified"]
    assert result["execution_authority"] == "none"
    assert all(x["status"] == "PAID_UNFUNDED_RESEARCH_ONLY"
               or x["status"] == "CONDITIONAL_ELIGIBILITY_REVIEW"
               for x in result["paid_research_only"])


@pytest.mark.parametrize("change", [
    lambda p: p["channels"][0].update(cost_class="PAID_CPC"),
    lambda p: p["channels"][0].update(actual_traffic_volume=1000),
    lambda p: p["channels"][0].update(research_rank=100),
    lambda p: p["channels"][0].update(sources=["http://example.test"]),
    lambda p: p["channels"][0].update(sources=["https://127.0.0.1/test"]),
    lambda p: p["channels"][0].update(permission_state="APPROVED_LIVE"),
    lambda p: p["channels"][-1].update(permission_state="PAID_DISABLED"),
    lambda p: p["global_controls"].update(media_spend_authority=True),
    lambda p: p["global_controls"].update(outbound_sent=True),
    lambda p: p.update(researched_at_utc="2028-01-01T00:00:00+00:00"),
    lambda p: p["channels"].pop(),
])
def test_bad_or_unauthorised_source_record_fails_closed(change):
    value = copy.deepcopy(source())
    change(value)
    with pytest.raises((ValueError, TypeError)):
        build_registry(value, now=NOW)


def test_original_founder_feed_receives_new_registry_without_changing_roster(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS_SOURCE, build_atlas
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    (runtime / "competitor_intelligence_feed_latest.json").write_text(
        json.dumps({"canonical_company_count": 14, "metro": "denver, co"}))
    atlas = build_atlas(json.loads((ROOT / ATLAS_SOURCE).read_text()), now=NOW)
    (runtime / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    registry = build_registry(source(), now=NOW)
    (runtime / "call_traffic_source_registry_latest.json").write_text(json.dumps(registry))
    result = build_feed_runtime(tmp_path)
    assert result["canonical_company_count"] == 14
    assert result["metro"] == "denver, co"
    traffic = result["call_acquisition_intelligence"]["traffic_source_research"]
    assert traffic["available"] is True
    assert traffic["source_count"] == 15
    assert traffic["policy_excluded_count"] == 1
    assert traffic["media_spend_authorized"] is False


def test_founder_feed_rejects_false_paid_activation(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS_SOURCE, build_atlas
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    atlas = build_atlas(json.loads((ROOT / ATLAS_SOURCE).read_text()), now=NOW)
    (runtime / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    registry = build_registry(source(), now=NOW)
    registry["media_spend_authorized"] = True
    (runtime / "call_traffic_source_registry_latest.json").write_text(json.dumps(registry))
    result = build_feed_runtime(tmp_path)
    assert result["call_acquisition_intelligence"]["traffic_source_research"]["available"] is False
