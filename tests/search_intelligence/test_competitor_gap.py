from empire_os.search_intelligence.competitor_gap import (
    analyse_competitor_gap,
)
from empire_os.search_intelligence.serp import (
    SerpResultEvidence,
    SerpSnapshot,
)


def result(url, position):
    return SerpResultEvidence(
        title=url,
        url=url,
        snippet="",
        position=position,
        engine="duckduckgo_html",
        relevance_score=None,
        provenance=("search_fabric",),
    )


def snapshot(*results, available=True, error=None):
    return SerpSnapshot(
        query="predictive revenue software",
        observed_at="2026-09-19T15:00:00+00:00",
        engine="duckduckgo_html",
        quality_gate="lexical_v1",
        cache=False,
        available=available,
        results=tuple(results),
        error=error,
    )


def test_gap_uses_only_observed_serp_positions_and_domains():
    analysis = analyse_competitor_gap(
        snapshot(
            result("https://competitor-a.example/a", 1),
            result("https://competitor-b.example/", 2),
            result("https://www.empire-ai.co.uk/", 3),
            result("https://competitor-a.example/b", 4),
        ),
        empire_domains=("empire-ai.co.uk",),
    )

    assert analysis.available is True
    assert analysis.observed_result_count == 4
    assert analysis.empire_result_count == 1
    assert analysis.competitor_result_count == 3
    assert analysis.empire_best_position == 3
    assert analysis.current_empire_coverage == 0.25
    assert analysis.competitor_presence == 0.75
    assert analysis.content_gap == 0.75
    assert [item.domain for item in analysis.competitor_domains] == [
        "competitor-a.example",
        "competitor-b.example",
    ]
    assert analysis.competitor_domains[0].observed_positions == (1, 4)
    assert analysis.opportunity_inputs() == {
        "competitor_presence": 0.75,
        "current_empire_coverage": 0.25,
        "content_gap": 0.75,
    }


def test_no_empire_result_is_observed_full_coverage_gap_not_fake_rank():
    analysis = analyse_competitor_gap(
        snapshot(
            result("https://a.example/", 1),
            result("https://b.example/", 2),
        ),
        empire_domains=("empire-ai.co.uk",),
    )
    assert analysis.empire_result_count == 0
    assert analysis.empire_best_position is None
    assert analysis.current_empire_coverage == 0.0
    assert analysis.competitor_presence == 1.0
    assert analysis.content_gap == 1.0


def test_unavailable_serp_keeps_metrics_unknown():
    analysis = analyse_competitor_gap(
        snapshot(
            available=False,
            error="All engines failed",
        ),
        empire_domains=("empire-ai.co.uk",),
    )
    assert analysis.available is False
    assert analysis.current_empire_coverage is None
    assert analysis.competitor_presence is None
    assert analysis.content_gap is None
    assert analysis.empire_best_position is None
    assert analysis.reason == "All engines failed"


def test_empire_domain_is_required():
    try:
        analyse_competitor_gap(
            snapshot(result("https://a.example", 1)),
            empire_domains=(),
        )
    except ValueError as exc:
        assert "Empire domain" in str(exc)
    else:
        raise AssertionError("missing Empire domains must fail closed")
