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
            "pages_checked": [],
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
    assert result["icp_assessed_candidate_count"] == 1
    assert result["verified_budget_candidate_count"] == 0
    row = result["candidates"][0]
    assert row["domain"] == "buyer.example"
    assert row["explicit_direct_buyer_evidence"] is True
    assert row["first_party_emails"] == ["jane@buyer.example"]
    assert row["first_party_phones"] == ["+15125550123"]
    assert row["first_party_people"][0]["name"] == "Jane Smith"
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
        kwargs["time_budget_seconds"] == 12.0
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
