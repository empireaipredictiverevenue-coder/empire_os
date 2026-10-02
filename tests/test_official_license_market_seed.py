from datetime import datetime, timezone

from empire_os.official_license_market_seed import (
    build_official_license_market_seeds,
)


NOW = datetime(2026, 10, 2, 21, 0, tzinfo=timezone.utc)


def _cache():
    return {
        "records": [
            {
                "license_type": "A/C Contractor",
                "license_number": "1",
                "business_name": "Alpha Air LLC",
                "business_county": "BEXAR",
                "business_city_state_zip": "SAN ANTONIO TX 78201",
                "owner_name": "SMITH, JANE A",
                "license_expiration_date_mmddccyy": "12/31/2027",
            },
            {
                "license_type": "A/C Contractor",
                "license_number": "2",
                "business_name": "Bravo HVAC Inc",
                "business_county": "TRAVIS",
                "business_city_state_zip": "AUSTIN TX 78701",
                "owner_name": "DOE, JOHN",
                "license_expiration_date_mmddccyy": "11/30/2027",
            },
            {
                "license_type": "A/C Contractor",
                "license_number": "3",
                "business_name": "Expired Air LLC",
                "business_city_state_zip": "DALLAS TX 75201",
                "owner_name": "OLD, OWNER",
                "license_expiration_date_mmddccyy": "01/01/2025",
            },
            {
                "license_type": "A/C Contractor",
                "license_number": "4",
                "business_name": "Company Owner HVAC LLC",
                "business_city_state_zip": "HOUSTON TX 77001",
                "owner_name": "COMPANY OWNER HVAC LLC",
                "license_expiration_date_mmddccyy": "12/31/2027",
            },
        ]
    }


def test_license_market_seed_discovers_domains_without_authority():
    queries_seen = []

    def search_fn(queries, num):
        queries_seen.extend(queries)
        assert num == 4
        return {
            query: (
                ["alphaair.example", "yelp.com"]
                if "Alpha Air" in query
                else ["bravohvac.example", "facebook.com"]
            )
            for query in queries
        }

    result = build_official_license_market_seeds(
        _cache(),
        search_fn=search_fn,
        max_queries=10,
        results_per_query=4,
        observed_at=NOW,
    )

    assert result["eligible_company_count"] == 2
    assert result["query_count"] == 2
    assert result["seed_count"] == 2
    assert len(queries_seen) == 2
    assert {row["domain"] for row in result["seeds"]} == {
        "alphaair.example",
        "bravohvac.example",
    }
    for row in result["seeds"]:
        assert row["truth_class"] == "OBSERVED_OFFICIAL_LICENSE_RESEARCH"
        assert row["identity_verified"] is False
        assert row["outreach_authorized"] is False
        assert row["execution_authority"] == "none"
        assert row["registry_identity_seed"]["buyer_authority_proven"] is False
        assert row["target_product_codes"] == ["managed_service"]


def test_license_market_seed_search_failure_is_observable_not_promoted():
    def broken(*_args, **_kwargs):
        raise TimeoutError("search unavailable")

    result = build_official_license_market_seeds(
        _cache(),
        search_fn=broken,
        max_queries=10,
        observed_at=NOW,
    )

    assert result["seed_count"] == 0
    assert result["error_count"] == 1
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["commercial_authority"] == "none"
