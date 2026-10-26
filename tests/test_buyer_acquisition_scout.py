from empire_os.buyer_acquisition_scout import (
    collect_research_queries,
    run_buyer_scout,
)


def plan():
    return {
        "priority_targets": [
            {
                "priority_score": 100,
                "corridor_key": "corridor:v1:roofing:austin_tx:qualified_lead:lead",
                "opportunity_key": "market:roofing:austin_tx",
                "research_queries": {
                    "local_and_smb_buyers": [
                        '"roofing" "local business" austin tx'
                    ],
                    "direct_demand_buyers": [
                        '"buy roofing leads" austin tx'
                    ],
                },
            }
        ],
        "product_priority_targets": [
            {
                "priority_score": 80,
                "product_code": "local_search_grid",
                "research_queries": {
                    "local_and_smb_buyers": [
                        '"local search" "small business"'
                    ],
                },
            }
        ],
        "icp_priority_targets": [
            {
                "priority_score": 95,
                "icp_profile_key": "high_ticket_home_service",
                "buying_triggers": [
                    "new service area",
                    "expansion",
                ],
                "decision_maker_roles": [
                    "owner",
                    "marketing director",
                ],
                "research_queries": {
                    "end_service_buyers": [
                        '"roofing" "new service area" austin tx'
                    ],
                },
            }
        ],
    }


def test_collect_queries_preserves_pool_and_target_provenance():
    rows = collect_research_queries(plan(), max_queries=10)

    assert len(rows) == 4
    assert any(
        row["buyer_pool"] == "direct_demand_buyers"
        and row["corridor_key"]
        for row in rows
    )
    assert any(
        row["opportunity_key"] == "market:roofing:austin_tx"
        for row in rows
        if row["target_kind"] == "corridor"
    )
    assert any(
        row["target_kind"] == "product"
        and row["product_code"] == "local_search_grid"
        for row in rows
    )
    assert any(
        row["target_kind"] == "icp"
        and row["icp_profile_key"] == "high_ticket_home_service"
        for row in rows
    )


def test_scout_discovers_evidence_without_creating_verified_buyer(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["buyer.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://buyer.example",
            "final_url": "https://buyer.example",
            "business_names": ["Buyer Exchange"],
            "title": "Buyer Exchange",
            "description": "We buy leads and run pay per lead campaigns.",
            "emails": ["jane@buyer.example"],
            "phones": ["+15125550123"],
            "people": [{"name": "Jane Smith", "title": "CEO"}],
            "pages_checked": [{
                "url": "https://buyer.example/advertisers/",
                "visible_text": "We buy leads from verified publishers.",
            }],
            "evidence_score": 0.95,
        },
    )

    result = run_buyer_scout(
        plan(),
        max_queries=10,
        max_domains=10,
        max_probes=10,
    )

    assert result["candidate_count"] == 1
    assert result["buyer_relationship_counts"] == {"direct_inventory_buyer": 1}
    assert result["observed_first_party_buyer_claim_receipt_count"] == 1
    assert result["buyer_role_conflict_count"] == 0
    assert result["icp_assessed_candidate_count"] == 1
    assert result["verified_budget_candidate_count"] == 0
    row = result["candidates"][0]
    assert row["domain"] == "buyer.example"
    assert row["explicit_direct_buyer_evidence"] is True
    assert row["buyer_relationship"] == "direct_inventory_buyer"
    assert row["commercial_sitemap_candidate_count"] == 0
    assert row["commercial_sitemap_page_fetch_count"] == 0
    claim = row["buyer_claim_provenance"]["claim_receipts"][0]
    assert claim["source_url"] == "https://buyer.example/advertisers/"
    assert claim["claim_excerpt"] == "We buy leads from verified publishers."
    assert len(claim["content_sha256"]) == 64
    assert claim["grants_outbound_authority"] is False
    assert row["first_party_buyer_evidence_pages"] == [{
        "url": "https://buyer.example/advertisers/",
        "buyer_side_signal_hits": ["buy leads", "we buy leads"],
    }]
    assert row["first_party_emails"] == ["jane@buyer.example"]
    assert row["first_party_phones"] == ["+15125550123"]
    assert row["first_party_people"][0]["name"] == "Jane Smith"
    assert row["target_opportunity_keys"] == [
        "market:roofing:austin_tx"
    ]
    assert row["target_icp_profile_keys"] == [
        "high_ticket_home_service"
    ]
    assert row["icp_intelligence"]["score_classification"] == (
        "MODEL_HEURISTIC"
    )
    assert row["icp_intelligence"]["budget_verified"] is False
    assert row["budget_verified"] is False
    assert row["candidate_state"] == "RESEARCH_EVIDENCE_ONLY"
    assert row["canonical_identity_verified"] is False
    assert row["commercial_terms_verified"] is False
    assert row["outreach_authorized"] is False
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_cross_domain_buyer_claim_never_qualifies_scout(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: ["buyer.example"] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://buyer.example/",
            "final_url": "https://buyer.example/",
            "business_names": ["Buyer Example"],
            "description": "Software company",
            "emails": [], "phones": [], "people": [],
            "pages_checked": [{
                "url": "https://unrelated.test/advertisers/",
                "visible_text": "We buy leads from publishers",
            }],
            "evidence_score": 0.2,
        },
    )
    output = run_buyer_scout(plan(), max_queries=1, max_domains=1, max_probes=1)
    assert len(output["candidates"]) == 1
    row = output["candidates"][0]
    assert row["explicit_direct_buyer_evidence"] is False
    assert row["first_party_buyer_evidence_pages"] == []
    assert row["outreach_authorized"] is False
    assert output["database_write_performed"] is False


