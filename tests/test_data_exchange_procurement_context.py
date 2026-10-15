"""Official procurement fixture tests; none of these notices are real leads."""
from copy import deepcopy
from datetime import date, datetime, timezone
from urllib.parse import parse_qs, urlsplit
import pytest

from empire_os.data_exchange_procurement_context import inspect_procurement_releases
from empire_os.source_intelligence import source_contract
from scripts.inspect_official_procurement_context import fetch_official_procurement

NOW = datetime(2026, 10, 14, 18, tzinfo=timezone.utc)


def fixture():
    return {
        "license": "http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "publisher": {"name": "Cabinet Office"},
        "releases": [
            {"id": "096757-2026", "ocid": "ocds-h6vhtk-078700",
             "date": "2026-10-13T23:18:35+01:00", "tag": ["tender"],
             "tender": {"title": "DO NOT LEAK ME", "description": "PRIVATE"}},
            {"id": "096756-2026", "ocid": "ocds-h6vhtk-078701",
             "date": "2026-10-13T22:18:35+01:00", "tag": ["planning"],
             "parties": [{"contactPoint": {"email": "person@example.com"}}]},
        ],
    }


def review(response=None, **kwargs):
    response = fixture() if response is None else response
    def getter(url):
        args = parse_qs(urlsplit(url).query)
        assert args["updatedFrom"] == ["2026-10-13T00:00:00Z"]
        assert args["updatedTo"] == ["2026-10-14T00:00:00Z"]
        assert args["limit"] == ["2"]
        return response
    return inspect_procurement_releases(
        start_date=date(2026, 10, 13),
        end_date=date(2026, 10, 13), limit=2,
        fetch_json=getter, observed_at=NOW, **kwargs,
    )


def test_official_procurement_context_does_not_infer_site_relation():
    result = review()
    assert result["sample_count"] == 2
    assert [x["stages"] for x in result["notices"]] == [["tender"], ["planning"]]
    assert all(x["relation_to_brownfield_site"] == "NONE_VERIFIED"
               for x in result["notices"])
    assert result["cross_source_entity_link"] == "NOT_VERIFIED"
    assert result["buyer_intent_verified"] is False
    assert result["customer_delivery_enabled"] is False
    assert result["execution_authority"] == "NONE"
    assert "DO NOT LEAK" not in str(result)
    assert "person@example.com" not in str(result)


def test_procurement_source_is_research_not_active_and_not_resale():
    contract = source_contract("gb_find_a_tender_ocds")
    assert contract.production_status == "research"
    assert contract.raw_resale_allowed is False
    assert "analytics" in contract.allowed_uses


@pytest.mark.parametrize("change", [
    {"license": "unknown"},
    {"publisher": {"name": "anonymous"}},
    {"releases": []},
    {"releases": [{}]},
    {"releases": "error"},
    {"releases": [fixture()["releases"][0]] * 2},
])
def test_unsafe_package_holds(change):
    packet = fixture()
    packet.update(change)
    with pytest.raises(ValueError):
        review(packet)


@pytest.mark.parametrize("field,value", [
    ("id", "nonsense"),
    ("id", "999999-3026"),
    ("ocid", "https://bad"),
    ("date", "2028-01-01T10:00:00Z"),
    ("date", "2026-10-13T12:00:00"),
    ("tag", ["buyer_intent"]),
    ("tag", "tender"),
])
def test_invalid_release_payload_holds(field, value):
    packet = fixture()
    packet["releases"][0][field] = value
    with pytest.raises(ValueError):
        review(packet)


def test_window_and_limit_protection():
    for start, end, limit in [
        (date(2026, 10, 13), date(2026, 10, 14), 0),
        (date(2026, 10, 13), date(2026, 10, 14), 6),
        (date(2026, 10, 13), date(2026, 10, 18), 2),
        (date(2026, 10, 20), date(2026, 10, 21), 2),
    ]:
        with pytest.raises(ValueError):
            inspect_procurement_releases(
                start_date=start, end_date=end, limit=limit,
                observed_at=NOW, fetch_json=lambda _: fixture(),
            )


@pytest.mark.parametrize("bad", [
    "https://evil.example/api/1.0/ocdsReleasePackages?limit=2",
    "http://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=2",
    "https://www.find-tender.service.gov.uk/api/1.0/ocdsRecordPackages?limit=2",
    "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages?limit=999",
])
def test_transport_rejects_unapproved_queries(bad):
    with pytest.raises(ValueError):
        fetch_official_procurement(bad)
