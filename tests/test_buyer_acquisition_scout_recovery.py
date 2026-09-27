from empire_os.buyer_acquisition_scout import run_buyer_scout


def _evidence(url: str) -> dict:
    return {
        "ok": True,
        "canonical_url": url,
        "final_url": url,
        "business_names": ["Recovered Company"],
        "title": "Recovered Company",
        "description": "Home services company serving local customers.",
        "emails": [],
        "phones": [],
        "people": [{"name": "Owner", "title": "Owner"}],
        "pages_checked": [],
        "evidence_score": 0.9,
    }


def _empty_plan() -> dict:
    return {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [],
    }


def test_generic_canonical_fallback_processes_all_seeds_not_first_only(
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(url),
    )

    plan = {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 100,
            "icp_profile_key": "legal_mass_tort_plaintiff_firm",
            "research_queries": {
                "enterprise_and_data_buyers": ["mass tort buyer"],
            },
        }],
    }
    seeds = [
        {
            "id": f"seed-{i}",
            "business_name": f"Recovered Law {i}",
            "niche": "mass tort lawyer",
            "website": f"https://seed-{i}.example",
            "icp_profile_key": "legal_mass_tort_plaintiff_firm",
        }
        for i in range(10)
    ]

    result = run_buyer_scout(
        plan,
        canonical_seed_records=seeds,
        max_domains=10,
        max_probes=10,
    )

    assert result["search_domain_count"] == 0
    assert result["canonical_seed_domain_count"] == 10
    assert result["candidate_count"] == 10


def test_opportunity_seeds_supplement_nonempty_search(monkeypatch):
    plan = {
        "priority_targets": [{
            "priority_score": 15000,
            "corridor_key": "opportunity-validation:v1:roofing:denver_co",
            "opportunity_key": "market:roofing:denver, co",
            "research_queries": {
                "end_service_buyers": ["roofing denver"],
            },
        }],
        "product_priority_targets": [],
        "icp_priority_targets": [],
    }

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["weak-search.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(url),
    )

    result = run_buyer_scout(
        plan,
        canonical_seed_records=[{
            "id": "seed-1",
            "business_name": "Denver Roof Co",
            "niche": "roofing",
            "website": "https://recovery-roof.example",
            "seed_opportunity_key": "market:roofing:denver, co",
            "seed_buyer_pools": ["end_service_buyers"],
            "icp_profile_key": "high_ticket_home_service",
        }],
        max_domains=10,
        max_probes=10,
    )

    assert result["search_domain_count"] == 1
    assert result["opportunity_seed_domain_count"] == 1
    assert result["opportunity_seed_supplement_used"] is True
    assert result["domain_count"] == 2
    assert any(
        row["domain"] == "recovery-roof.example"
        and row["target_opportunity_keys"]
        == ["market:roofing:denver, co"]
        for row in result["candidates"]
    )


def test_search_disabled_never_calls_search_fabric(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("search fabric must stay disabled")
        ),
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(url),
    )

    result = run_buyer_scout(
        _empty_plan(),
        canonical_seed_records=[{
            "id": "seed-1",
            "business_name": "Denver Roof Co",
            "niche": "roofing",
            "website": "https://recovery-roof.example",
            "seed_opportunity_key": "market:roofing:denver, co",
            "seed_buyer_pools": ["end_service_buyers"],
            "icp_profile_key": "high_ticket_home_service",
        }],
        search_enabled=False,
        max_domains=5,
        max_probes=5,
    )

    assert result["search_enabled"] is False
    assert result["search_domain_count"] == 0
    assert result["opportunity_seed_domain_count"] == 1
    assert result["candidate_count"] == 1
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"