def test_buyer_named_business_without_first_party_purchase_claim_is_not_verified(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: ["buyer.example"] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://buyer.example/",
            "final_url": "https://buyer.example/",
            "business_names": ["We Buy Leads Ltd"],
            "description": "Digital marketing and analytics solutions",
            "emails": [], "phones": [], "people": [],
            "pages_checked": [],
            "evidence_score": 0.2,
        },
    )
    result = run_buyer_scout(plan(), max_queries=1, max_domains=1, max_probes=1)
    assert len(result["candidates"]) == 1
    row = result["candidates"][0]
    assert row["explicit_direct_buyer_evidence"] is False
    assert row["first_party_buyer_evidence_pages"] == []
    assert row["outreach_authorized"] is False


def test_scout_uses_bounded_parallel_probe_workers(monkeypatch):
    seen = []

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: [
                "one.example",
                "two.example",
                "three.example",
            ]
            for query in queries
        },
    )

    def fake_probe(url, **kwargs):
        seen.append((url, kwargs))
        return {
            "ok": True,
            "canonical_url": url,
            "business_names": [url],
            "description": "Local business",
            "emails": [],
            "phones": [],
            "people": [],
            "pages_checked": [],
            "evidence_score": 0.7,
        }

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        fake_probe,
    )

    result = run_buyer_scout(
        plan(),
        max_queries=1,
        max_domains=3,
        max_probes=3,
    )

    assert result["probed_domain_count"] == 3
    assert len(seen) == 3
    assert all(
        kwargs["time_budget_seconds"] == 16.0
        and kwargs["max_pages"] == 5
        and kwargs["page_priority"] == "commercial"
        and kwargs["public_only"] is True
        for _, kwargs in seen
    )


