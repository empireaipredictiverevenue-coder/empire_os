from empire_os.search_intelligence.models import SearchOpportunity
from empire_os.search_intelligence.scoring import score_opportunity


def test_unknown_required_metric_keeps_score_unknown():
    opportunity = SearchOpportunity(
        query="predictive revenue platform",
        intent_score=0.9,
        commercial_intent=0.8,
        conversion_probability=0.4,
        relevance=0.9,
        authority_fit=0.7,
        freshness=0.8,
        competition=None,
    )
    result = score_opportunity(opportunity)
    assert result.opportunity_score is None
    assert "competition" in result.score_reason


def test_observed_formula_is_deterministic():
    opportunity = SearchOpportunity(
        query="predictive revenue platform",
        intent_score=0.9,
        commercial_intent=0.8,
        conversion_probability=0.5,
        relevance=0.9,
        authority_fit=0.8,
        freshness=0.75,
        competition=0.6,
    )
    result = score_opportunity(opportunity)
    assert result.opportunity_score == 0.324
    assert result.score_reason == "observed_deterministic_formula"
