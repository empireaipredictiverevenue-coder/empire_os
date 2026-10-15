"""Government discovery mock responses exist only as test fixtures."""
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from empire_os.data_exchange_discovery import discover_official_brownfield_sample
from scripts.discover_construction_brownfield import fetch_discovery_listing

NOW = datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)


def listing(url, ids=(1718671, 1718672), total=619):
    params = parse_qs(urlsplit(url).query)
    assert params["dataset"] == ["brownfield-land"]
    assert params["geometry_entity"] == ["626027"]
    assert params["geometry_relation"] == ["within"]
    assert params["field"] == ["entity", "dataset"]
    assert params["limit"] == ["5"]
    assert params["offset"] == ["0"]
    return {"count": total, "entities": [
        {"entity": entity_id, "dataset": "brownfield-land"} for entity_id in ids
    ]}


def entity_fetch(url, org=207):
    entity = int(url.rsplit("/", 1)[-1].replace(".json", ""))
    return {
        "entity": entity,
        "dataset": "brownfield-land",
        "quality": "authoritative",
        "organisation-entity": org,
        "planning-permission-status": "permissioned",
        "hectares": "0.45",
        "entry-date": "2024-11-29",
        "site-address": "Private text must never flow into pilot",
        "contact": "Private person must never flow into pilot",
    }


def review(fetch_listing=listing, fetch_entity=entity_fetch, **kwargs):
    return discover_official_brownfield_sample(
        authority="manchester", limit=5, offset=0,
        fetch_listing=fetch_listing,
        fetch_entity=fetch_entity,
        observed_at=NOW, **kwargs,
    )


def test_bounded_listing_only_collects_sample_not_project_claims():
    data = review()
    assert data["pilot_authority"] == "manchester"
    assert data["total_geographic_matches_reported"] == 619
    assert data["sample_count"] == 2
    assert data["sample_is_complete"] is False
    assert data["sample_coverage_status"] == "PARTIAL_SAMPLE"
    assert data["preview"]["dataset_record_count"] == 2
    assert data["preview"]["assessment_status"] == "HOLD"
    assert data["commercial_readiness"] == "HOLD_RIGHTS_AND_BUYER_VALIDATION"
    assert data["customer_delivery_enabled"] is False
    assert data["execution_authority"] == "NONE"
    assert "Private text" not in str(data)
    assert "Private person" not in str(data)
    assert all(r["source_entry_date"] == "2024-11-29" for r in data["preview"]["records"])


def test_wrong_organisation_fails_closed():
    with pytest.raises(ValueError, match="organisation"):
        review(fetch_entity=lambda url: entity_fetch(url, org=202))


@pytest.mark.parametrize("bad", [
    {"count": 619, "entities": [{"entity": 123, "dataset": "planning-application"}]},
    {"count": 1, "entities": [{"entity": 123, "dataset": "brownfield-land"},
                               {"entity": 124, "dataset": "brownfield-land"}]},
    {"count": 619, "entities": [{"entity": 123, "dataset": "brownfield-land"},
                                 {"entity": 123, "dataset": "brownfield-land"}]},
    {"count": 619, "entities": [{"entity": "123", "dataset": "brownfield-land"}]},
    {"count": "619", "entities": []},
    {"count": 619, "entities": []},
    [],
])
def test_rejects_malformed_listing(bad):
    with pytest.raises(ValueError):
        review(fetch_listing=lambda url: bad)


def test_rejects_unapproved_authority_and_bounds():
    for changes in [
        {"authority": "london", "limit": 5, "offset": 0},
        {"authority": "manchester", "limit": 6, "offset": 0},
        {"authority": "manchester", "limit": True, "offset": 0},
        {"authority": "manchester", "limit": 5, "offset": -1},
        {"authority": "manchester", "limit": 5, "offset": 1001},
    ]:
        with pytest.raises(ValueError):
            discover_official_brownfield_sample(
                fetch_listing=listing, fetch_entity=entity_fetch,
                observed_at=NOW, **changes,
            )


@pytest.mark.parametrize("url", [
    "https://attacker.example/entity.json?dataset=brownfield-land",
    "http://www.planning.data.gov.uk/entity.json",
    "https://www.planning.data.gov.uk.evil.com/entity.json",
    "https://www.planning.data.gov.uk/entity.json?dataset=contacts",
    "https://www.planning.data.gov.uk/entity.json?dataset=brownfield-land&limit=999999",
    "https://www.planning.data.gov.uk/entity/1.json",
    "https://www.planning.data.gov.uk/entity.json?dataset=brownfield-land&geometry_entity=626027",
])
def test_listing_transport_rejects_nonapproved_queries(url):
    with pytest.raises(ValueError):
        fetch_discovery_listing(url)


def test_ended_government_entity_cannot_be_dressed_up_as_current():
    def ended(url):
        row = entity_fetch(url)
        row["end-date"] = "2020-12-22"
        return row
    with pytest.raises(ValueError, match="validity"):
        review(fetch_entity=ended)