def test_scout_classifies_predictive_revenue_enterprise_candidate(monkeypatch):
    enterprise_plan = {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 100,
            "icp_profile_key": (
                "predictive_revenue_home_services_platform"
            ),
            "buying_triggers": [
                "acquisition",
                "data analytics",
            ],
            "decision_maker_roles": [
                "chief revenue officer",
                "chief marketing officer",
            ],
            "research_queries": {
                "enterprise_and_data_buyers": [
                    '"home services platform" "acquisition"'
                ],
            },
        }],
    }

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["platform.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://platform.example",
            "final_url": "https://platform.example",
            "business_names": ["Platform Services Group"],
            "title": "Platform Services Group",
            "description": (
                "National home services platform expanding by acquisition "
                "with data analytics across portfolio brands."
            ),
            "emails": ["growth@platform.example"],
            "phones": ["+15125550123"],
            "people": [{
                "name": "Jane Smith",
                "title": "Chief Revenue Officer",
            }],
            "pages_checked": [],
            "evidence_score": 0.95,
        },
    )

    result = run_buyer_scout(
        enterprise_plan,
        max_queries=10,
        max_domains=10,
        max_probes=10,
    )

    assert result[
        "predictive_revenue_enterprise_candidate_count"
    ] == 1
    row = result["candidates"][0]
    assert row["predictive_revenue_enterprise_candidate"] is True
    assert row["predictive_revenue_enterprise_profile"] == (
        "predictive_revenue_home_services_platform"
    )
    assert row["predictive_revenue_enterprise_fit_score"] >= 40
    assert row["outreach_authorized"] is False


def test_scout_classifies_mass_tort_firm_lane(monkeypatch):
    legal_plan = {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 100,
            "icp_profile_key": "legal_mass_tort_plaintiff_firm",
            "buying_triggers": [
                "new litigation",
                "case intake",
            ],
            "decision_maker_roles": [
                "managing partner",
                "intake director",
            ],
            "research_queries": {
                "enterprise_and_data_buyers": [
                    '"mass tort law firm" "new litigation"'
                ],
            },
        }],
    }

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["masslaw.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://masslaw.example",
            "final_url": "https://masslaw.example",
            "business_names": ["Mass Law Group"],
            "title": "Mass Law Group",
            "description": (
                "Plaintiff mass tort law firm expanding case intake "
                "for multidistrict litigation."
            ),
            "emails": ["intake@masslaw.example"],
            "phones": ["+12125550100"],
            "people": [{
                "name": "Jane Smith",
                "title": "Managing Partner",
            }],
            "pages_checked": [],
            "evidence_score": 0.95,
        },
    )

    result = run_buyer_scout(
        legal_plan,
        max_queries=10,
        max_domains=10,
        max_probes=10,
    )

    row = result["candidates"][0]
    assert row["continuous_commercial_lane"] == "legal_mass_tort"
    assert row["continuous_lane_candidate"] is True
    assert result["continuous_lane_candidate_counts"][
        "legal_mass_tort"
    ] == 1
    assert row["outreach_authorized"] is False


def test_scout_classifies_insurance_lane(monkeypatch):
    insurance_plan = {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 98,
            "icp_profile_key": "insurance_distribution_growth",
            "buying_triggers": [
                "acquisition",
                "expansion",
            ],
            "decision_maker_roles": [
                "chief revenue officer",
                "chief marketing officer",
            ],
            "research_queries": {
                "enterprise_and_data_buyers": [
                    '"insurance agency network" "acquisition"'
                ],
            },
        }],
    }

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["insurance.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://insurance.example",
            "final_url": "https://insurance.example",
            "business_names": ["Insurance Network Group"],
            "title": "Insurance Network Group",
            "description": (
                "Insurance agency network expanding distribution "
                "through acquisitions and new markets."
            ),
            "emails": ["growth@insurance.example"],
            "phones": ["+13125550100"],
            "people": [{
                "name": "John Smith",
                "title": "Chief Revenue Officer",
            }],
            "pages_checked": [],
            "evidence_score": 0.95,
        },
    )

    result = run_buyer_scout(
        insurance_plan,
        max_queries=10,
        max_domains=10,
        max_probes=10,
    )

    row = result["candidates"][0]
    assert row["continuous_commercial_lane"] == "insurance"
    assert row["continuous_lane_candidate"] is True
    assert result["continuous_lane_candidate_counts"]["insurance"] == 1
    assert row["outreach_authorized"] is False


