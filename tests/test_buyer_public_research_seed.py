from datetime import datetime, timezone

from empire_os.buyer_public_research_seed import build_public_research_seeds


def test_public_research_seeds_are_observe_only_and_bounded():
    plan = {
        "priority_targets": [{
            "priority_score": 100,
            "buyer_hunt_required": True,
            "niche_family": "roofing",
            "corridor_key": "corridor:v1:roofing:austin_tx:qualified_lead:lead",
            "product_code": "permit_intelligence",
        }]
    }

    def fake_search(queries, num):
        assert 1 <= len(queries) <= 12
        assert num == 5
        return {query: ["buyer.example", "linkedin.com"] for query in queries}

    result = build_public_research_seeds(
        plan,
        search_fn=fake_search,
        max_queries=12,
        results_per_query=5,
        observed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        include_volume=False,
    )

    assert result["mode"] == "OBSERVE"
    assert result["outbound_sent"] is False
    assert result["commercial_authority"] == "none"
    assert result["execution_authority"] == "none"
    assert result["query_count"] == 5
    assert result["query_strategy_counts"]["publisher_first"] == 2
    assert result["publisher_first_queries_are_discovery_hints_only"] is True
    by_domain = {row["domain"]: row for row in result["seeds"]}
    assert "buyer.example" in by_domain
    assert "linkedin.com" not in by_domain
    row = by_domain["buyer.example"]
    assert row["identity_verified"] is False
    assert row["commercial_terms_verified"] is False
    assert row["buyer_capacity_verified"] is False
    assert row["buyer_price_verified"] is False
    assert row["outreach_authorized"] is False
    assert row["target_buyer_pools"] == ["direct_demand_buyers"]
    assert (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
        in row["target_corridor_keys"]
    )


