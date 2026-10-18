"""Page-only Search Console protects source integrity and URL aliases."""
import pytest
from empire_os.search_intelligence.first_party_gsc_page_review import (
    review_gsc_priority_pages, PRIORITY_PAGE_ROUTES, PROPERTY, GscPageEvidenceError,
)


START, END = "2026-10-08", "2026-10-17"


def packet(items):
    return {
        "available": True, "source": "google_search_console",
        "site_url": PROPERTY, "dimensions": ["page"],
        "data_state": "final", "window": [START, END],
        "count": len(items), "limit": 1000, "items": items,
    }


def row(url, *, clicks=2, impressions=25, ctr=.08, position=6.3):
    return {
        "keys": [url], "clicks": clicks, "impressions": impressions,
        "ctr": ctr, "position": position,
    }


def test_owned_priority_pages_get_actual_gsc_performance_not_buyer_claims():
    p = packet([
        row("https://empire-ai.co.uk/industries/solar"),
        row("https://empire-ai.co.uk/unrelated-legacy", clicks=0, impressions=1, ctr=0),
    ])
    d = review_gsc_priority_pages(p, start_date=START, end_date=END)
    assert d["returned_page_rows"] == 2
    solar = next(x for x in d["priority_page_findings"] if x["product_key"] == "solar")
    assert solar["status"] == "GSC_PAGE_PERFORMANCE_OBSERVED"
    assert solar["observed_url_aliases"][0]["impressions"] == 25
    assert solar["observed_url_aliases"][0]["clicks"] == 2
    assert solar["observed_url_aliases"][0]["evidence_ref"].startswith("gsc-page-row-sha256:")
    assert solar["reported_impressions_total_across_aliases"] is None
    assert solar["qualified_buyer_verified"] is False
    assert solar["google_indexing_verified"] is False
    assert d["total_returned_property_traffic_claimed"] is None
    assert d["publishing_authorized"] is False


def test_url_aliases_remain_distinct_with_separate_receipts():
    d = review_gsc_priority_pages(
        packet([
            row("https://www.empire-ai.co.uk/industries/hvac", clicks=1, impressions=4, ctr=.25),
            row("https://empire-ai.co.uk/industries/hvac", clicks=2, impressions=8, ctr=.25),
        ]),
        start_date=START, end_date=END,
    )
    hvac = next(x for x in d["priority_page_findings"] if x["product_key"] == "hvac")
    assert hvac["observed_alias_count"] == 2
    assert hvac["reported_impressions_total_across_aliases"] is None
    assert len({r["evidence_ref"] for r in hvac["observed_url_aliases"]}) == 2


def test_no_rows_does_not_assert_no_ranking_or_indexation():
    d = review_gsc_priority_pages(packet([]), start_date=START, end_date=END)
    assert len(d["priority_page_findings"]) == len(PRIORITY_PAGE_ROUTES) == 4
    assert all(x["status"] == "NO_PAGE_IN_RETURNED_GSC_ROWS"
               and x["google_indexing_verified"] is False
               for x in d["priority_page_findings"])
    assert d["indexation_verified"] is False


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(source="caller_supplied_unverified"),
    lambda x: x.update(site_url="sc-domain:example.com"),
    lambda x: x.update(dimensions=["query", "page"]),
    lambda x: x.update(data_state="partial"),
    lambda x: x.update(window=["2026-10-01", END]),
    lambda x: x.update(count=99),
    lambda x: x.update(items=[row("https://external.test/foo")]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk:9999/foo")]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/industries/solar"),
                              row("https://empire-ai.co.uk/industries/solar")]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/industries/solar", clicks=4, impressions=1)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/industries/solar", clicks=True)]),
    lambda x: x.update(items=[row("https://empire-ai.co.uk/industries/solar", ctr=2)]),
    lambda x: x.update(items=[{"keys": ["solar", "https://empire-ai.co.uk/"]}]),
])
def test_untrusted_gsc_page_data_fails_closed(mutate):
    d = packet([])
    mutate(d)
    # Some adversarial fixture mutations change count and data; every one
    # must fail before content is presented as authenticated observation.
    with pytest.raises(GscPageEvidenceError):
        review_gsc_priority_pages(d, start_date=START, end_date=END)
