"""Marketing Agency handoff regression: source questions, link tagging, no sends."""
from urllib.parse import parse_qs, urlsplit
import pytest

from empire_os.jev_newsjack_marketing_handoff import prepare_marketing_director_handoff
from empire_os.jev_newsjack_traffic_briefs import prepare_editorial_traffic_reviews

NOW = "2026-10-18T13:50:00+00:00"
SOURCE = "https://www.gov.uk/government/speeches/building-an-energy-system-that-delivers-for-all"


def source_signal():
    return {
        "signal_id": "govuk:official-test",
        "title": "Building an energy system that delivers for all",
        "sector": "solar", "market": "GB",
        "primary_source_url": SOURCE,
        "published_at": "2026-10-14T14:46:56+00:00",
        "observed_at": NOW,
        "evidence_refs": ["govuk:content_api:official-test"],
    }


def inspecting(url):
    if url.endswith("/industries/solar"):
        title = "Solar Installer Coverage & Lead Qualification | Empire AI"
        headings = ["Solar growth starts with the right territory"]
    elif url.endswith("/commercial"):
        title = "AI Consultancy & Revenue Intelligence | Empire AI"
        headings = ["Turn the opportunity into a real proposal"]
    else:
        raise AssertionError("unapproved URL")
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED", "http_status": 200,
        "source_url": url, "page_title": title, "document_headings": headings,
        "content_sha256": "a" * 64,
    }


def review():
    return prepare_editorial_traffic_reviews(
        [source_signal()], as_of=NOW, inspector=inspecting
    )


def test_routes_into_existing_media_os_and_marketing_attribution():
    result = prepare_marketing_director_handoff(review(), generated_at=NOW)
    assert result["campaign_preview_count"] == 1
    job = result["campaign_previews"][0]
    assert job["campaign_owner"] == "existing_marketing_agency.marketing_director"
    assert job["content_draft"]["draft_status"] == "INTERNAL_DRAFT"
    assert job["content_draft"]["claim_verification_complete"] is False
    assert job["marketing_agency_ingested"] is False
    assert job["publication_ready"] is False
    assert job["jev_suggested_content_brief_above_threshold"] is False
    assert job["attribution_plan"]["capture_installed_or_verified"] is False
    assert job["attribution_plan"]["visitor_sessions"] is None
    assert job["attribution_plan"]["enquiries"] is None
    assert job["attribution_plan"]["required_chain"][-1] == "recognized_revenue"
    assert len(job["channel_previews"]) == 3
    assert all(a["public_publish_authorized"] is False for a in job["channel_previews"])


def test_utm_links_distinct_and_deterministic_and_owned():
    a = prepare_marketing_director_handoff(review(), generated_at=NOW)
    b = prepare_marketing_director_handoff(review(), generated_at=NOW)
    assert a == b
    channels = a["campaign_previews"][0]["channel_previews"]
    assert len({c["preview_url"] for c in channels}) == 3
    for channel in channels:
        parsed = urlsplit(channel["preview_url"])
        assert parsed.netloc == "empire-ai.co.uk"
        assert parsed.path == "/industries/solar"
        query = parse_qs(parsed.query)
        assert query["utm_campaign"] == [channel["campaign_id"]]
        assert query["utm_content"] == [channel["asset_id"]]
        assert query["utm_source"][0] in ("linkedin", "youtube", "owned_newsletter")


def test_failed_review_never_creates_campaign():
    packet = review()
    packet["review_queue"][0]["status"] = "HOLD_FOR_RESEARCH"
    assert prepare_marketing_director_handoff(
        packet, generated_at=NOW
    )["campaign_preview_count"] == 0


def test_forged_destination_or_wrong_digest_refused():
    packet = review()
    packet["review_queue"][0]["page_url"] = "https://evil.example/private"
    assert prepare_marketing_director_handoff(
        packet, generated_at=NOW
    )["campaign_preview_count"] == 0
    packet = review()
    packet["review_queue"][0]["page_content_sha256"] = "0" * 64
    assert prepare_marketing_director_handoff(
        packet, generated_at=NOW
    )["campaign_preview_count"] == 0


def test_holds_when_commercial_page_unverified():
    packet = review()
    packet["observed_owned_pages"]["https://empire-ai.co.uk/commercial"]["live_verified"] = False
    assert prepare_marketing_director_handoff(
        packet, generated_at=NOW
    )["campaign_preview_count"] == 0


def test_schema_authority_and_time_fail_closed():
    packet = review()
    packet["execution_authority"] = "publish"
    with pytest.raises(ValueError):
        prepare_marketing_director_handoff(packet, generated_at=NOW)
    packet = review()
    packet["live_publication"] = True
    with pytest.raises(ValueError):
        prepare_marketing_director_handoff(packet, generated_at=NOW)
    with pytest.raises(ValueError):
        prepare_marketing_director_handoff(review(), generated_at="2026-10-18")


def test_empty_review_has_no_assets_or_actions():
    r = prepare_editorial_traffic_reviews([], as_of=NOW, inspector=inspecting)
    p = prepare_marketing_director_handoff(r, generated_at=NOW)
    assert p["campaign_preview_count"] == 0
    assert p["external_publish_authorized"] is False


def test_low_confidence_jev_never_promotes_publish_readiness():
    packet = review()
    packet["review_queue"][0]["jev_classification"] = {
        "label": "content_brief",
        "confidence": 0.1233,
        "source_ref": "laya:shadow:fixture",
    }
    job = prepare_marketing_director_handoff(
        packet, generated_at=NOW
    )["campaign_previews"][0]
    assert job["jev_suggested_content_brief_above_threshold"] is False
    assert job["publication_ready"] is False
    assert job["content_draft"]["claim_verification_complete"] is False
    assert job["marketing_agency_ingested"] is False


def test_strong_model_cannot_authorize_publication_or_claimed_results():
    packet = review()
    packet["review_queue"][0]["jev_classification"] = {
        "label": "content_brief",
        "confidence": 0.98,
        "source_ref": "laya:shadow:fixture",
    }
    out = prepare_marketing_director_handoff(packet, generated_at=NOW)
    job = out["campaign_previews"][0]
    assert job["jev_suggested_content_brief_above_threshold"] is True
    assert out["external_publish_authorized"] is False
    assert job["publication_ready"] is False
    assert job["attribution_plan"]["visitor_sessions"] is None
    assert job["attribution_plan"]["enquiries"] is None
    assert job["attribution_plan"]["recognized_revenue"] is None
