"""Site audit is source-bound and never assumes conversion delivery."""
import pytest

from empire_os.search_intelligence.first_party_semantic_corpus import PRIORITY_PAGES
from empire_os.search_intelligence.semantic_site_quality import (
    inspect_owned_commercial_page, inspect_commercial_form_html,
)


def page_html(spec, *, include_commercial=True, include_pv=False,
              include_heat_pump=False, status="index,follow"):
    return (
        "<html><head><title>Relevant sector analysis | Empire AI</title>"
        f'<link rel="canonical" href="{spec.url}">'
        f'<meta name="robots" content="{status}">'
        "</head><body><h1>Evidence-first industry overview</h1>"
        "<h2>Evidence before opinion</h2>"
        "<p>Buyers need transparent evidence for a good business decision.</p>"
        + ('<p>Heat pumps support heating and cooling.</p>' if include_heat_pump else "")
        + ('<p>Photovoltaic panels convert sunlight.</p>' if include_pv else "")
        + ('<a href="/commercial">Request a founder-reviewed proposal</a>' if include_commercial else "")
        + '<a href="/insights/revenue-opportunity-assessment">ROI assessment</a>'
        "</body></html>"
    )


def test_hvac_heat_pump_gap_is_human_editorial_candidate():
    spec = PRIORITY_PAGES[2]
    r = inspect_owned_commercial_page(
        spec, html=page_html(spec), http_status=200
    )
    assert r["metadata_eligible"] is True
    assert r["observed_commercial_form_route_link"] is True
    assert r["observed_roi_assessment_route_link"] is True
    assert r["converted_leads_proven"] is False
    assert "EDITORIAL_REVIEW_HVAC_HEAT_PUMP_CONTEXT" in [
        x["action"] for x in r["editorial_review_candidates"]
    ]
    assert r["site_content_modified"] is False


def test_explicit_heat_pump_copy_removes_that_gap():
    spec = PRIORITY_PAGES[2]
    r = inspect_owned_commercial_page(
        spec, html=page_html(spec, include_heat_pump=True), http_status=200
    )
    assert r["observed_sector_phrases"]["heat_pump"] is True
    assert all(
        x["action"] != "EDITORIAL_REVIEW_HVAC_HEAT_PUMP_CONTEXT"
        for x in r["editorial_review_candidates"]
    )


def test_solar_pv_explanation_is_editorial_not_rank_proof():
    spec = PRIORITY_PAGES[1]
    r = inspect_owned_commercial_page(
        spec, html=page_html(spec), http_status=200
    )
    assert "EDITORIAL_REVIEW_SOLAR_PV_EXPLANATION" in [
        x["action"] for x in r["editorial_review_candidates"]
    ]
    stronger = inspect_owned_commercial_page(
        spec, html=page_html(spec, include_pv=True), http_status=200
    )
    assert stronger["editorial_review_candidates"] == []
    assert stronger["google_indexing_proven"] is False


def test_missing_form_route_anchor_is_not_conclusion_form_unavailable():
    spec = PRIORITY_PAGES[0]
    r = inspect_owned_commercial_page(
        spec, html=page_html(spec, include_commercial=False), http_status=200
    )
    assert r["observed_commercial_form_route_link"] is False
    assert any(x["action"] == "REVIEW_EXPLICIT_PROPOSAL_ROUTE"
               for x in r["editorial_review_candidates"])
    assert r["converted_leads_proven"] is False


def test_noindex_metadata_held_for_site_quality_review():
    spec = PRIORITY_PAGES[0]
    r = inspect_owned_commercial_page(
        spec, html=page_html(spec, status="noindex"), http_status=200
    )
    assert r["metadata_eligible"] is False
    assert r["editorial_review_candidates"][0]["severity"] == "high"


def test_commercial_page_static_form_presence_does_not_verify_crm():
    html = ('<html><form><input required type="email">'
            '<input type="text" required><button type="submit">Send</button>'
            '</form></html>')
    result = inspect_commercial_form_html(html, http_status=200)
    assert result["static_form_presence_observed"] is True
    assert result["email_input_count"] == 1
    assert result["required_input_count"] == 2
    assert result["submit_button_count"] == 1
    assert result["submission_executed"] is False
    assert result["submission_delivery_verified"] is False
    assert result["crm_record_verified"] is False


def test_form_html_fail_closed_without_submit():
    html = '<form><input type="email"></form>'
    r = inspect_commercial_form_html(html, http_status=200)
    assert r["static_form_presence_observed"] is False
    assert r["submission_delivery_verified"] is False


@pytest.mark.parametrize("bad", [None, 3, "x" * 2_000_001])
def test_bad_html_rejected(bad):
    spec = PRIORITY_PAGES[0]
    with pytest.raises(ValueError):
        inspect_owned_commercial_page(spec, html=bad, http_status=200)
    with pytest.raises(ValueError):
        inspect_commercial_form_html(bad, http_status=200)


def test_live_site_quality_orchestrator_reuses_only_allowed_owned_urls():
    from scripts.review_live_semantic_site_quality import build_live_site_quality_review
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith('/commercial'):
            return 200, '<form><input type="email" required><button type="submit">Submit</button></form>'
        spec = next(spec for spec in PRIORITY_PAGES if spec.url == url)
        return 200, page_html(spec)
    result = build_live_site_quality_review(public_get=fetch)
    assert result['assessed_public_pages'] == 4
    assert len(calls) == 5
    assert len(set(calls)) == 5
    assert result['page_to_static_commercial_form_path_observed'] is True
    assert result['commercial_form']['submission_delivery_verified'] is False
    assert result['crm_receipt_verified'] is False
    assert result['paid_api_requests'] == 0
    assert result['site_mutated'] is False


def test_live_site_quality_missing_form_is_not_proven_conversion():
    from scripts.review_live_semantic_site_quality import build_live_site_quality_review
    def fetch(url):
        if url.endswith('/commercial'):
            return 200, '<div>No real HTML form</div>'
        spec = next(spec for spec in PRIORITY_PAGES if spec.url == url)
        return 200, page_html(spec)
    result = build_live_site_quality_review(public_get=fetch)
    assert result['page_to_static_commercial_form_path_observed'] is False
    assert result['commercial_form']['static_form_presence_observed'] is False


def test_site_quality_missing_public_page_is_explicit_unavailable_not_empty_pass():
    from scripts.review_live_semantic_site_quality import build_live_site_quality_review
    def fetch(url):
        if url.endswith('/industries/hvac'):
            raise OSError('temporary unavailable')
        if url.endswith('/commercial'):
            return 200, '<form><input type="email"><button type="submit">Submit</button></form>'
        spec = next(spec for spec in PRIORITY_PAGES if spec.url == url)
        return 200, page_html(spec)
    result = build_live_site_quality_review(public_get=fetch)
    assert result['assessed_public_pages'] == 3
    assert result['page_to_static_commercial_form_path_observed'] is False
    assert result['read_errors'][0]['url'].endswith('/industries/hvac')
