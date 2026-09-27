from empire_os.search_intelligence.backlinks import (
    BacklinkObservation,
    analyse_backlink_graph,
)


def backlink(**overrides):
    values = {
        "source_url": "https://partner.example/article",
        "target_url": "https://empire-ai.co.uk/guides/revenue",
        "observed_at": "2026-09-20T13:00:00+00:00",
        "anchor_text": "predictive revenue",
        "rel": "",
        "source": "crawler_observation",
        "provenance": ("crawler:1",),
    }
    values.update(overrides)
    return BacklinkObservation(**values)


def test_observed_backlinks_build_domain_graph_without_score():
    result = analyse_backlink_graph(
        (
            backlink(),
            backlink(
                source_url="https://second.example/page",
                rel="nofollow",
            ),
        ),
        empire_domains=("empire-ai.co.uk",),
    )
    assert result.available is True
    assert result.observed_backlinks == 2
    assert result.referring_domains == 2
    assert result.dofollow_backlinks == 1
    assert result.nofollow_backlinks == 1
    assert result.authority_score is None
    assert result.evidence_count == 2


def test_no_observations_stay_unavailable():
    result = analyse_backlink_graph(
        (),
        empire_domains=("empire-ai.co.uk",),
    )
    assert result.available is False
    assert result.observed_backlinks == 0
    assert result.authority_score is None
    assert result.reason == "no_observed_backlink_evidence"


def test_non_empire_targets_are_not_counted():
    result = analyse_backlink_graph(
        (
            backlink(
                target_url="https://competitor.example/page"
            ),
        ),
        empire_domains=("empire-ai.co.uk",),
    )
    assert result.available is False
    assert result.observed_backlinks == 0


def test_duplicate_source_domain_counts_links_but_one_domain():
    result = analyse_backlink_graph(
        (
            backlink(source_url="https://partner.example/a"),
            backlink(source_url="https://partner.example/b"),
        ),
        empire_domains=("empire-ai.co.uk",),
    )
    assert result.observed_backlinks == 2
    assert result.referring_domains == 1