def test_baseline_domains_are_only_research_hints():
    result = build_public_research_seeds(
        {},
        search_fn=lambda queries, num: {},
        observed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    assert result["seed_count"] >= 5
    for row in result["seeds"]:
        assert row["truth_class"] == "OBSERVED_PUBLIC_RESEARCH"
        assert row["identity_verified"] is False
        assert row["commercial_terms_verified"] is False
        assert row["buyer_capacity_verified"] is False
        assert row["buyer_price_verified"] is False
        assert row["outreach_authorized"] is False
        assert row["execution_authority"] == "none"


def test_search_failure_degrades_to_baseline_seeds():
    def broken_search(_queries, num):
        raise RuntimeError("provider unavailable")

    result = build_public_research_seeds(
        {"priority_targets": [{
            "priority_score": 1,
            "buyer_hunt_required": True,
            "niche_family": "roofing",
        }]},
        search_fn=broken_search,
        observed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    assert result["seed_count"] >= 5
    assert result["error_count"] == 1
    assert result["errors"][0].startswith("search_fabric:RuntimeError:")
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_rotating_volume_wave_is_bounded_and_observe_only():
    seen = {}

    def fake_search(queries, num):
        seen["queries"] = list(queries)
        seen["num"] = num
        return {
            query: [f"buyer{index}.example"]
            for index, query in enumerate(queries)
        }

    result = build_public_research_seeds(
        {},
        search_fn=fake_search,
        max_queries=24,
        results_per_query=7,
        observed_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert result["query_count"] == 24
    assert len(seen["queries"]) == 24
    assert seen["num"] == 7
    assert any("roofing" in q or "hvac" in q for q in seen["queries"])
    assert result["outbound_sent"] is False
    assert result["commercial_authority"] == "none"
    assert result["execution_authority"] == "none"
    volume_rows = [
        row for row in result["seeds"]
        if row["domain"].endswith(".example")
        and "local_and_smb_buyers" in row["target_buyer_pools"]
    ]
    assert len(volume_rows) == 22
    assert result["query_strategy_counts"]["publisher_first"] == 2
    assert result["query_strategy_counts"]["local_volume"] == 22
    assert all(
        "local_and_smb_buyers" in row["target_buyer_pools"]
        for row in volume_rows
    )
    assert all(
        "managed_service" in row["target_product_codes"]
        for row in volume_rows
    )


def test_publisher_first_search_rotates_without_extra_requests_or_outbound():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    observed=[]
    def capture(queries,num):
        observed.append(tuple(queries))
        return {}
    early=build_public_research_seeds(
        {},search_fn=capture,max_queries=2,include_volume=False,
        observed_at=datetime(2026,10,10,0,0,tzinfo=timezone.utc)
    )
    late=build_public_research_seeds(
        {},search_fn=capture,max_queries=2,include_volume=False,
        observed_at=datetime(2026,10,10,0,30,tzinfo=timezone.utc)
    )
    assert early["query_count"] == 2
    assert late["query_count"] == 2
    assert early["query_strategy_counts"]["publisher_first"] == 2
    assert late["query_strategy_counts"]["publisher_first"] == 2
    assert len(set(observed[0]) & set(observed[1])) == 0
    assert any('"publisher"' in q and '"SEO"' in q for batch in observed for q in batch)
    assert all(x["execution_authority"]=="none" and x["outreach_authorized"] is False
               for x in early["seeds"])
    assert early["commercial_authority"]=="none" and early["outbound_sent"] is False


def test_new_public_publisher_pages_remain_unapproved_cold_start_seeds():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    result=build_public_research_seeds(
        {},search_fn=lambda queries,num:{},max_queries=2,
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc)
    )
    domains={x["domain"]:x for x in result["seeds"]}
    for domain in ("elocal.com","polyares.com","homevantaleadgroup.com",
                   "joinglobalwiz.com"):
        assert domain in domains
        row=domains[domain]
        assert any(ref.startswith("public:publisher_review:") for ref in row["source_refs"])
        assert row["identity_verified"] is False
        assert row["commercial_terms_verified"] is False
        assert row["buyer_capacity_verified"] is False
        assert row["buyer_price_verified"] is False
        assert row["outreach_authorized"] is False
        assert row["execution_authority"]=="none"


def test_publisher_query_provider_failure_is_bounded_and_fails_closed():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    counter={"calls":0}
    def fail(queries,num):
        counter["calls"]+=1
        raise RuntimeError("website_search_failure")
    out=build_public_research_seeds(
        {},search_fn=fail,max_queries=4,
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc)
    )
    assert counter["calls"]==1
    assert out["error_count"]==1
    assert out["outbound_sent"] is False
    assert out["execution_authority"]=="none"
    assert out["seed_count"]>=11


def test_registry_comparison_reports_novelty_but_not_verified_buyers():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    data=build_public_research_seeds(
        {},search_fn=lambda queries,num:{q:["leadsmartinc.com","newpublisher.example"]
                                         for q in queries},
        max_queries=2,
        known_registry_domains={"leadsmartinc.com","callflowmarket.com","px.com"},
        observed_at=datetime(2026,10,10,0,0,tzinfo=timezone.utc),
    )
    c=data["source_method_comparison"]
    assert c["status"]=="REGISTRY_COMPARISON"
    assert c["known_registry_domain_count"]==3
    assert sorted(c["publisher_programme_page_novel_domains"])==[
        "elocal.com","homevantaleadgroup.com","joinglobalwiz.com","polyares.com",
    ]
    assert c["query_methods"]["publisher_first"]["not_in_registry"]==1
    assert c["query_methods"]["publisher_first"]["verified_buyer_approvals"]==0
    assert c["query_methods"]["publisher_first"]["recognized_revenue"] is None
    assert c["outbound_authorized"] is False


def test_unknown_baseline_cannot_invent_novel_discovered_buyers():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    report=build_public_research_seeds(
        {},search_fn=lambda q,num:{},max_queries=1,
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc),
    )
    c=report["source_method_comparison"]
    assert c["status"]=="REGISTRY_BASELINE_UNAVAILABLE"
    assert c["publisher_programme_page_novel_domains"] is None
    assert c["known_registry_domain_count"] is None
    assert c["execution_authority"]=="none"


