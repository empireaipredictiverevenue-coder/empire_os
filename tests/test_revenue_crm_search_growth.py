from empire_os.revenue_crm_search_growth import build_crm_search_growth_brief
from empire_os.search_intelligence.ai_visibility import AiCitationObservation
from empire_os.search_intelligence.backlinks import BacklinkObservation


def test_crm_search_growth_connects_backlinks_mentions_and_citation_gap():
    brief = build_crm_search_growth_brief(
        prospect_id="p1",
        domain="example.com",
        query="best roofing company dallas",
        engine="chatgpt",
        backlinks=(
            BacklinkObservation(
                source_url="https://directory.example/listing",
                target_url="https://example.com/",
                observed_at="2026-09-21T09:00:00+00:00",
                provenance=("search:backlink:1",),
            ),
        ),
        citations=(
            AiCitationObservation(
                query="best roofing company dallas",
                engine="chatgpt",
                observed_at="2026-09-21T09:00:00+00:00",
                cited_url="https://competitor.com/roofing",
                provenance=("ai:query:1",),
                mention_text="Competitor Roofing",
            ),
        ),
        competitor_domains=("competitor.com",),
    )
    assert brief.prospect_id == "p1"
    assert brief.backlink_analysis.observed_backlinks == 1
    assert brief.ai_visibility.empire_cited is False
    assert brief.citation_gap is not None
    assert brief.citation_gap.citation_gap_observed is True
    assert "competitor_citation_gap" in brief.opportunities
    assert brief.crm_mutation is False
    assert brief.link_building_execution is False


def test_missing_evidence_stays_unknown_not_zero_score():
    brief = build_crm_search_growth_brief(
        prospect_id="p1",
        domain="example.com",
        query="roofing dallas",
        engine="chatgpt",
        backlinks=(),
        citations=(),
    )
    assert brief.backlink_analysis.available is False
    assert brief.ai_visibility.available is False
    assert "establish_backlink_baseline" in brief.opportunities
    assert "collect_ai_visibility_evidence" in brief.opportunities
