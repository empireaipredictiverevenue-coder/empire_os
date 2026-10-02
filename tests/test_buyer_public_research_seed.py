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
    )

    assert result["mode"] == "OBSERVE"
    assert result["outbound_sent"] is False
    assert result["commercial_authority"] == "none"
    assert result["execution_authority"] == "none"
    assert result["query_count"] == 3
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
