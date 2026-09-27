from empire_os.community_intent import IntentObservation
from empire_os.pain_solution_engine import build_pain_solution_briefs


def obs(url, source, score, band, pains):
    return IntentObservation(
        source=source,
        url=url,
        title="Observed buyer pain",
        text="Observed text",
        observed_at="2026-09-21T10:00:00+00:00",
        pain_points=tuple(pains),
        intent_score=score,
        intent_band=band,
    )


def test_repeated_search_pain_maps_to_existing_search_products():
    rows = [
        obs("https://reddit.com/a", "reddit", 70, "high", ("search_visibility",)),
        obs("https://linkedin.com/b", "linkedin", 65, "high", ("search_visibility",)),
        obs("https://reddit.com/c", "reddit", 60, "high", ("search_visibility",)),
    ]
    brief = build_pain_solution_briefs(rows)[0]
    assert brief.pain_point == "search_visibility"
    assert brief.offer_key == "search_growth_command"
    assert "authority_intelligence" in brief.products
    assert "geo_ai_visibility" in brief.products
    assert brief.evidence_strength == "strong"
    assert brief.opportunity_event == "opportunity_candidate_created"
    assert brief.execution_authority == "none"


def test_single_weak_mention_does_not_emit_opportunity_event():
    brief = build_pain_solution_briefs([
        obs("https://reddit.com/a", "reddit", 30, "low", ("lead_generation",))
    ])[0]
    assert brief.evidence_strength == "thin"
    assert brief.opportunity_event is None
