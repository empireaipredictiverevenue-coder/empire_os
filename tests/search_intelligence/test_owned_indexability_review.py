"""Owned-site technical SEO evidence: explicit indexability vs buyer release."""
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
import pytest
from empire_os.search_intelligence.owned_indexability_review import (
    analyse_owned_indexability, _owned_url,
)

BASE="https://empire-ai.co.uk"
GATES=(
 "/roofing","/roofing/replacement-vs-repair","/roofing/installation-checklist",
 "/research/agent-governance","/privacy","/terms",
)


def make_data():
    urls=[BASE+"/",BASE+"/industries/roofing",BASE+"/aeo/roofing/DFW/"]
    sitemap='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+u+'</loc></url>' for u in urls)+'</urlset>'
    robots="User-agent: *\nAllow: /\nSitemap: https://empire-ai.co.uk/sitemap.xml\n"
    pages=[
        {"url":u,"http":200,
         "html_robots":[],"xrobots":["index, follow"] if "/aeo/" in u else [],
         "canonical":[u.rstrip("/") or "/"],
         "h1_count":1,"title":"Original helpful page"}
        for u in urls
    ]
    pages[0]["canonical"]=[BASE]
    gated=[
        {"path":p,"http":200 if p=="/roofing" else 404,
         "html_robots":["noindex,nofollow"] if p=="/roofing" else [],
         "xrobots":[]}
        for p in GATES
    ]
    return {"sitemap":sitemap.encode(),"robots":robots.encode(),"pages":pages,
            "gated_pages":gated,"observed_at":"2026-10-14T14:45:30+00:00"}


def run(d=None):
    return analyse_owned_indexability(**(d or make_data()))


def test_healthy_public_sitemap_and_separate_buyer_protections():
    d=run()
    assert d["sitemap_url_count"]==3
    assert d["sitemap_indexability_signal_count"]==3
    assert d["needs_technical_review_count"]==0
    assert d["google_indexation_verified"] is False
    assert d["remove_buyer_noindex_allowed"] is False
    assert d["revenue_verified"] is False
    assert d["production_write"] is False
    assert d["expected_gated"]["/roofing"]["observed_http"]==200
    assert d["expected_gated"]["/roofing"]["publication_allowed"] is False
    assert d["expected_gated"]["/privacy"]["observed_http"]==404


def test_bare_homepage_canonical_equivalent_to_slash():
    assert _owned_url(BASE)=="/"
    assert _owned_url(BASE+"/")=="/"
    assert run()["technical_issues"]==[]


@pytest.mark.parametrize("bad",[
  "https://evil.example/", "http://empire-ai.co.uk/",
  "https://user:pw@empire-ai.co.uk/private",
  "https://empire-ai.co.uk:8443/private",
  "https://empire-ai.co.uk/roofing#content",
  "https://empire-ai.co.uk/roofing?phone=1",
])
def test_untrusted_sitemap_destinations_rejected(bad):
    d=make_data()
    d["pages"][0]["url"]=bad
    with pytest.raises(ValueError,match="invalid_owned_sitemap_url"):
        run(d)


def test_noindex_on_sitemap_page_is_real_conflict_not_approved_release():
    d=make_data()
    d["pages"][1]["html_robots"]=["noindex,nofollow"]
    result=run(d)
    assert result["technical_issues"][0]["signal_status"]=="NOINDEX_SITEMAP_CONFLICT"
    assert result["publication_authorized"] is False


def test_non_200_is_technical_review_not_empty_valid_sitemap():
    d=make_data()
    d["pages"][1]["http"]=404
    result=run(d)
    assert result["technical_issues"][0]["signal_status"]=="HTTP_NOT_200"
    assert result["sitemap_indexability_signal_count"]==2


def test_external_or_other_page_canonical_stays_issue():
    d=make_data()
    d["pages"][1]["canonical"]=["https://another.example/industry"]
    assert run(d)["technical_issues"][0]["signal_status"]=="CANONICAL_POINTS_ELSEWHERE"
    d=make_data()
    d["pages"][1]["canonical"]=[BASE+"/"]
    assert run(d)["technical_issues"][0]["signal_status"]=="CANONICAL_POINTS_ELSEWHERE"


def test_missing_title_or_main_heading_review():
    d=make_data()
    d["pages"][1]["h1_count"]=0
    assert run(d)["technical_issues"][0]["signal_status"]=="PAGE_TITLE_OR_HEADING_MISSING"


def test_unreleased_leadsmart_becoming_indexable_fails_closed():
    d=make_data()
    d["gated_pages"][0]["html_robots"]=[]
    with pytest.raises(ValueError,match="leadsmart_buyer_landing_accidentally_indexable"):
        run(d)


def test_unreleased_new_guide_must_not_be_live_without_approval():
    d=make_data()
    d["gated_pages"][1]["http"]=200
    with pytest.raises(ValueError,match="unreleased_or_legal_route_in_public_view"):
        run(d)


def test_unreleased_guide_in_sitemap_refused():
    d=make_data()
    url=BASE+"/roofing/replacement-vs-repair"
    d["sitemap"]=d["sitemap"].replace(b"</urlset>",(f"<url><loc>{url}</loc></url></urlset>").encode())
    d["pages"].append({"url":url,"http":404,"html_robots":[],"xrobots":[],"canonical":[],"h1_count":0,"title":""})
    with pytest.raises(ValueError,match="gated_content_must_not_appear_in_sitemap"):
        run(d)


def test_source_fetch_failure_never_proves_gate_safe():
    d=make_data()
    d["gated_pages"][0]["http"]=None
    with pytest.raises(ValueError,match="gated_route_fetch_unavailable"):
        run(d)


def test_missing_sitewide_robot_sitemap_declaration_fail():
    d=make_data()
    d["robots"]=b"User-agent: *\nDisallow: /\n"
    with pytest.raises(ValueError,match="sitemap_not_advertised_in_robots"):
        run(d)
    d["robots"]=b"User-agent: *\nDisallow: /\nSitemap: https://empire-ai.co.uk/sitemap.xml\n"
    with pytest.raises(ValueError,match="sitewide_disallow_in_robots"):
        run(d)


def test_duplicate_sitemap_and_no_count_attestation_denied():
    d=make_data()
    d["sitemap"]=d["sitemap"].replace(b"</urlset>",b"<url><loc>https://empire-ai.co.uk/</loc></url></urlset>")
    d["pages"].append(d["pages"][0])
    with pytest.raises(ValueError,match="duplicate_owned_sitemap_url"):
        run(d)
    d=make_data()
    d["pages"].pop()
    with pytest.raises(ValueError,match="sitemap_must_have_exact_observations"):
        run(d)