def test_existing_scout_refresh_reads_actual_canonical_registry_without_writes(tmp_path):
    from empire_os.buyer_public_research_seed import (
        refresh_public_research_seeds,
    )
    import json
    runtime=tmp_path/"runtime/buyer_network_intelligence"
    runtime.mkdir(parents=True)
    registry={
        "relationships":[
            {"identity_domains":["leadsmartinc.com"]},
            {"identity_domains":["px.com","callflowmarket.com"]},
        ],
    }
    (runtime/"commercial_relationship_registry_latest.json").write_text(
        json.dumps(registry)
    )
    refreshed=refresh_public_research_seeds(
        tmp_path,search_fn=lambda q,num:{},
        max_queries=2,
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc),
    )
    comparison=refreshed["source_method_comparison"]
    assert comparison["status"]=="REGISTRY_COMPARISON"
    assert comparison["known_registry_domain_count"]==3
    assert comparison["publisher_programme_page_research_seed_count"]==4
    assert len(comparison["publisher_programme_page_novel_domains"])==4
    assert refreshed["outbound_sent"] is False
    assert refreshed["database_write_performed"] is False
    path=tmp_path/"runtime/buyer_acquisition/public_research_seeds.json"
    assert path.exists()
    assert json.loads(path.read_text())["source_method_comparison"]==comparison


def test_zero_fresh_domains_is_not_reported_as_successful_discovery():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    result=build_public_research_seeds(
        {},search_fn=lambda q,num:{},
        max_queries=2,include_volume=False,
        known_registry_domains={"leadsmartinc.com"},
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc)
    )
    assert result["query_strategy_counts"]["publisher_first"]==2
    assert result["fresh_search_domain_count"]==0
    assert result["fresh_search_result_status"]=="NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED"
    assert result["search_provider_health_independently_verified"] is False
    assert result["error_count"]==0  # search-fabric returned empty, did not raise
    assert result["source_method_comparison"]["query_methods"]["publisher_first"]["discovered_domains"]==0
    assert result["seed_count"]>0  # curated existing seeds, not fresh hits
    assert result["outbound_sent"] is False


def test_real_query_domain_is_separated_from_static_seed_pool():
    from empire_os.buyer_public_research_seed import build_public_research_seeds
    result=build_public_research_seeds(
        {},search_fn=lambda q,num:{q[0]:["newpartner.example"]},
        max_queries=2,include_volume=False,
        known_registry_domains=set(),
        observed_at=datetime(2026,10,10,tzinfo=timezone.utc)
    )
    assert result["fresh_search_domain_count"]==1
    assert result["fresh_search_result_status"]=="FRESH_DOMAIN_RESULTS_OBSERVED"
    assert result["source_method_comparison"]["query_methods"]["publisher_first"]["discovered_domains"]==1
    assert result["source_method_comparison"]["query_methods"]["publisher_first"]["verified_buyer_approvals"]==0


def test_new_us_publisher_seeds_are_non_authoritative_without_extra_searches():
    observed = {}
    def search(queries, num):
        observed["queries"] = list(queries)
        return {}
    report = build_public_research_seeds(
        {}, search_fn=search, max_queries=2,
        observed_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
        include_volume=False,
    )
    rows = {item["domain"]: item for item in report["seeds"]}
    for domain in ("ringpartner.com", "leadsbycall.com", "leadspedio.com", "ringondemand.com"):
        assert domain in rows
        row = rows[domain]
        assert "USA" in row["target_markets"]
        assert row["outreach_authorized"] is False
        assert row["buyer_capacity_verified"] is False
        assert row["commercial_terms_verified"] is False
        assert row["identity_verified"] is False
    assert len(observed["queries"]) == 2
    assert report["outbound_sent"] is False


def test_visiqua_multi_format_publisher_pages_researched_without_authority():
    from empire_os.buyer_public_research_seed import publisher_review_page_paths
    report = build_public_research_seeds(
        {}, search_fn=lambda queries, num: {}, max_queries=2,
        observed_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
        include_volume=False,
    )
    row = next(item for item in report['seeds'] if item['domain']=='visiqua.com')
    assert row['website'] == 'https://visiqua.com/calls/'
    assert row['target_markets'] == ['USA']
    assert row['outreach_authorized'] is False
    assert row['buyer_capacity_verified'] is False
    assert row['commercial_terms_verified'] is False
    assert row['identity_verified'] is False
    assert publisher_review_page_paths('visiqua.com') == ('/calls','/clicks','/leads')
    assert report['query_count'] == 2
