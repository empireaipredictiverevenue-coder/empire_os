"""Multi-niche proprietary research boundary: dental remains live first lane."""
from hashlib import sha256

import pytest

from empire_os.research.brokerage_niche_profiles import (
    COUNTRIES, NICHES, research_intake_plan, SOURCE_READY_ONLY
)
from empire_os.research.brokerage_decision_brief import discover_held_candidates
from scripts.run_brokerage_deep_research_20261021 import run, render_markdown


def inspected(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Observed original dental source"],
    }


def test_deep_research_bot_is_niche_agnostic_but_sources_are_not():
    assert {"dental", "roofing", "solar", "hvac", "legal", "property"} <= set(NICHES)
    assert COUNTRIES == ("US", "GB")
    assert SOURCE_READY_ONLY == {("dental", "US"), ("dental", "GB")}
    for niche in NICHES:
        for market in COUNTRIES:
            intake = research_intake_plan(niche, market)
            assert intake["niche"] == niche
            assert intake["country"] == market
            assert len(intake["search_queries"]) == 2
            assert intake["buyer_problem_to_qualify"]
            assert intake["source_pages_verified"] == 0
            assert not intake["buyer_intent_verified"]
            assert not intake["editorial_signed_off"]
            assert not intake["outbound_authorized"]
            assert not intake["payment_authorized"]
            assert not intake["source_reuse_rights_verified"]


def test_dental_retains_verified_us_uk_workflow():
    both = run(country="both", niche="dental", inspect_fn=inspected)
    assert both["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
    assert both["niche"] == "dental"
    assert len(both["market_reports"]) == 2
    assert [x["original_pages_inspected"] for x in both["market_reports"]] == [3, 3]
    assert not both["editorial_signoff_verified"]


@pytest.mark.parametrize("niche", ["roofing", "solar", "hvac", "legal", "property"])
def test_other_niches_do_not_forge_dental_source_evidence(niche):
    def no_inspection(*args, **kwargs):
        raise AssertionError("A new niche must not fetch dental source pages")
    result = run(country="both", niche=niche, inspect_fn=no_inspection)
    assert result["status"] == "HELD_NICHE_ORIGINAL_SOURCE_INTAKE_REQUIRED"
    assert result["market_reports"] == []
    assert result["scope"] == ["US", "GB"]
    assert all(p["source_catalogue_state"] == "ORIGINAL_SOURCES_NOT_YET_ADMITTED"
               and p["source_pages_verified"] == 0
               for p in result["niche_intake_plans"])
    assert not result["genuine_buyer_or_revenue_proven"]
    assert not result["outbound_sent"]
    assert not result["database_writes"]
    rendered = render_markdown(result)
    assert "source intake required" in rendered
    assert "Original sources admitted: **none**" in rendered
    assert "dental implant" not in rendered.lower()


def test_fresh_discovery_is_only_candidates_for_other_niches():
    calls = []
    def search(query, **kwargs):
        calls.append(query)
        return {
            "searchParameters": {"engine": "bing_html", "cache": False,
                                 "search_state": "RESULTS", "quality_gate": "lexical_v2"},
            "organic": [{"title": "UK roofing contractor published original source",
                         "link": "https://public-roofing.example-business.co.uk/services"}],
        }
    report = run(country="GB", niche="roofing", probe_public_search=True, search_fn=search)
    assert len(calls) == 2 and all("roofing" in q.lower() for q in calls)
    assert "dental" not in " ".join(calls).lower()
    d = report["niche_intake_plans"][0]["public_search_diagnostic"]
    assert d["status"] == "FRESH_DISCOVERY_CANDIDATES_NOT_ADMITTED"
    assert d["source_admissions"] == 0
    assert len(d["candidate_urls"]) == 1
    assert report["market_reports"] == []
    assert report["status"] == "HELD_NICHE_ORIGINAL_SOURCE_INTAKE_REQUIRED"


def test_bad_niche_rejected():
    with pytest.raises(ValueError, match="NICHE"):
        run(country="both", niche="anything", inspect_fn=inspected)
    with pytest.raises(ValueError, match="NICHE"):
        research_intake_plan("unknown", "US")
    with pytest.raises(ValueError, match="COUNTRY"):
        research_intake_plan("dental", "FR")
    with pytest.raises(ValueError, match="NICHE"):
        discover_held_candidates("GB", None, niche="unknown")



def test_all_non_dental_markets_have_independent_specific_search_probes():
    seen = set()
    for niche in ("roofing", "solar", "hvac", "legal", "property"):
        for country in ("US", "GB"):
            plan = research_intake_plan(niche, country)
            queries = plan["search_queries"]
            assert len(queries) == 2
            assert all(isinstance(q, str) and len(q) >= 25 for q in queries)
            assert all("dental" not in q.casefold() for q in queries)
            assert ("Chicago" in " ".join(queries) or "Illinois" in " ".join(queries)) if country == "US" else ("Birmingham" in " ".join(queries) or "UK" in " ".join(queries))
            assert plan["source_catalogue_state"] == "ORIGINAL_SOURCES_NOT_YET_ADMITTED"
            assert plan["source_reuse_rights_verified"] is False
            assert plan["editorial_signed_off"] is False
            assert tuple(queries) not in seen
            seen.add(tuple(queries))
    assert len(seen) == 10
