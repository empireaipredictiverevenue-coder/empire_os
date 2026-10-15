"""Real GSC-shaped receipts drive review without invented buyer demand."""
from copy import deepcopy
from datetime import date, timedelta
import json
import pytest

from empire_os.search_intelligence.organic_revenue_baseline import review_owned_organic_baseline


def _row(query, url, impressions, clicks, position=12.0):
    return {
        "keys": [query, url],
        "impressions": impressions,
        "clicks": clicks,
        "position": position,
        "ctr": clicks / impressions if impressions else 0,
    }


def _packet(rows):
    return {
        "available": True, "source": "google_search_console",
        "site_url": "sc-domain:empire-ai.co.uk",
        "count": len(rows), "items": rows,
    }


def _review(current=None, previous=None, **kwargs):
    return review_owned_organic_baseline(
        site_url="sc-domain:empire-ai.co.uk",
        tenant_id="empire-ai", site_id="empire-ai.co.uk",
        current=current if current is not None else _packet([
            _row("antenna approvals", "https://empire-ai.co.uk/aeo/antenna-install/FAR/", 5, 0, 75),
            _row("empire ai", "https://www.empire-ai.co.uk/", 7, 0, 8),
            _row("empire ai singapore", "http://www.empire-ai.co.uk/", 1, 0, 20),
        ]),
        previous=previous if previous is not None else _packet([
            _row("other query", "https://empire-ai.co.uk/blog/research/", 13, 1),
        ]),
        current_start="2026-09-14",current_end="2026-10-12",
        previous_start="2026-08-16", previous_end="2026-09-13",
        **kwargs,
    )


def test_owned_live_gsc_plan_is_bounded_with_observed_only_counts():
    result=_review()
    assert result["gsc_property"]=="sc-domain:empire-ai.co.uk"
    assert result["current"]["impressions"]==13
    assert result["current"]["clicks"]==0
    assert result["current"]["legacy_aeo_page_impressions"]==5
    assert result["current"]["brand_query_impressions"]==8
    assert result["previous"]["clicks"]==1
    assert result["current"]["homepage_scheme_or_host_variations_observed"] is True
    assert len(result["tasks"])==4
    assert result["tasks"][1]["status"]=="EVIDENCE_HOLD"
    assert result["tasks"][2]["automatic_noindex_or_deletion_allowed"] is False
    assert result["tasks"][3]["automatic_redirect_or_site_change_allowed"] is False
    assert result["direct_publishing_allowed"] is False
    assert result["production_mutation"] is False
    assert result["external_model_calls"]==0
    assert result["offer_eligibility_verified"] is False
    assert result["current"]["top_pages"][0]["current_live_page_verified"] is False


@pytest.mark.parametrize("bad",[
    "sc-domain:another-site.co.uk",
    "https://empire-ai.co.uk",
    "sc-domain:empire-ai.co.uk.evil.test",
])
def test_cross_property_or_unapproved_property_denied(bad):
    with pytest.raises(ValueError,match=".*property.*"):
        review_owned_organic_baseline(
            site_url=bad,tenant_id="empire-ai",site_id="empire-ai.co.uk",
            current=_packet([]),previous=_packet([]),
            current_start="2026-09-14",current_end="2026-10-12",
            previous_start="2026-08-16",previous_end="2026-09-13",
        )


@pytest.mark.parametrize("bad_url",[
    "https://empire-ai.co.uk.evil.test/page",
    "https://bad.empire-ai.co.uk/page",
    "https://alice@empire-ai.co.uk/",
    "http://127.0.0.1:8771/",
    "javascript:alert(1)",
    "https://empire-ai.co.uk/#frag",
])
def test_non_owned_or_suspicious_page_cannot_become_evidence(bad_url):
    with pytest.raises(ValueError,match="nonowned_or_invalid_gsc_page_url"):
        _review(current=_packet([_row("empire ai",bad_url,1,0)]))


def test_cross_tenant_denied():
    with pytest.raises(ValueError,match="owned_tenant_site_binding_required"):
        review_owned_organic_baseline(
            site_url="sc-domain:empire-ai.co.uk",
            tenant_id="other-tenant", site_id="empire-ai.co.uk",
            current=_packet([]), previous=_packet([]),
            current_start="2026-09-14", current_end="2026-10-12",
            previous_start="2026-08-16", previous_end="2026-09-13",
        )


def test_missing_data_is_unknown_not_zero_or_marketed_as_revenue():
    result=_review(current=_packet([]),previous=_packet([]))
    assert result["current"]["impressions"]==0
    assert result["current"]["ctr_percent"] is None
    assert result["tasks"][0]["verified_buyer_enquiries"] is None
    assert result["tasks"][0]["verified_sales"] is None
    assert result["tasks"][0]["revenue"] is None
    assert len(result["tasks"])==2


@pytest.mark.parametrize("metrics",[
    {"impressions":-1},
    {"clicks":2},
    {"position":0},
    {"ctr":1.5},
    {"ctr":float("nan")},
    {"impressions":True},
])
def test_impossible_or_fabricated_gsc_metrics_rejected(metrics):
    row=_row("empire ai","https://empire-ai.co.uk/",1,0)
    row.update(metrics)
    with pytest.raises(ValueError,match="invalid_gsc|inconsistent_gsc"):
        _review(current=_packet([row]))


