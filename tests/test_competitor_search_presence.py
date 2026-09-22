from empire_os.competitor_search_presence import (
    build_search_presence_snapshot,
    search_presence_intelligence_signal,
)


def _companies():
    return [
        {
            "entity_id": "entity-a",
            "company_name": "Roofer A",
            "company_domain": "roofer-a.example",
        },
        {
            "entity_id": "entity-b",
            "company_name": "Roofer B",
            "company_domain": "roofer-b.example",
        },
    ]


def _search(query, num):
    return {
        "organic": [
            {
                "title": "Roofer A",
                "link": "https://roofer-a.example/service",
                "snippet": "Denver roofing",
                "position": 2,
            },
            {
                "title": "Other",
                "link": "https://other.example/page",
                "snippet": "Other",
                "position": 3,
            },
            {
                "title": "Roofer B",
                "link": "https://roofer-b.example/",
                "snippet": "Denver roofer",
                "position": 5,
            },
        ],
        "searchParameters": {
            "q": query,
            "num": num,
            "engine": "bing_html",
            "quality_gate": "lexical_v1",
        },
    }


def test_search_presence_observes_only_canonical_market_domains():
    result = build_search_presence_snapshot(
        companies=_companies(),
        queries=("Denver roofing",),
        search_fn=_search,
        max_workers=1,
    )

    assert result["canonical_company_count"] == 2
    assert result["company_with_search_presence_count"] == 2
    assert result["observation_count"] == 2
    assert result["search_presence_available"] is True
    assert result["market_share"] is None
    assert result["market_share_inferred"] is False
    assert result["demand_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False


def test_search_presence_share_is_observed_presence_not_market_share():
    result = build_search_presence_snapshot(
        companies=_companies(),
        queries=("Denver roofing",),
        search_fn=_search,
        max_workers=1,
    )

    by_name = {
        row["company_name"]: row
        for row in result["companies"]
    }

    assert by_name["Roofer A"]["best_position"] == 2
    assert by_name["Roofer B"]["best_position"] == 5
    assert (
        by_name["Roofer A"]["observed_search_presence_share"]
        >
        by_name["Roofer B"]["observed_search_presence_share"]
    )
    assert result["share_metric"] == (
        "reciprocal_position_weighted_observed_search_presence"
    )
    assert result["market_share_inferred"] is False


def test_search_presence_signal_is_observe_only():
    result = build_search_presence_snapshot(
        companies=_companies(),
        queries=("Denver roofing",),
        search_fn=_search,
        max_workers=1,
    )
    company = next(
        row for row in result["companies"]
        if row["company_name"] == "Roofer A"
    )

    signal = search_presence_intelligence_signal(
        company,
        source_id="00000000-0000-0000-0000-000000000031",
    )

    assert signal["signal_type"] == "competitor_search_presence"
    assert signal["signal_domain"] == "search_intelligence"
    assert signal["payload"]["research_candidate"] is True
    assert signal["payload"]["market_share_inferred"] is False
    assert signal["payload"]["demand_inferred"] is False
    assert signal["payload"]["buyer_intent"] is False
    assert signal["payload"]["commercial_intent"] is False
    assert signal["payload"]["prospect_created"] is False
    assert signal["payload"]["outreach_enabled"] is False
    assert signal["market_share_inferred"] is False
    assert signal["execution_authority"] == "none"


def test_no_results_stays_available_as_known_zero_presence():
    def empty_search(query, num):
        return {
            "organic": [],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "none",
            },
        }

    result = build_search_presence_snapshot(
        companies=_companies(),
        queries=("Denver roofing",),
        search_fn=empty_search,
        max_workers=1,
    )

    assert result["company_with_search_presence_count"] == 0
    assert result["observation_count"] == 0
    assert result["search_presence_available"] is False
    assert result["market_share"] is None



def test_search_presence_matches_owned_subdomains():
    def search_with_subdomain(query, num):
        return {
            "organic": [{
                "title": "Roofer A Blog",
                "link": "https://blog.roofer-a.example/denver-roofing",
                "snippet": "Denver roofing",
                "position": 4,
            }],
            "searchParameters": {
                "q": query,
                "num": num,
                "engine": "bing_html",
                "quality_gate": "lexical_v1",
            },
        }

    result = build_search_presence_snapshot(
        companies=_companies(),
        queries=("Denver roofing",),
        search_fn=search_with_subdomain,
        max_workers=1,
    )

    assert result["company_with_search_presence_count"] == 1
    assert result["observation_count"] == 1
    company = next(
        row for row in result["companies"]
        if row["company_name"] == "Roofer A"
    )
    assert company["search_presence_observed"] is True
    assert company["best_position"] == 4