def test_public_research_seed_supplements_weak_search_without_bypassing_gates(
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {
            "ok": True,
            "canonical_url": "https://buyer.example",
            "final_url": "https://buyer.example",
            "business_names": ["Buyer Network"],
            "title": "Buyer Network",
            "description": (
                "We buy leads for roofing campaigns and connect approved "
                "publishers with advertisers using pay per call campaigns."
            ),
            "emails": ["partners@buyer.example"],
            "phones": [],
            "people": [],
            "pages_checked": [],
            "evidence_score": 0.95,
        },
    )

    result = run_buyer_scout(
        plan(),
        max_queries=10,
        max_domains=10,
        max_probes=10,
        research_seed_records=[{
            "domain": "buyer.example",
            "website": "https://buyer.example",
            "source_refs": ["public:first_party:buyer.example"],
            "source_queries": ['"roofing" "publisher" "pay per call"'],
            "target_buyer_pools": ["direct_demand_buyers"],
            "target_corridor_keys": [
                "corridor:v1:roofing:austin_tx:qualified_lead:lead"
            ],
            "target_product_codes": ["permit_intelligence"],
        }],
    )

    assert result["public_research_seed_domain_count"] == 1
    assert result["public_research_seed_supplement_used"] is True
    assert result["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["domain"] == "buyer.example"
    assert row["discovery_source"] == "public_research_seed"
    # A homepage description and search query are discovery hints; this
    # mocked probe returned no fetched first-party purchasing page.
    assert row["explicit_direct_buyer_evidence"] is False
    assert row["buyer_relationship"] == "unknown"
    assert row["buyer_claim_provenance"]["claim_receipts"] == []
    assert row["canonical_identity_verified"] is False
    assert row["commercial_terms_verified"] is False
    assert row["budget_verified"] is False
    assert row["outreach_authorized"] is False
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"

def test_public_research_seed_does_not_overwrite_query_accounting(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_args, **_kwargs: {"ok": False, "error": "offline"},
    )
    result = run_buyer_scout(
        plan(),
        max_queries=10,
        max_domains=10,
        max_probes=10,
        research_seed_records=[{
            "domain": "buyer.example",
            "website": "https://buyer.example",
            "target_buyer_pools": ["direct_demand_buyers"],
        }],
    )
    assert result["query_count"] == 4
    assert len(result["queries"]) == 4


def test_official_publisher_programmes_get_bounded_fair_probing_without_authority(
    monkeypatch,
):
    # 50 unrelated directory hits used to evict evidence-rich, pre-reviewed
    # publisher URLs from a 40-domain scout selection.
    search_hits=[f"contractor{i:03d}.com" for i in range(50)]
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries,num: {q:search_hits for q in queries},
    )
    probed=[]
    def observe(url, **kwargs):
        probed.append(url)
        return {"ok": True, "canonical_url": url, "final_url": url,
                "title": "Publisher Research", "description": "Publisher programme",
                "business_names": [], "emails": [], "phones": [],
                "people": [], "pages_checked": [], "evidence_score": 0.10}
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",observe
    )
    reviewed=["elocal.com","homevantaleadgroup.com",
              "joinglobalwiz.com","polyares.com"]
    seeds=[{
        "website":f"https://www.{domain}/affiliate-program",
        "domain":domain,
        "source_refs":["public:publisher_review:"+domain],
        "target_buyer_pools":["direct_demand_buyers"],
    } for domain in reviewed]
    data=run_buyer_scout(
        plan(), max_queries=10,max_domains=40,max_probes=20,
        research_seed_records=seeds,
    )
    assert data["domain_count"] == 40
    assert data["probed_domain_count"] == 20
    assert data["publisher_review_seed_count"] == 4
    assert data["publisher_review_included_count"] == 4
    assert data["publisher_review_probed_count"] == 4
    assert {x["domain"] for x in data["candidates"]} >= set(reviewed)
    assert {f"https://{d}" for d in reviewed} <= set(probed)
    for row in data["candidates"]:
        if row["domain"] in reviewed:
            assert row["discovery_source"] == "public_research_seed"
            assert row["commercial_terms_verified"] is False
            assert row["outreach_authorized"] is False
            assert row["canonical_identity_verified"] is False
    assert data["publisher_review_claims_are_not_buyer_approval"] is True
    assert data["outbound_sent"] is False
    assert data["execution_authority"] == "none"


