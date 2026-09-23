from datetime import datetime, timezone

from empire_os.buyer_scout import run_buyer_scout


def test_buyer_scout_materializes_internal_observations_only():
    plan = {
        "priority_targets": [
            {
                "corridor_key": (
                    "corridor:v1:roofing:austin_tx:"
                    "qualified_lead:lead"
                ),
                "priority_score": 100,
                "research_queries": {
                    "direct_demand_buyers": [
                        '"buy roofing leads" austin tx',
                    ],
                    "local_and_smb_buyers": [
                        '"roofing" "local business" austin tx',
                    ],
                },
            }
        ],
        "product_priority_targets": [],
    }

    def search(query, num=5):
        return {
            "organic": [
                {
                    "title": "Texas Lead Exchange",
                    "link": "https://texasleadexchange.example/buy-leads",
                    "snippet": "We buy leads and pay per lead.",
                }
            ],
            "searchParameters": {"engine": "test"},
        }

    result = run_buyer_scout(
        plan,
        search_fn=search,
        max_queries=2,
        observed_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert result["query_count"] == 2
    assert result["observation_count"] == 1
    obs = result["observations"][0]
    assert obs["buyer_profile"]["buyer_type"] == "direct_lead_buyer"
    assert obs["candidate_state"] == "RESEARCH_OBSERVATION"
    assert obs["identity_verified"] is False
    assert obs["outbound_ready"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_buyer_scout_deduplicates_same_domain_across_queries():
    plan = {
        "priority_targets": [
            {
                "corridor_key": "corridor:v1:x:y:qualified_lead:lead",
                "priority_score": 50,
                "research_queries": {
                    "local_and_smb_buyers": ["q1", "q2"],
                },
            }
        ],
        "product_priority_targets": [],
    }

    def search(query, num=5):
        return {
            "organic": [
                {
                    "title": "Acme",
                    "link": "https://acme.example/" + query,
                    "snippet": "Local business",
                }
            ],
            "searchParameters": {"engine": "test"},
        }

    result = run_buyer_scout(
        plan,
        search_fn=search,
        max_queries=2,
        observed_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert result["query_count"] == 2
    assert result["observation_count"] == 1


def test_buyer_scout_can_research_non_lead_product_demand():
    plan = {
        "priority_targets": [],
        "product_priority_targets": [
            {
                "product_code": "local_search_grid",
                "priority_score": 35,
                "research_queries": {
                    "local_and_smb_buyers": [
                        '"search intelligence" "small business"',
                    ],
                },
            }
        ],
    }

    def search(query, num=5):
        return {
            "organic": [
                {
                    "title": "Local Dental Group",
                    "link": "https://dental.example",
                    "snippet": "Multi-location local dental business.",
                }
            ],
            "searchParameters": {"engine": "test"},
        }

    result = run_buyer_scout(
        plan,
        search_fn=search,
        max_queries=1,
        observed_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert result["observations"][0]["product_code"] == (
        "local_search_grid"
    )
    assert result["observations"][0]["target_pool"] == (
        "local_and_smb_buyers"
    )
