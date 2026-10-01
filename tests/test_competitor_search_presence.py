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
        verify_canonical_companies=False,
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
        verify_canonical_companies=False,
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
        verify_canonical_companies=False,
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
        verify_canonical_companies=False,
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
        verify_canonical_companies=False,
    )

    assert result["company_with_search_presence_count"] == 1
    assert result["observation_count"] == 1
    company = next(
        row for row in result["companies"]
        if row["company_name"] == "Roofer A"
    )
    assert company["search_presence_observed"] is True
    assert company["best_position"] == 4



def test_canonical_company_verification_is_one_query_per_company():
    calls = []

    def targeted_search(query, num):
        calls.append(query)
        if "roofer-a.example" in query:
            return {
                "organic": [{
                    "title": "Roofer A",
                    "link": "https://roofer-a.example/",
                    "snippet": "Roofer A",
                    "position": 1,
                }],
                "searchParameters": {
                    "q": query,
                    "num": num,
                    "engine": "bing_html",
                    "quality_gate": "lexical_v1",
                },
            }
        if "roofer-b.example" in query:
            return {
                "organic": [{
                    "title": "Roofer B",
                    "link": "https://www.roofer-b.example/services",
                    "snippet": "Roofer B",
                    "position": 1,
                }],
                "searchParameters": {
                    "q": query,
                    "num": num,
                    "engine": "bing_html",
                    "quality_gate": "lexical_v1",
                },
            }
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
        queries=(),
        search_fn=targeted_search,
        max_workers=2,
        verify_canonical_companies=True,
    )

    assert len(calls) == 2
    assert all(call.startswith("site:") for call in calls)
    assert result["canonical_search_verified_company_count"] == 2
    assert result["company_with_search_presence_count"] == 2
    assert result["company_with_generic_market_presence_count"] == 0
    assert result["canonical_verification_observation_count"] == 2
    assert result["generic_query_observation_count"] == 0
    assert result["search_presence_available"] is True
    assert result["share_of_voice_available"] is False
    assert result["share_metric"] is None
    assert all(
        row["observed_search_presence_share"] is None
        for row in result["companies"]
    )


def test_targeted_verification_does_not_pollute_generic_share():
    def mixed_search(query, num):
        if query == "Denver roofing":
            return {
                "organic": [{
                    "title": "Roofer A",
                    "link": "https://roofer-a.example/service",
                    "snippet": "Denver roofing",
                    "position": 2,
                }],
                "searchParameters": {
                    "q": query,
                    "num": num,
                    "engine": "bing_html",
                    "quality_gate": "lexical_v1",
                },
            }
        domain = (
            "roofer-a.example"
            if "roofer-a.example" in query
            else "roofer-b.example"
        )
        name = "Roofer A" if domain.startswith("roofer-a") else "Roofer B"
        return {
            "organic": [{
                "title": name,
                "link": f"https://{domain}/",
                "snippet": name,
                "position": 1,
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
        search_fn=mixed_search,
        max_workers=2,
        verify_canonical_companies=True,
    )

    by_name = {row["company_name"]: row for row in result["companies"]}

    assert result["canonical_search_verified_company_count"] == 2
    assert result["company_with_generic_market_presence_count"] == 1
    assert result["share_of_voice_available"] is True
    assert by_name["Roofer A"]["observed_search_presence_share"] == 1.0
    assert by_name["Roofer B"]["observed_search_presence_share"] == 0.0


def test_cache_and_errors_cannot_be_restamped_as_observations():
    for change in ({"error": "unavailable"}, {"searchParameters": {"cache": True}}):
        def search(query, num):
            return {**_search(query, num), **change}
        result = build_search_presence_snapshot(
            companies=_companies(), queries=("Denver roofing",), search_fn=search,
        )
        assert result["observation_count"] == 0


def test_public_only_never_uses_auto_or_keyed_engines(monkeypatch):
    from empire_os import competitor_search_presence as module
    calls = []
    def search(query, num, engine):
        calls.append(engine)
        return {"organic": [], "error": "unavailable"}
    monkeypatch.setattr(module, "search_web", search)
    assert module._public_search_query("Denver roofing")["organic"] == []
    assert calls == ["bing_html", "duckduckgo_html", "bing_rss", "duckduckgo_lite", "mojeek"]


def test_failed_refresh_preserves_previous_snapshot(tmp_path, monkeypatch):
    import json
    import pytest
    from empire_os import competitor_search_presence as module
    root = tmp_path / "runtime/competitive_intelligence"
    root.mkdir(parents=True)
    (root / "competitor_market_scale_latest.json").write_text(json.dumps({"niche": "roofing", "metro": "Denver"}))
    output = tmp_path / module.SNAPSHOT_RELATIVE_PATH
    output.write_text('{"generated_at":"old"}')
    monkeypatch.setattr(module, "load_resolved_market_entities", lambda *a, **k: _companies())
    monkeypatch.setattr(module, "_public_search_query", lambda *a: {"organic": [], "error": "unavailable"})
    with pytest.raises(ValueError, match="fresh_search_observations_unavailable"):
        module.refresh_search_presence_snapshot(tmp_path, object(), public_only=True)
    assert output.read_text() == '{"generated_at":"old"}'