def test_tiny_budget_never_displaces_higher_priority_opportunity(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries,num: {q:["contractorfirst.com"] for q in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda *_a,**_k:{"ok":False,"error":"offline_test"},
    )
    out=run_buyer_scout(
        plan(), max_queries=2,max_domains=1,max_probes=1,
        research_seed_records=[{
            "website":"https://polyares.com/pay-per-call-affiliate-program",
            "source_refs":["public:publisher_review:polyares.com"],
            "target_buyer_pools":["direct_demand_buyers"],
        }],
    )
    assert out["domain_count"]==1
    assert out["publisher_review_included_count"]==0
    assert out["publisher_review_probed_count"]==0
    assert out["outbound_sent"] is False


def test_founder_do_not_pursue_holds_search_canonical_and_research_seeds(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: ["callvox.pro"] for query in queries},
    )
    def never_probe(*args, **kwargs):
        raise AssertionError("founder-excluded domain must never be probed")
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site", never_probe
    )
    output = run_buyer_scout(
        plan(), max_queries=1, max_domains=2, max_probes=2,
        canonical_seed_records=[{
            "website": "https://callvox.pro",
            "icp_profile_key": "high_ticket_home_service",
        }],
        research_seed_records=[{
            "website": "https://callvox.pro/publishers",
            "target_buyer_pools": ["direct_demand_buyers"],
        }],
    )
    assert output["candidate_count"] == 0
    assert output["outbound_sent"] is False
    assert output["database_write_performed"] is False



def test_small_query_budget_reserves_existing_legal_and_insurance_icp_lanes():
    # Real scout defaults to 12 queries. Large generic product query streams
    # previously displaced all legal and mass-tort firm discovery.
    plan = {
        "priority_targets": [{
            "priority_score": 999,
            "corridor_key": "corridor:roofing:us",
            "research_queries": {
                "direct_demand_buyers": ["roofing buyer demand usa"],
                "end_service_buyers": ["roofing contractor usa"],
                "local_and_smb_buyers": ["roofing service business usa"],
            },
        }],
        "product_priority_targets": [{
            "priority_score": 300 - i,
            "product_code": "research_product_%d" % i,
            "research_queries": {
                "enterprise_and_data_buyers": ['"predictive revenue" "data team"' + str(i)],
                "agency_and_reseller_buyers": ["B2B growth agency no." + str(i)],
            },
        } for i in range(12)],
        "icp_priority_targets": [
            {
                "priority_score": 106,
                "icp_profile_key": "legal_mass_tort_plaintiff_firm",
                "research_queries": {
                    "direct_demand_buyers": ["mass tort law firm vendor analytics"]
                },
            },
            {
                "priority_score": 104,
                "icp_profile_key": "legal_plaintiff_growth_firm",
                "research_queries": {
                    "direct_demand_buyers": ["plaintiff law firm marketing analytics"]
                },
            },
            {
                "priority_score": 104,
                "icp_profile_key": "insurance_distribution_growth",
                "research_queries": {
                    "enterprise_and_data_buyers": [
                        "insurance distribution analytics agency"
                    ]
                },
            },
        ],
    }
    queries = collect_research_queries(plan, max_queries=12)
    assert len(queries) == 12
    targets = {
        q["icp_profile_key"] for q in queries
        if q["target_kind"] == "icp"
    }
    assert targets >= {
        "legal_mass_tort_plaintiff_firm",
        "legal_plaintiff_growth_firm",
        "insurance_distribution_growth",
    }
    assert any(q["target_kind"] == "corridor" for q in queries)
    assert any(q["target_kind"] == "product" for q in queries)
    assert any(q["buyer_pool"] == "agency_and_reseller_buyers" for q in queries)
    assert len({(
        q["query"], q["buyer_pool"],
        q.get("corridor_key"), q.get("product_code"),
        q.get("icp_profile_key")
    ) for q in queries}) == 12
    assert len(collect_research_queries(plan, max_queries=4)) == 4


