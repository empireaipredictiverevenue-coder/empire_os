"""Bounded full-issued-day DOB NOW -> OTI buildings -> DCP PLUTO review.

On-demand, read-only official-source inspection. Reuses EXISTING DOB keyset
reader, exact source day counts, event merger, and 40-event property join.
Does not touch the canonical signal inbox, schedulers, EmpireDB or CRM.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import re

from empire_os.dobnow_incremental import _merge, official_day_row_count
from empire_os.lead_sources.nyc_dobnow import (
    MAX_ROWS, LOOKBACK_DAYS, current_event_sample,
)
from empire_os.permit_property_source_join import (
    SCHEMA as SINGLE_PAGE_SCHEMA,
    MAX_EVENTS, review_official_building_landuse,
)

SCHEMA="empire.permit_property_three_agency_full_day.v2"
MAX_DAY_SOURCE_PAGES=30
MAX_DAILY_SOURCE_ROWS=MAX_DAY_SOURCE_PAGES*MAX_ROWS


def _date(day: str, now: datetime) -> None:
    if not isinstance(day,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day):
        raise ValueError("INVALID_OFFICIAL_PERMIT_DATE")
    try:
        parsed=datetime.fromisoformat(day).date()
    except ValueError as e:
        raise ValueError("INVALID_OFFICIAL_PERMIT_DATE") from e
    if not now.date()-timedelta(days=LOOKBACK_DAYS)<=parsed<=now.date():
        raise ValueError("PERMIT_DATE_OUTSIDE_BOUNDED_WINDOW")


def review_full_official_day(
    day: str, *, now: datetime | None=None,
    fetch_page: Callable=current_event_sample,
    count_source_rows: Callable=official_day_row_count,
    join_property: Callable=review_official_building_landuse,
) -> dict[str,Any]:
    """Fail-closed only when a *whole* issued day agrees with official count.

    Real person, private addresses, owner names and direct contact fields
    are never selected. Even all three agency matches prove references only.
    """
    at=now or datetime.now(timezone.utc)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("OBSERVATION_CLOCK_MUST_BE_OFFSET_AWARE")
    at=at.astimezone(timezone.utc)
    _date(day,at)

    start_count=count_source_rows(day)
    if (not isinstance(start_count,dict)
            or type(start_count.get("count")) is not int
            or not 0<=start_count["count"]<=MAX_DAILY_SOURCE_ROWS
            or not isinstance(start_count.get("sha256"),str)):
        raise ValueError("SOURCE_DAY_EXCEEDS_BOUNDED_RESEARCH_CAP")
    expected=start_count["count"]

    staged={}
    source_page_receipts=[]
    cursor=None
    selected_rows=0
    complete=False
    for page in range(MAX_DAY_SOURCE_PAGES):
        review=fetch_page(now=at,issued_day=day,after_source_row_id=cursor)
        if (not isinstance(review,dict)
                or review.get("mode")!="OBSERVE"
                or review.get("no_sales_authority") is not True
                or review.get("issued_day")!=day):
            raise ValueError("UNTRUSTED_OFFICIAL_DOBNOW_PAGE")
        count=review.get("query_rows")
        last=review.get("last_source_row_id")
        if type(count) is not int or not 0<=count<=MAX_ROWS:
            raise ValueError("UNBOUNDED_OFFICIAL_DOBNOW_PAGE")
        if count>0 and (
                not isinstance(last,str) or last==cursor
                or not re.fullmatch(r"row-[a-z0-9._~-]{4,60}",last)):
            raise ValueError("OFFICIAL_SOURCE_ROW_CURSOR_NOT_ADVANCING")
        if count==0 and review.get("events"):
            raise ValueError("SOURCE_EMPTY_PAGE_WITH_EVENTS")
        for ev in review.get("events",[]):
            if not isinstance(ev,dict) or ev.get("issued_date")!=day:
                raise ValueError("EVENT_OUTSIDE_EXACT_ISSUED_DAY")
            _merge(staged,ev)
        selected_rows+=count
        if selected_rows>expected:
            raise ValueError("SOURCE_ROW_COUNT_OVERRUN")
        source_page_receipts.append({
            "page":page, "official_rows":count,
            "end_row_id":last,
            "two_dob_selected_response_sha256":review["source_response_sha256"],
        })
        cursor=last or cursor
        if count<MAX_ROWS:
            complete=True
            break
    if not complete:
        raise ValueError("SOURCE_DAY_INCOMPLETE_PAGE_CAP")
    end_count=count_source_rows(day)
    if (not isinstance(end_count,dict)
            or end_count.get("count")!=expected
            or expected!=selected_rows
            or not isinstance(end_count.get("sha256"),str)):
        raise ValueError("SOURCE_DAY_COUNT_CHANGED_OR_MISMATCHED")

    events=[staged[k] for k in sorted(staged)]
    all_diagnostics=[]
    property_chunks=[]
    for offset in range(0,len(events),MAX_EVENTS):
        batch=events[offset:offset+MAX_EVENTS]
        result=join_property(batch,now=at)
        if (not isinstance(result,dict)
                or result.get("schema")!=SINGLE_PAGE_SCHEMA
                or result.get("mode")!="OBSERVE"
                or result.get("execution_authority")!="none"
                or result.get("permit_event_count")!=len(batch)
                or len(result.get("diagnostics",[]))!=len(batch)
                or result.get("external_outreach_sent") is not False
                or result.get("data_warehouse_or_empiredb_mutated") is not False):
            raise ValueError("UNTRUSTED_PROPERTY_CHUNK")
        all_diagnostics.extend(result["diagnostics"])
        property_chunks.append({
            "chunk_index":len(property_chunks),
            "job_count":len(batch),
            "source_selected_response_receipts":
                result["source_selected_response_receipts"],
        })
    jobs=[x.get("permit_job_filing_ref") for x in all_diagnostics]
    if len(jobs)!=len(events) or len(set(jobs))!=len(events) or (
        set(jobs)!=set(staged)
    ):
        raise ValueError("INCOMPLETE_PROPERTY_JOIN_COVERAGE")
    statuses=Counter(x["building_tax_lot_evidence_state"] for x in all_diagnostics)
    uses=Counter(x["dcp_land_use_category"] for x in all_diagnostics)
    industrial=sum(x["industrial_tax_lot_context_corroborated"]
                   is True for x in all_diagnostics)
    if any(x.get("verified_business_buyer") is not False
           or x.get("warehouse_operation_verified") is not False
           or x.get("commercial_contact_authorized") is not False
           for x in all_diagnostics):
        raise ValueError("UNEXPECTED_COMMERCIAL_AUTHORITY_FROM_SOURCE_JOIN")

    return {
        "schema":SCHEMA,"mode":"OBSERVE",
        "reviewed_at_utc":at.isoformat(),"issued_day":day,
        "coverage_state":"FULL_ISSUED_DAY_OFFICIAL_COUNT_MATCH_AT_OBSERVATION",
        "source_datasets":{
            "dob_now_filings":"w9ak-ipjd",
            "dob_now_initial_permits":"rbx6-tga4",
            "oti_building_footprints":"5zhs-2jue",
            "dcp_pluto":"64uk-42ks",
        },
        "source_agencies":["NYC DOB","NYC OTI","NYC DCP"],
        "official_day_count_before_scan":expected,
        "official_day_count_after_scan":end_count["count"],
        "source_permit_row_count":selected_rows,
        "source_page_count":len(source_page_receipts),
        "source_page_receipts":source_page_receipts,
        "source_day_count_sha256":{
            "before":start_count["sha256"],"after":end_count["sha256"],
        },
        "property_review_chunk_count":len(property_chunks),
        "property_chunks":property_chunks,
        "permit_event_count":len(events),
        "event_level_join_status_counts":dict(sorted(statuses.items())),
        "event_level_landuse_category_counts":dict(sorted(uses.items())),
        "event_level_industrial_lot_context_count":industrial,
        "diagnostics":sorted(all_diagnostics,
                             key=lambda x:x["permit_job_filing_ref"]),
        "input_dob_sample_may_be_incomplete":False,
        "source_change_caveat":"Count agreement not atomic snapshot; source may alter unobserved rows with same count.",
        "physical_warehouse_or_site_activity_verified":False,
        "person_company_buyer_verified":False,
        "property_ownership_verified":False,
        "rights_review_required_for_customer_distribution":True,
        "external_outreach_sent":False,
        "data_warehouse_or_empiredb_mutated":False,
        "paid_provider_used":False,
        "execution_authority":"none",
    }
