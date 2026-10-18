"""First-party GSC daily trend proof, no synthesized chart points."""
from datetime import date, timedelta
import json
import pytest

from empire_os.search_intelligence.gsc_daily_series import (
    GscDailyEvidenceHeld, read_daily, validate_daily, SCHEMA,
)


START=date(2026,10,4)
END=date(2026,10,16)


def sample():
    return {
        "available":True,"source":"google_search_console",
        "dimensions":["date"],"site_url":"sc-domain:empire-ai.co.uk",
        "count":2,"limit":13,
        "items":[
            {"keys":["2026-10-16"],"clicks":0,"impressions":6,
             "ctr":0.0,"position":19.8333},
            {"keys":["2026-10-04"],"clicks":1,"impressions":8,
             "ctr":0.125,"position":29.3333},
        ],
    }


def test_observed_dates_are_sorted_but_missing_days_stay_missing():
    d=validate_daily(sample(),start=START,end=END)
    assert d["schema_version"]==SCHEMA
    assert d["status"]=="DATE_DIMENSION_ROWS_OBSERVED"
    assert d["date_window"]==["2026-10-04","2026-10-16"]
    assert d["days_observed"]==2
    assert len(d["days_missing_unreported"])==11
    assert d["rows"][0]["date"]=="2026-10-04"
    assert d["rows"][1]["date"]=="2026-10-16"
    assert d["reported_date_dimension_clicks"]==1
    assert d["reported_date_dimension_impressions"]==14
    assert d["missing_days_treated_as_zero"] is False
    assert d["independent_google_rank_positions_verified"] is False
    assert d["gsc_average_position_is_independent_serp_rank"] is False
    assert d["buyer_enquiries_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["database_writes"] is False
    assert d["outbound_sent"] is False
    assert not any("query" in point for point in d["rows"])


@pytest.mark.parametrize("mutate",[
    lambda d:d.update(site_url="sc-domain:attacker.invalid"),
    lambda d:d.update(dimensions=["query","page"]),
    lambda d:d.update(count=3),
    lambda d:d["items"][1]["keys"].__setitem__(0,"2026-10-16"),
    lambda d:d["items"][0].update(clicks=7),
    lambda d:d["items"][1].update(clicks=True),
    lambda d:d["items"][1].update(impressions=-1),
    lambda d:d["items"][1].update(position=float("nan")),
    lambda d:d["items"][1].update(ctr=1.2),
    lambda d:d["items"][0].update(keys=["2026-10-17"]),
    lambda d:d["items"][0].update(keys=["not-a-date"]),
])
def test_invalid_metric_or_provenance_fails_closed(mutate):
    x=sample();mutate(x)
    with pytest.raises(GscDailyEvidenceHeld):
        validate_daily(x,start=START,end=END)


def test_exact_allowlisted_loopback_request_no_credentials():
    requested=[]
    def transport(url):
        requested.append(url)
        return json.dumps(sample()).encode()
    result=read_daily(start=START,end=END,transport=transport)
    assert result["status"]=="DATE_DIMENSION_ROWS_OBSERVED"
    assert len(requested)==1
    assert requested[0].startswith("http://127.0.0.1:8771/v1/search/search-console/daily?")
    assert "start_date=2026-10-04" in requested[0]
    assert "end_date=2026-10-16" in requested[0]
    assert "limit=13" in requested[0]
    assert "token" not in requested[0]


def test_failed_source_held_not_zero_traffic():
    def fail(url):
        raise OSError("private-creds-NEVER PRINT")
    d=read_daily(start=START,end=END,transport=fail)
    assert d["status"]=="HELD_GSC_DAILY_SOURCE_UNAVAILABLE"
    assert d["days_observed"] is None
    assert d["reported_date_dimension_clicks"] is None
    assert d["reported_date_dimension_impressions"] is None
    assert d["rows"]==[]
    assert "private-creds" not in json.dumps(d)


def test_invalid_json_held_not_fabricated_zero():
    d=read_daily(start=START,end=END,transport=lambda url:b'{"keys":"bad"}')
    assert d["status"]=="HELD_GSC_DAILY_SOURCE_UNAVAILABLE"
    assert d["reported_date_dimension_clicks"] is None


def test_31_day_limit():
    with pytest.raises(GscDailyEvidenceHeld):
        read_daily(start=START,end=START+timedelta(days=31),transport=lambda _:b'{}')


def test_count_restricts_file_size():
    d=read_daily(start=START,end=END,transport=lambda url: b'x'*65537)
    assert d["status"]=="HELD_GSC_DAILY_SOURCE_UNAVAILABLE"


def test_snapshot_exposes_only_bounded_observed_daily_evidence():
    from empire_os.search_intelligence import department_snapshot as snapshot
    from empire_os.search_intelligence.department_integration_review import reconcile_department
    from tests.test_search_department_integrated_20261018 import evidence
    source=reconcile_department(**evidence())
    source['gsc_final_page_window']=['2026-10-04','2026-10-16']
    source['gsc_daily_chart']=validate_daily(sample(),start=START,end=END)
    source['gsc_daily_chart']['private_credential']='SECRET-NOT-SAFE'
    snapshot._reset_snapshot_for_tests()
    try:
        d=snapshot.read_department_snapshot(reader=lambda:source,clock=lambda:1.0)
    finally:
        snapshot._reset_snapshot_for_tests()
    assert d['gsc_daily_chart']['days_observed']==2
    assert d['gsc_daily_chart']['reported_date_dimension_clicks']==1
    assert d['gsc_daily_chart']['reported_date_dimension_impressions']==14
    assert d['gsc_returned_page_sample_impressions']==55
    assert d['gsc_daily_chart']['missing_days_treated_as_zero'] is False
    assert d['independent_google_rank_positions_verified'] is False
    assert 'SECRET-NOT-SAFE' not in json.dumps(d)


@pytest.mark.parametrize('modify',[
    lambda c:c['rows'][0].update(clicks=90),
    lambda c:c['rows'][0].update(query='private customer'),
    lambda c:c.update(reported_date_dimension_impressions=500),
    lambda c:c.update(independent_google_rank_positions_verified=True),
    lambda c:c.update(date_window=['2026-10-03','2026-10-16']),
    lambda c:c.update(days_missing_unreported=[]),
])
def test_untrusted_chart_cannot_reach_founder_snapshot(modify):
    from empire_os.search_intelligence import department_snapshot as snapshot
    from empire_os.search_intelligence.department_integration_review import reconcile_department
    from tests.test_search_department_integrated_20261018 import evidence
    source=reconcile_department(**evidence())
    source['gsc_final_page_window']=['2026-10-04','2026-10-16']
    source['gsc_daily_chart']=validate_daily(sample(),start=START,end=END)
    modify(source['gsc_daily_chart'])
    snapshot._reset_snapshot_for_tests()
    try:
        with pytest.raises(snapshot.DepartmentSnapshotUnavailable):
            snapshot.read_department_snapshot(reader=lambda:source,clock=lambda:1.0)
    finally:
        snapshot._reset_snapshot_for_tests()


def test_held_daily_source_does_not_erase_existing_seo_department():
    from empire_os.search_intelligence import department_snapshot as snapshot
    from empire_os.search_intelligence.department_integration_review import reconcile_department
    from empire_os.search_intelligence.gsc_daily_series import held
    from tests.test_search_department_integrated_20261018 import evidence
    source=reconcile_department(**evidence())
    source['gsc_final_page_window']=['2026-10-04','2026-10-16']
    source['gsc_daily_chart']=held(start=START,end=END)
    snapshot._reset_snapshot_for_tests()
    try:
        safe=snapshot.read_department_snapshot(reader=lambda:source,clock=lambda:1.0)
    finally:
        snapshot._reset_snapshot_for_tests()
    assert safe['status']=='DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN'
    assert safe['gsc_daily_chart']['status']=='HELD_GSC_DAILY_SOURCE_UNAVAILABLE'
    assert safe['gsc_daily_chart']['reported_date_dimension_clicks'] is None
    assert safe['gsc_returned_page_sample_clicks']==1
