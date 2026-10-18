"""News-to-owned-site research preview: offline tests, no mutations."""
import pytest

from empire_os.jev_newsjack_traffic_briefs import (
    APPROVED_PAGE_ROUTES, COMMERCIAL_CONTACT,
    prepare_editorial_traffic_reviews,
)

NOW = "2026-10-18T15:00:00+00:00"


def story(*, sector="solar", market="GB", published="2026-10-14T10:00:00+00:00"):
    return {
        "signal_id": "story:gov:fixture",
        "title": "Government announces an energy system update for households",
        "sector": sector,
        "market": market,
        "primary_source_url": "https://www.gov.uk/government/speeches/building-an-energy-system-that-delivers-for-all",
        "published_at": published,
        "observed_at": NOW,
        "evidence_refs": ["govuk:content_api:fixture:1"],
    }


def inspector(path):
    assert path in {*APPROVED_PAGE_ROUTES.values(), COMMERCIAL_CONTACT}
    if path.endswith("/industries/solar"):
        title = "Solar Installer Coverage & Lead Qualification | Empire AI"
        heads = ["Solar growth starts with the right territory."]
    elif path.endswith("/industries/roofing"):
        title = "Commercial Roofing Buyer Fit & Lead Qualification | Empire AI"
        heads = ["Commercial roofing demand intelligence, grounded in buyer fit."]
    else:
        title = "AI Consultancy & Revenue Intelligence | Empire AI"
        heads = ["Turn the opportunity into a real proposal."]
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "http_status": 200, "source_url": path,
        "page_title": title, "document_headings": heads,
        "content_sha256": "a" * 64,
    }


def test_verified_solar_landing_creates_research_preview_not_published_article():
    got = prepare_editorial_traffic_reviews([story()], as_of=NOW, inspector=inspector)
    assert got["verified_existing_page_count"] == 2
    assert got["editorial_research_preview_count"] == 1
    item = got["review_queue"][0]
    assert item["status"] == "EDITORIAL_RESEARCH_PREVIEW"
    assert item["page_url"] == APPROVED_PAGE_ROUTES[("solar", "GB")]
    assert item["cta_existing_commercial_page"] == COMMERCIAL_CONTACT
    assert "independent_corroboration_required" in item["research_gaps"]
    assert "trusted_gsc_demand_observation_missing" in item["research_gaps"]
    assert item["published_article_count"] == 0
    assert item["attributable_visitors"] is None
    assert got["live_publication"] is False


def test_roofing_uses_real_roofing_page_not_solar_page():
    got = prepare_editorial_traffic_reviews(
        [story(sector="roofing", market="US")], as_of=NOW, inspector=inspector
    )
    assert got["review_queue"][0]["page_url"] == APPROVED_PAGE_ROUTES[("roofing", "US")]


def test_unapproved_market_does_not_probe_caller_supplied_url():
    calls = []
    def observing(path):
        calls.append(path)
        return inspector(path)
    case = story(sector="solar", market="US")
    case["destination_url"] = "https://example.net/private"
    case["destination_live_verified"] = True
    case["destination_evidence_refs"] = ["fabricated:proof"]
    result = prepare_editorial_traffic_reviews([case], as_of=NOW, inspector=observing)
    assert calls == []
    assert result["review_queue"][0]["status"] == "HOLD_FOR_RESEARCH"
    assert result["review_queue"][0]["page_url"] is None


def test_failed_inspector_can_never_promote_page_proof():
    def failed(path):
        if path.endswith("/industries/solar"):
            return {"status": "HTTP_NOT_SUCCESS", "http_status": 404}
        return inspector(path)
    result = prepare_editorial_traffic_reviews([story()], as_of=NOW, inspector=failed)
    item = result["review_queue"][0]
    assert item["status"] == "HOLD_FOR_RESEARCH"
    assert item["cta_existing_commercial_page"] is None or item["page_url"] is None


def test_stale_article_stays_held_even_if_owned_page_is_live():
    result = prepare_editorial_traffic_reviews(
        [story(published="2026-09-01T10:00:00+00:00")],
        as_of=NOW, inspector=inspector,
    )
    assert result["editorial_research_preview_count"] == 0
    assert result["review_queue"][0]["status"] == "HOLD_FOR_RESEARCH"


def test_wrong_page_heading_blocks_even_with_valid_http_200():
    def wrong(path):
        row = inspector(path)
        if path.endswith("/industries/solar"):
            row["page_title"] = "Unrelated account login page"
            row["document_headings"] = ["Account login"]
        return row
    result = prepare_editorial_traffic_reviews([story()], as_of=NOW, inspector=wrong)
    assert result["review_queue"][0]["status"] == "HOLD_FOR_RESEARCH"


def test_inspection_fixed_and_bounded():
    with pytest.raises(ValueError):
        prepare_editorial_traffic_reviews([story()] * 51, as_of=NOW,
                                         inspector=inspector)
    with pytest.raises(ValueError):
        prepare_editorial_traffic_reviews([{"signal_id": "valid"}, []],
                                         as_of=NOW, inspector=inspector)
