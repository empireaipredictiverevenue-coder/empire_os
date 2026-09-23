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
    }


def test_collect_queries_preserves_pool_and_target_provenance():
    rows = collect_research_queries(plan(), max_queries=10)

    assert len(rows) == 3
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
    row = result["candidates"][0]
    assert row["domain"] == "buyer.example"
    assert row["explicit_direct_buyer_evidence"] is True
    assert row["first_party_emails"] == ["jane@buyer.example"]
    assert row["first_party_phones"] == ["+15125550123"]
    assert row["first_party_people"][0]["name"] == "Jane Smith"
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
