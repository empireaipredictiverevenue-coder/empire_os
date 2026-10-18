"""Offline integration test for page-only GSC report; no real Google API."""
import pytest

from scripts.review_live_gsc_page_performance import (
    build_live_priority_page_report, local_gsc_get, BASE,
)
from empire_os.search_intelligence.first_party_gsc_page_review import GscPageEvidenceError


START, END = "2026-10-08", "2026-10-17"


def test_page_level_reader_preserves_commercial_page_metrics():
    requested=[]
    def get(path, *, params=None):
        requested.append((path,params))
        if path.endswith("/status"):
            return {"available":True,"site_url":"sc-domain:empire-ai.co.uk"}
        return {
            "available":True, "source":"google_search_console",
            "site_url":"sc-domain:empire-ai.co.uk",
            "dimensions":["page"],"data_state":"final",
            "window":[START,END],"count":1,"limit":1000,
            "items":[{
                "keys":["https://www.empire-ai.co.uk/industries/roofing"],
                "clicks":3,"impressions":9,"ctr":1/3,"position":4.8,
            }],
        }
    result=build_live_priority_page_report(
        start_date=START,end_date=END,get_json=get,
    )
    roofing=next(x for x in result["priority_page_findings"]
                 if x["product_key"]=="roofing")
    assert roofing["observed_url_aliases"][0]["clicks"]==3
    assert roofing["observed_url_aliases"][0]["impressions"]==9
    assert roofing["qualified_buyer_verified"] is False
    assert result["commercial_conversion_verified"] is False
    assert requested[0][0]=="/search-console/status"
    assert requested[1]==("/search-console/pages",{
        "start_date":START,"end_date":END,"limit":1000,
    })
    assert BASE=="http://127.0.0.1:8771/v1/search"


def test_page_only_reader_does_not_fallback_to_query_page_report():
    requested=[]
    def get(path, *, params=None):
        requested.append(path)
        if path.endswith("/status"):
            return {"available":True,"site_url":"sc-domain:empire-ai.co.uk"}
        raise OSError("page_only_gsc_reader_not_yet_deployed")
    with pytest.raises(OSError):
        build_live_priority_page_report(
            start_date=START,end_date=END,get_json=get,
        )
    assert "/search-console/observations" not in requested


@pytest.mark.parametrize("start,end",[
    ("2026-10-17","2026-10-08"),
    ("2026-09-01","2026-10-17"),
    ("bad","2026-10-17"),
])
def test_invalid_period_rejected_before_network(start,end):
    with pytest.raises(GscPageEvidenceError):
        build_live_priority_page_report(
            start_date=start,end_date=end,
            get_json=lambda *a,**kw:pytest.fail("NETWORK_MUST_NOT_RUN"),
        )


def test_local_gsc_get_allowlist_fails_before_network():
    with pytest.raises(GscPageEvidenceError):
        local_gsc_get("/search-console/observations")
