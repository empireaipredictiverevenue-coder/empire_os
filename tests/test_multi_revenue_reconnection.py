from empire_os.buyer_acquisition_scout import collect_research_queries
from empire_os.buyer_acquisition_team import (
    commercial_research_profile, direct_buyer_profile,
)
from empire_os.buyer_scout import _flatten_queries
from empire_os.buyer_scout_review_readiness import review_readiness
from test_buyer_scout_review_readiness import candidate


def test_bounded_queries_do_not_starve_mrr_or_icp():
    plan = {
        "priority_targets": [{"priority_score": 99999, "research_queries": {
            "direct_demand_buyers": [f"lead query {i}" for i in range(40)],
            "local_and_smb_buyers": ["owner operator"],
        }}],
        "product_priority_targets": [{"product_code": "software_mrr",
            "research_queries": {"software_and_advisory_buyers": ["software teams"]}}],
        "icp_priority_targets": [{"icp_profile_key": "enterprise",
            "research_queries": {"enterprise_and_data_buyers": ["api consumers"]}}],
    }
    rows = collect_research_queries(plan, max_queries=4)
    assert {r["target_kind"] for r in rows} == {"corridor", "product", "icp"}
    assert any(r["buyer_pool"] == "local_and_smb_buyers" for r in rows)
    assert len(rows) == 4
    assert len(_flatten_queries(plan, max_queries=4)) == 4


def test_unknown_and_affiliate_are_not_qualified_lead_buyers():
    assert direct_buyer_profile({})["buyer_type"] == "unknown"
    affiliate = direct_buyer_profile({"business_name": "Lead Smart",
        "description": "Affiliate program for publisher call supply"})
    assert affiliate["buyer_type"] == "publisher_affiliate_partner"
    assert affiliate["explicit_direct_buyer_evidence"] is False
    assert affiliate["binding_commercial_evidence"] is False


def test_mrr_targets_survive_large_catalog_and_query_budget():
    from empire_os.buyer_acquisition_team import build_buyer_acquisition_plan
    products = [{"active": True, "product_code": f"pilot_{i}",
        "billing_model": "flat_pilot", "catalog_state": "VERIFIED",
        "version_state": "VERIFIED", "binding_terms_ready": True}
        for i in range(30)]
    plan = build_buyer_acquisition_plan({}, catalog_snapshot={"products": products})
    assert len(plan["product_priority_targets"]) > 30
    rows = collect_research_queries(plan, max_queries=10)
    assert any(row.get("billing_model") == "monthly_subscription" for row in rows)


def test_shared_search_does_not_discard_product_provenance():
    plan = {"product_priority_targets": [
        {"product_code": code, "research_queries": {
            "software_and_advisory_buyers": ["same query"]}}
        for code in ["mrr_a", "mrr_b"]]}
    rows = collect_research_queries(plan, max_queries=5)
    assert {r["product_code"] for r in rows} == {"mrr_a", "mrr_b"}


def test_multiple_intents_preserve_evidence_without_claiming_demand():
    profile = commercial_research_profile([
        {"buyer_pool": "software_and_advisory_buyers", "query": "software teams",
         "product_code": "mrr", "opportunity_key": "opportunity:1"},
        {"buyer_pool": "enterprise_and_data_buyers", "query": "api consumers"},
        {"buyer_pool": "direct_demand_buyers"},
    ])
    assert len(profile["commercial_intents"]) == 2
    assert profile["research_routes"][0]["opportunity_key"] == "opportunity:1"
    assert profile["demand_state"] == "UNKNOWN"
    assert profile["customer_state"] == "UNKNOWN"
    assert profile["commercial_terms_verified"] is False


def test_mixed_pool_product_review_requires_independent_provenance():
    row = candidate(target_buyer_pools=["direct_demand_buyers",
        "software_and_advisory_buyers"], target_product_codes=["mrr"])
    assert review_readiness(row) == (False, "direct_buyer_evidence_missing")

    row["query_evidence"].append({"buyer_pool": "software_and_advisory_buyers",
        "product_code": "mrr", "query": "software teams"})
    assert review_readiness(row) == (True, "review_ready")
    assert row["explicit_direct_buyer_evidence"] is False
    row["query_evidence"][-1]["product_code"] = "unrelated"
    assert review_readiness(row) == (False, "direct_buyer_evidence_missing")


def test_distribution_joins_explicit_products_and_research_without_acceptance():
    from empire_os.revenue_distribution import build_revenue_distribution, SOURCES
    from test_commercial_product_catalog import base_row
    now = "2026-09-29T12:00:00+00:00"
    data = {name: {"generated_at": now} for name in SOURCES}
    data["catalog"]["products"] = [base_row()]
    data["radar"]["candidates"] = [{"opportunity_key": "observed:1",
        "evidence_refs": ["observed:source"], "products": ["managed_service"]}]
    data["buyer_scout"]["candidates"] = [{"domain": "example.test",
        "target_product_codes": ["managed_service"]}]
    result = build_revenue_distribution(data, generated_at=now)
    row = result["opportunities"][0]
    assert row["product_matches"][0]["binding_terms_ready"] is True
    assert row["product_matches"][0]["price_accepted"] is None
    assert row["commercial_research_matches"][0]["demand_verified"] is False
    assert row["expected_canonical_revenue_contribution_cents"] is None
    data["catalog"]["generated_at"] = "2026-09-01T12:00:00+00:00"
    row = build_revenue_distribution(data, generated_at=now)["opportunities"][0]
    assert row["product_matches"][0]["binding_terms_ready"] is None
    assert row["product_matches"][0]["price_basis"] is None


def test_many_targets_cannot_starve_other_research_pools():
    pools = ['direct_demand_buyers', 'software_and_advisory_buyers',
             'enterprise_and_data_buyers', 'local_and_smb_buyers',
             'agency_and_reseller_buyers', 'publisher_affiliate_partners']
    targets = [{'product_code': str(i), 'priority_score': 100,
                'research_queries': {pools[0]: [f'direct target {i}']}}
               for i in range(30)]
    targets += [{'product_code': pool, 'research_queries': {pool: [pool]}}
                for pool in pools[1:]]
    rows = collect_research_queries({'product_priority_targets': targets}, max_queries=6)
    assert {row['buyer_pool'] for row in rows} == set(pools)


def test_default_budget_covers_existing_commercial_research_lanes():
    from empire_os.buyer_acquisition_team import build_buyer_acquisition_plan
    plan = build_buyer_acquisition_plan({})
    rows = collect_research_queries(plan, max_queries=20)
    all_targets = sum([plan.get(key, []) for key in (
        'priority_targets', 'product_priority_targets', 'icp_priority_targets')], [])
    available = {pool for target in all_targets for pool in target.get('research_queries', {})}
    assert {r['buyer_pool'] for r in rows} == available
    assert any('white label' in r['query'] for r in rows)
    assert any('publisher affiliate' in r['query'] for r in rows)
