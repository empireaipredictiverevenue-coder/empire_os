import pytest

from empire_os.search_intelligence.ai_visibility import (
    AiCitationObservation,
    analyse_ai_visibility,
)


def observation(**overrides):
    values = {
        "query": "predictive revenue software",
        "engine": "answer_engine",
        "observed_at": "2026-09-19T20:00:00+00:00",
        "cited_url": "https://empire-ai.co.uk/guides/revenue",
        "source_url": "https://answer.example/result/1",
        "citation_position": 2,
        "mention_text": "Empire AI",
        "provenance": ("provider_capture:1",),
    }
    values.update(overrides)
    return AiCitationObservation(**values)


def test_observed_empire_citation_is_counted():
    result = analyse_ai_visibility(
        (observation(),),
        empire_domains=("empire-ai.co.uk",),
        query="predictive revenue software",
        engine="answer_engine",
    )
    assert result.available is True
    assert result.observed_citations == 1
    assert result.empire_citations == 1
    assert result.empire_cited is True
    assert result.empire_positions == (2,)
    assert result.evidence_count == 1


def test_no_observations_remain_unknown_not_zero_visibility():
    result = analyse_ai_visibility(
        (),
        empire_domains=("empire-ai.co.uk",),
        query="predictive revenue software",
        engine="answer_engine",
    )
    assert result.available is False
    assert result.empire_cited is None
    assert result.reason == "no_observed_ai_citation_evidence"


def test_competitor_only_observation_is_observed_false():
    result = analyse_ai_visibility(
        (
            observation(
                cited_url="https://competitor.example/page",
                citation_position=1,
            ),
        ),
        empire_domains=("empire-ai.co.uk",),
        query="predictive revenue software",
        engine="answer_engine",
    )
    assert result.available is True
    assert result.empire_cited is False
    assert result.empire_citations == 0
    assert result.cited_domains == ("competitor.example",)


def test_unrelated_query_is_not_reused_as_visibility_evidence():
    result = analyse_ai_visibility(
        (observation(query="other query"),),
        empire_domains=("empire-ai.co.uk",),
        query="predictive revenue software",
        engine="answer_engine",
    )
    assert result.available is False


def test_observation_requires_provenance():
    with pytest.raises(ValueError, match="requires provenance"):
        observation(provenance=()).validate()


def test_observation_requires_absolute_cited_url():
    with pytest.raises(ValueError, match="absolute http"):
        observation(cited_url="/relative").validate()
