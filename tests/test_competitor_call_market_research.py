"""Evidence-backed acquisition research cannot be mistaken for real calls."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.competitor_call_market_research import SOURCE, build_market_research
from empire_os.competitor_intelligence_feed import build_feed_runtime

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)


def dataset():
    return json.loads((ROOT / SOURCE).read_text())


def test_eight_operator_market_research_complete():
    research = build_market_research(dataset(), now=NOW)
    assert research["operator_count"] == 8
    assert research["distinct_primary_sources_count"] == 12
    assert research["operators_by_observed_channel"]["affiliate_publishers"] == 8
    assert research["documented_reported_indicator_count"] == 4
    assert research["business_model_research_pass_complete"] is True
    assert research["channel_conversion_performance_established"] is False
    assert research["ranking_of_profitable_channels_verified"] is False


def test_numbers_are_source_classified_never_inferred_calls():
    research = build_market_research(dataset(), now=NOW)
    angi = next(x for x in research["operators"] if x["operator_id"] == "angi")
    assert any(x["value"] == 323470000 and x["source_class"] == "REGULATORY_FILING"
               for x in angi["reported_indicators"])
    assert all(not x["qualified_calls_audited"] for x in research["operators"])
    assert research["paid_traffic_enabled"] is False
    assert research["outbound_enabled"] is False
    assert research["live_call_traffic_authorized"] is False
    assert research["measurement_contract"]["buyer_accepted_payable_calls"] == "UNKNOWN"
    assert research["measurement_contract"]["independently_paid_settlement_usd"] == "UNKNOWN"


@pytest.mark.parametrize("change", [
    lambda x: x["operators"][0]["source_urls"].append("http://www.sec.gov/test"),
    lambda x: x["operators"][0]["channel_families"].append("unknown"),
    lambda x: x["operators"][0].update(id="elocal"),
    lambda x: x["operators"].pop(),
    lambda x: x["measurement_contract"].update(connected_calls=99),
    lambda x: x["prohibitions"].update(outbound_enabled=True),
    lambda x: x.update(observed_at_utc="2028-01-01T00:00:00+00:00"),
])
def test_source_or_execution_contract_tamper_fails_closed(change):
    original = copy.deepcopy(dataset())
    change(original)
    with pytest.raises((ValueError, TypeError)):
        build_market_research(original, now=NOW)


def test_original_founder_feed_exposes_separate_operators(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS, build_atlas
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    (runtime / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14,"metro":"denver, co"}')
    atlas = build_atlas(json.loads((ROOT / ATLAS).read_text()), now=NOW)
    (runtime / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    market = build_market_research(dataset(), now=NOW)
    (runtime / "call_acquisition_market_research_latest.json").write_text(json.dumps(market))
    result = build_feed_runtime(tmp_path)
    assert result["canonical_company_count"] == 14
    research = result["call_acquisition_intelligence"]["business_model_research"]
    assert research["available"] is True
    assert research["operator_count"] == 8
    assert research["execution_authority"] == "none"


def test_founder_feed_rejects_paid_activation(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS, build_atlas
    runtime = tmp_path / "runtime/competitive_intelligence"
    runtime.mkdir(parents=True)
    (runtime / "call_acquisition_atlas_latest.json").write_text(json.dumps(
        build_atlas(json.loads((ROOT / ATLAS).read_text()), now=NOW)))
    bad = build_market_research(dataset(), now=NOW)
    bad["paid_traffic_enabled"] = True
    (runtime / "call_acquisition_market_research_latest.json").write_text(json.dumps(bad))
    feed = build_feed_runtime(tmp_path)
    assert feed["call_acquisition_intelligence"]["business_model_research"]["available"] is False
