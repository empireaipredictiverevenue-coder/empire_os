from datetime import datetime, timezone
import pytest
from empire_os.acquisition_yc_first_party_sweep import _roles, sweep_first_party

NOW = datetime(2026,10,23,8,30,tzinfo=timezone.utc)


def a():
    return [{"prospect_ref":"abc","company":"Sample",
             "source_url":"https://www.ycombinator.com/companies/sample",
             "niche":"Marketing & Growth","status":"RESEARCH_ONLY",
             "contact_authorized":False}]


def catalog():
    return {"generated_at":NOW.isoformat(), "products":[{
        "product_code":"search_growth_command","active":True,"binding_terms_ready":True,
        "catalog_state":"VERIFIED","version_state":"VERIFIED"}]}


def page():
    return b'<html><head><title>Jobs at Sample | Y Combinator</title></head><body>Jobs at\nSample\nFounding Marketing\nSan Francisco\nApply Now\nWhy you should join Sample</body></html>'


def test_extract_marketing_role():
    roles, checksum = _roles(page(),company="Sample")
    assert roles == ["Founding Marketing"]
    assert len(checksum) == 64


def test_hiring_not_procurement():
    r = sweep_first_party(assignments=a(),catalog=catalog(),now=NOW,fetch=lambda u:page())
    assert r["source_pages_observed"] == 1
    assert r["observed_commercial_hiring"] == 1
    assert r["product_hypotheses"] == 1
    assert r["independent_buying_triggers"] == 0
    assert not r["records"][0]["qualified_for_copy"]
    assert r["jev_observations_submitted"] == 1
    assert r["verified_revenue"] is None


def test_unavailable_source_is_not_zero_hiring_claim():
    def unavailable(_):
        raise TimeoutError("private")
    r = sweep_first_party(assignments=a(),catalog=catalog(),now=NOW,fetch=unavailable)
    assert r["records"][0]["research_status"] == "YC_LISTING_FETCH_UNAVAILABLE"
    assert r["records"][0]["yc_listing_sha256"] is None
    assert r["observed_commercial_hiring"] == 0


def test_no_verified_catalog_no_product():
    r = sweep_first_party(assignments=a(), catalog={"generated_at":"2025-01-01T00:00:00+00:00"},
                          now=NOW, fetch=lambda u:page())
    assert r["records"][0]["candidate_product_code"] is None


def test_unapproved_research_assignment_rejected():
    q=a()
    q[0]["status"]="QUALIFIED"
    with pytest.raises(ValueError):
        sweep_first_party(assignments=q,catalog=catalog(),now=NOW,fetch=lambda u:page())


def test_search_uses_existing_provider_only_when_healthy():
    calls = []
    def search(query, num):
        calls.append((query, num))
        return {"organic": [{"url":"https://example.com/unverified"}]}
    r = sweep_first_party(
        assignments=a(),catalog=catalog(),now=NOW,fetch=lambda _:page(),
        search_health={"last_state":"HEALTHY", "circuit_open":False},
        search_lookup=search)
    assert len(calls) == 1
    assert r["search_queries_attempted"] == 1
    assert r["unverified_search_results_observed"] == 1
    assert r["independent_buying_triggers"] == 0
    assert r["qualified_for_commercial_review"] == 0

def test_provider_cooldown_not_bypassed():
    def forbidden_search(*args, **kwargs):
        raise AssertionError("Search provider must not be called during cooldown")
    r = sweep_first_party(
        assignments=a(),catalog=catalog(),now=NOW,fetch=lambda _:page(),
        search_health={"last_state":"CIRCUIT_OPEN", "circuit_open":True},
        search_lookup=forbidden_search)
    assert r["search_queries_attempted"] == 0
    assert r["search_fabric_not_overridden"] is True
