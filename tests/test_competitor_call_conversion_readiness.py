"""Existing owner traffic, media, and protected settlement evidence stay distinct."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from empire_os.competitor_call_conversion_readiness import build_readiness
from empire_os.competitor_intelligence_feed import build_feed_runtime

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def owner_sources():
    return {
        "gsc": {
            "schema_version": "empire.search.seo_growth_action_queue.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "source_property": "sc-domain:empire-ai.co.uk",
            "database_writes": False, "outbound_sent": False,
            "as_of": "2026-10-26",
            "gsc_returned_page_rows": 33,
            "gsc_pages_without_reported_row": 19,
            "keyword_exact_query_matches": 0,
        },
        "youtube": {
            "schema_version": "empire.media.youtube_growth_command_centre.v1",
            "mode": "OBSERVE", "execution_authority": "none",
            "source": "youtube_analytics_api",
            "observed_at": "2026-10-18T22:25:09+00:00",
            "owned_analytics_authenticated": True,
            "automatic_upload_authorized": False,
            "verified_website_traffic": None,
            "verified_commercial_enquiries": None,
        },
        "sources": {
            "schema_version": "empire.call_traffic_source_registry.v1",
            "mode": "OBSERVE", "source_count": 15,
            "organic_earned_count": 7, "paid_candidate_count": 7,
            "policy_excluded_count": 1, "media_spend_authorized": False,
            "execution_authority": "none",
        },
    }


def built(data=None, state="PROTECTED_BY_COMMERCIAL_OWNER"):
    data = owner_sources() if data is None else data
    return build_readiness(gsc=data["gsc"], youtube=data["youtube"],
                           sources=data["sources"],
                           cash_source_state=state, now=NOW)


def test_source_evidence_not_fabricated_session_or_settlement():
    result = built()
    assert result["source_registry_available"] is True
    assert result["first_party_organic"]["available"] is True
    assert result["first_party_organic"]["gsc_page_rows"] == 33
    assert result["first_party_organic"]["direct_site_sessions_verified"] is False
    assert result["owned_youtube"]["available"] is True
    assert result["owned_youtube"]["verified_website_visits"] is None
    assert result["call_to_cash"]["source_state"] == "PROTECTED_BY_COMMERCIAL_OWNER"
    assert result["call_to_cash"]["protected_content_read"] is False
    assert result["call_to_cash"]["settled_revenue_usd"] is None
    assert len(result["measurement_chain_steps"]) == 6
    assert all(not r["verified"] and r["count"] is None
               for r in result["measurement_chain_steps"])
    assert result["exact_source_to_settlement_proven"] is False
    assert result["acquisition_source_profitability_calibrated"] is False


def test_existing_original_team_ownership_and_paid_source_remain_held():
    result = built()
    assert len(result["next_owner_actions"]) == 5
    assert result["next_owner_actions"][0]["owner"] == "ORIGINAL_SEARCH_INTELLIGENCE_AND_WEBSITE_OWNERS"
    assert result["next_owner_actions"][2]["owner"] == "ORIGINAL_LEAD_SMART_CALL_OWNER"
    assert result["ad_spend_authorized"] is False
    assert result["content_publication_authorized"] is False
    assert result["database_writes"] is False
    assert result["external_send_authorized"] is False
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize("mutation", [
    lambda x: x["gsc"].update(mode="LIVE"),
    lambda x: x["gsc"].update(outbound_sent=True),
    lambda x: x["gsc"].update(source_property="sc-domain:competitor.com"),
    lambda x: x["gsc"].update(gsc_returned_page_rows=-3),
    lambda x: x["gsc"].update(as_of="2025-01-01"),
    lambda x: x["youtube"].update(automatic_upload_authorized=True),
    lambda x: x["youtube"].update(observed_at="2026-01-01T00:00:00+00:00"),
    lambda x: x["sources"].update(media_spend_authorized=True),
])
def test_unverified_owner_source_is_unavailable_not_fabricated(mutation):
    data = copy.deepcopy(owner_sources())
    mutation(data)
    result = built(data)
    assert not result["exact_source_to_settlement_proven"]
    assert not result["ad_spend_authorized"]
    assert not result["acquisition_source_profitability_calibrated"]


def test_no_sources_are_a_valid_unproven_observation():
    result = build_readiness(gsc=None, youtube=None, sources=None,
                             cash_source_state="ABSENT", now=NOW)
    assert result["first_party_organic"]["available"] is False
    assert result["first_party_organic"]["gsc_page_rows"] is None
    assert result["owned_youtube"]["verified_website_visits"] is None
    assert result["call_to_cash"]["settled_revenue_usd"] is None


def test_invalid_commercial_source_state_is_rejected():
    with pytest.raises(ValueError):
        build_readiness(gsc=None, youtube=None, sources=None,
                        cash_source_state="SETTLEMENT_VERIFIED", now=NOW)


def test_original_founder_feed_does_not_let_observe_become_paid(tmp_path):
    from empire_os.competitor_call_channel_atlas import SOURCE as ATLAS, build_atlas
    root = Path(__file__).resolve().parents[1]
    p = tmp_path / "runtime/competitive_intelligence"
    p.mkdir(parents=True)
    atlas = build_atlas(json.loads((root / ATLAS).read_text()), now=NOW)
    (p / "call_acquisition_atlas_latest.json").write_text(json.dumps(atlas))
    (p / "competitor_intelligence_feed_latest.json").write_text(
        '{"canonical_company_count":14}')
    packet = built()
    (p / "call_conversion_readiness_latest.json").write_text(json.dumps(packet))
    visible = build_feed_runtime(tmp_path)["call_acquisition_intelligence"]["conversion_evidence_readiness"]
    assert visible["available"] is True
    assert visible["first_party_organic"]["gsc_page_rows"] == 33
    assert visible["exact_source_to_settlement_proven"] is False
    packet["ad_spend_authorized"] = True
    (p / "call_conversion_readiness_latest.json").write_text(json.dumps(packet))
    rejected = build_feed_runtime(tmp_path)["call_acquisition_intelligence"]["conversion_evidence_readiness"]
    assert rejected["available"] is False

def test_dynamic_weekly_report_reader_follows_existing_owner_export(tmp_path):
    from empire_os.competitor_call_conversion_readiness import _latest_gsc_review
    folder = tmp_path / "weekly"
    folder.mkdir()
    (folder / "weekly_seo_growth_actions_2026-10-20.json").write_text(
        json.dumps({"as_of": "2026-10-20", "page_rows": 5}))
    (folder / "weekly_seo_growth_actions_2026-10-26.json").write_text(
        json.dumps({"as_of": "2026-10-26", "page_rows": 33}))
    (folder / "fake_weekly_seo_growth_actions_2026-10-30.json").write_text(
        json.dumps({"as_of": "2026-10-30", "page_rows": 2000}))
    assert _latest_gsc_review(folder)["page_rows"] == 33
    assert _latest_gsc_review(tmp_path / "missing") is None