def test_duplicate_rows_and_untrusted_source_rejected():
    row=_row("empire ai","https://empire-ai.co.uk/",1,0)
    with pytest.raises(ValueError,match="duplicate_gsc"):
        _review(current=_packet([row,row]))
    untrusted=_packet([row])
    untrusted["source"]="self_reported_keywords"
    with pytest.raises(ValueError,match="unverified_or_cross_property"):
        _review(current=untrusted)
    missing=_packet([row])
    missing["count"]=0
    with pytest.raises(ValueError,match="count_mismatch"):
        _review(current=missing)


def test_row_limit_truncation_refused():
    p=_packet([])
    row=_row("empire ai","https://empire-ai.co.uk/",1,0)
    p["items"]=[dict(row, keys=[f"query {i}",row["keys"][1]]) for i in range(1000)]
    p["count"]=1000
    with pytest.raises(ValueError,match="truncated"):
        _review(current=p)


def test_non_comparable_time_windows_rejected():
    data={
        "site_url":"sc-domain:empire-ai.co.uk",
        "tenant_id":"empire-ai","site_id":"empire-ai.co.uk",
        "current":_packet([]),"previous":_packet([]),
        "current_start":"2026-09-14","current_end":"2026-10-12",
        "previous_start":"2026-09-10","previous_end":"2026-10-08",
    }
    with pytest.raises(ValueError,match="not_comparable"):
        review_owned_organic_baseline(**data)


def test_gsc_legacy_inspection_is_not_an_order_to_delete_pages():
    result=_review()
    assert all("authority" not in task for task in result["tasks"])
    assert not result["direct_publishing_allowed"]
    assert result["tasks"][2]["next_action"].startswith("inspect")


def _daily_row(day, impressions, clicks, position=12.0):
    return {
        "keys": [day], "impressions": impressions, "clicks": clicks,
        "ctr": clicks / impressions if impressions else 0,
        "position": position if impressions else 0,
    }


def _daily_packet(rows):
    return {
        "available": True, "source": "google_search_console",
        "site_url": "sc-domain:empire-ai.co.uk",
        "dimensions": ["date"],
        "count": len(rows), "items": rows,
    }


def test_sitewide_daily_truth_overrides_incomplete_query_page_aggregation():
    current = _packet([_row("empire ai","https://www.empire-ai.co.uk/",23,0)])
    previous = _packet([_row("generic","https://empire-ai.co.uk/",93,0)])
    report = _review(
        current=current, previous=previous,
        current_daily=_daily_packet([
            _daily_row("2026-09-14",54,1),
            _daily_row("2026-09-15",23,0),
        ]),
        previous_daily=_daily_packet([
            _daily_row("2026-08-16",0,0),
            _daily_row("2026-08-17",164,3),
        ]),
    )
    assert report["sitewide_current"]["impressions"]==77
    assert report["sitewide_current"]["clicks"]==1
    assert report["sitewide_previous"]["impressions"]==164
    assert report["sitewide_previous"]["clicks"]==3
    assert report["sitewide_current"]["visibility_gap_unattributed_impressions"]==54
    assert report["sitewide_current"]["visibility_gap_unattributed_clicks"]==1
    assert report["sitewide_current"]["query_page_impression_coverage_percent"]==29.87
    assert report["measurement_status"]=="GSC_DAILY_SITEWIDE_PLUS_QUERY_PAGE"
    assert report["tasks"][0]["sitewide_traffic_truth_available"] is True
    assert report["tasks"][0]["verified_sales"] is None


def test_missing_daily_report_remains_unknown_not_zero():
    report=_review()
    assert report["sitewide_current"] is None
    assert report["sitewide_previous"] is None
    assert report["measurement_status"]=="QUERY_PAGE_ONLY_SITEWIDE_UNKNOWN"
    assert report["tasks"][0]["status"]=="EVIDENCE_HOLD"
    with pytest.raises(ValueError,match="both_sitewide"):
        _review(current_daily=_daily_packet([]))


@pytest.mark.parametrize("bad",[
    {"available":False},
    {"source":"self_reported"},
    {"dimensions":["query"]},
    {"site_url":"sc-domain:other.test"},
    {"count":0},
])
def test_daily_malformed_source_or_count_fail_closed(bad):
    current_daily=_daily_packet([_daily_row("2026-09-14",25,0)])
    current_daily.update(bad)
    with pytest.raises(ValueError,match="gsc_daily|cross_property"):
        _review(
            current=_packet([_row("empire ai","https://empire-ai.co.uk/",2,0)]),
            current_daily=current_daily,
            previous_daily=_daily_packet([]),
        )


def test_daily_rows_outside_window_duplicates_and_bad_metrics_rejected():
    base=_daily_row("2026-09-14",3,0)
    for rows in (
        [base,base],
        [_daily_row("2026-08-01",3,0)],
        [dict(base, position=0)],
        [dict(base, clicks=4)],
        [dict(base, ctr=float("inf"))],
    ):
        with pytest.raises(ValueError,match="gsc_daily|inconsistent"):
            _review(
                current=_packet([_row("empire ai","https://empire-ai.co.uk/",1,0)]),
                current_daily=_daily_packet(rows),
                previous_daily=_daily_packet([]),
            )


def test_unsupported_query_volume_is_never_inferred_from_impression_count():
    review=_review(
        current_daily=_daily_packet([_daily_row("2026-09-14",13,0)]),
        previous_daily=_daily_packet([_daily_row("2026-08-16",13,1)]),
    )
    assert "monthly_search_volume" not in review
    assert review["sitewide_current"]["hidden_queries_identified"] is False
    assert review["sitewide_current"]["commercial_source_attribution_verified"] is False
    assert review["direct_publishing_allowed"] is False