def test_overflow_recovery_priority_uses_two_existing_scout_queries_without_expanding_budget():
    from empire_os.buyer_acquisition_scout import collect_research_queries

    targets = [
        {"corridor_key": "c:protected", "priority_score": 9999,
         "research_queries": {"direct_demand_buyers": ["protected legacy corridor"]}},
        {"corridor_key": "c:roofing:dallas", "priority_score": 90,
         "research_queries": {"direct_demand_buyers": ["first party roofing buyers dallas"]}},
        {"corridor_key": "c:roofing:denver", "priority_score": 80,
         "research_queries": {"direct_demand_buyers": ["first party roofing buyers denver"]}},
    ]
    for i in range(15):
        targets.append({"corridor_key": f"c:other:{i}", "priority_score": 200,
            "research_queries": {"direct_demand_buyers": [f"other buyer query {i}"]}})
    plan = {
        "priority_targets": targets,
        "product_priority_targets": [
            {"product_code": f"mrr:{i}", "priority_score": 800,
             "research_queries": {"software_and_advisory_buyers": [f"software MRR buyer {i}"]}}
            for i in range(12)
        ],
        "icp_priority_targets": [
            {"icp_profile_key": k, "priority_score": 300,
             "research_queries": {"enterprise_and_data_buyers": [f"buying evidence {k}"]}}
            for k in [
                "legal_mass_tort_plaintiff_firm",
                "legal_plaintiff_growth_firm",
                "insurance_distribution_growth",
            ]
        ],
        "demand_gap_queue": [
            {"corridor_key": "c:roofing:dallas", "buyer_hunt_required": True, "overflow_count": 4},
            {"corridor_key": "c:roofing:denver", "buyer_hunt_required": True, "overflow_count": 4},
        ],
    }
    rows = collect_research_queries(plan, max_queries=12)
    assert len(rows) == 12
    assert {r["corridor_key"] for r in rows if r.get("corridor_key") in {
        "c:roofing:dallas", "c:roofing:denver",
    }} == {"c:roofing:dallas", "c:roofing:denver"}
    assert {r["target_kind"] for r in rows} == {"corridor", "icp", "product"}
    assert {r.get("icp_profile_key") for r in rows} >= {
        "legal_mass_tort_plaintiff_firm",
        "legal_plaintiff_growth_firm",
        "insurance_distribution_growth",
    }
    assert len(collect_research_queries(plan, max_queries=4)) == 4
    plan["demand_gap_queue"] = []
    without_gap = collect_research_queries(plan, max_queries=12)
    assert not any(r.get("corridor_key") in {
        "c:roofing:dallas", "c:roofing:denver",
    } for r in without_gap)


def test_overflow_requires_real_hunt_and_positive_integer_volume():
    from empire_os.buyer_acquisition_scout import collect_research_queries
    p = plan()
    p["demand_gap_queue"] = [
        {"corridor_key": p["priority_targets"][0]["corridor_key"],
         "buyer_hunt_required": True, "overflow_count": True},
    ]
    # Boolean is not a verified numeric demand count.
    assert len(collect_research_queries(p, max_queries=12)) == 4
    p["demand_gap_queue"] = {"invalid": "not_list"}
    assert len(collect_research_queries(p, max_queries=12)) == 4
