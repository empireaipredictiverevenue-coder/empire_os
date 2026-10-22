"""Week-over-week GSC status taxonomy; zero is never invented from absent rows."""
from datetime import date, timedelta

import pytest

from empire_os.search_intelligence.weekly_two_page_outcomes import (
    build_weekly_report, weekly_window_bounds,
    WeeklyGscHeld, SITE_PAGES, PROPERTY,
)


def good_status():
    return {"available":True,"site_url":PROPERTY}


def page_row(url, clicks=0, impressions=0):
    return {
        "keys":[url], "clicks":clicks,"impressions":impressions,
        "ctr":clicks/impressions if impressions else 0,
        "position":9.0,
    }


def provider(*, previous=None, current=None, error=False):
    calls=[]
    def get(path, *, params=None):
        calls.append((path,params))
        if path=="/search-console/status":
            return good_status()
        if error:raise OSError("GSC unavailable")
        start=params["start_date"]
        end=params["end_date"]
        rows=(previous if len([x for x in calls if x[0]=="/search-console/pages"])==1 else current)
        rows=rows or []
        return {
            "source":"google_search_console","site_url":PROPERTY,"available":True,
            "dimensions":["page"],"data_state":"final",
            "window":[start,end],"count":len(rows),
            "items":rows,
        }
    return get,calls


def test_weekly_final_window_is_delayed_four_days():
    prev,cur=weekly_window_bounds(date(2026,11,2))
    assert [x.isoformat() for x in cur]==["2026-10-23","2026-10-29"]
    assert [x.isoformat() for x in prev]==["2026-10-16","2026-10-22"]


def test_absent_rows_not_confused_with_measured_zero():
    fake,calls=provider(previous=[],current=[
        page_row(SITE_PAGES[0],0,0),
        page_row(SITE_PAGES[1],0,3)
    ])
    r=build_weekly_report(as_of=date(2026,11,2),get_json=fake)
    assert r["current_window"]["pages"][0]["status"]=="MEASURED_ZERO"
    assert r["current_window"]["pages"][0]["impressions"]==0
    assert r["current_window"]["pages"][0]["ctr"] is None
    assert r["current_window"]["pages"][1]["status"]=="MEASURED_PAGE_METRICS"
    assert r["current_window"]["pages"][1]["clicks"]==0
    assert r["current_window"]["pages"][1]["ctr"]==0
    assert r["previous_window"]["pages"][0]["status"]=="NO_PAGE_IN_RETURNED_GSC_ROWS"
    assert r["previous_window"]["pages"][0]["impressions"] is None
    assert r["comparison_valid_after_release"] is False
    assert r["first_complete_postrelease_window"]==["2026-10-23","2026-10-29"]
    assert r["first_postrelease_final_check_from"]=="2026-11-02"
    assert r["new_postrelease_page_data_status"]=="POSTRELEASE_WINDOW_ELIGIBLE_FOR_GSC_REPORT"
    assert all(c["click_change"] is None for c in r["comparisons"])
    assert all(x[1]["limit"]==1000 for x in calls if x[0]=="/search-console/pages")


def test_two_full_postpublication_weeks_with_actual_observations_are_comparable():
    old=[page_row(SITE_PAGES[0],2,20),page_row(SITE_PAGES[1],1,5)]
    new=[page_row(SITE_PAGES[0],4,40),page_row(SITE_PAGES[1],2,10)]
    get,_=provider(previous=old,current=new)
    r=build_weekly_report(as_of=date(2026,11,9),get_json=get)
    assert r["comparison_valid_after_release"] is True
    assert [c["click_change"] for c in r["comparisons"]]==[2,1]
    assert [c["impression_change"] for c in r["comparisons"]]==[20,5]
    assert r["realised_revenue_verified"] is False
    assert r["automatic_jev_model_calls"]==0
    assert r["website_mutations"] is False


def test_absent_one_week_disables_growth_math_even_after_release():
    get,_=provider(previous=[],current=[page_row(SITE_PAGES[0],0,14)])
    r=build_weekly_report(as_of=date(2026,11,9),get_json=get)
    assert r["comparison_valid_after_release"] is True
    assert all(c["comparison_status"]=="NOT_COMPARABLE_OR_PAGE_ROW_MISSING" for c in r["comparisons"])


def test_unavailable_source_is_not_implicit_zero():
    get,_=provider(error=True)
    r=build_weekly_report(as_of=date(2026,11,2),get_json=get)
    assert r["current_window"]["source_status"]=="SOURCE_UNAVAILABLE"
    assert all(x["status"]=="SOURCE_UNAVAILABLE" and x["clicks"] is None for x in r["current_window"]["pages"])
    assert r["source_errors"]


def test_premature_window_gets_specific_non_final_status():
    get,_=provider()
    r=build_weekly_report(as_of=date(2026,10,23),get_json=get)
    assert all(p["status"]=="NO_PAGE_IN_RETURNED_GSC_ROWS" for p in r["current_window"]["pages"])
    # Although the historical window is final, the just-published page still
    # has no seven-day, fully postrelease measurement window.
    assert r["comparison_valid_after_release"] is False


def test_reject_query_page_dimension_and_unowned_pages():
    def fake(path, *, params=None):
        if path=="/search-console/status":return good_status()
        return {
            "source":"google_search_console","site_url":PROPERTY,
            "available":True,"dimensions":["query","page"],
            "data_state":"final",
            "window":[params["start_date"],params["end_date"]],
            "count":1,
            "items":[page_row(SITE_PAGES[0])]
        }
    r=build_weekly_report(as_of=date(2026,11,9),get_json=fake)
    assert r["source_errors"]
    assert all(p["clicks"] is None for p in r["current_window"]["pages"])


def test_reject_unreasonable_lags():
    get,_=provider()
    with pytest.raises(WeeklyGscHeld):
        build_weekly_report(as_of=date(2026,11,9),get_json=get,lag_days=1)
