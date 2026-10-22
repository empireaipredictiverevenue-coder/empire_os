"""Official SAM.gov public-notice review, deliberately outside SaaS lead scoring.

Only manually observed official webpage fields are captured. Indexed-page
text does not substitute for SAM.gov live notice/API status, attachments,
qualification, or a separately signed editorial admission.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from math import isfinite
from typing import Any, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import re

SCHEMA="empire.jev.sam_public_contract_review.v1"
INPUT_SCHEMA="empire.jev.sam_public_contract_sources.v1"
PINNED_OFFICIAL_DATES={
    "W9127826RA089":("2026-10-05","2026-10-05","2026-11-05T14:00:00-06:00"),
    "36C25727Q0022":("2026-09-22","2026-10-09","2026-10-28T15:00:00-05:00"),
    "140L4326Q0127":("2026-09-24","2026-10-15","2026-10-23T17:00:00-06:00"),
}
FIXED_NOTICES={
    "W9127826RA089":("general_contractor","238990","TOTAL_SMALL_BUSINESS",
                     "9c89a95ffe824dc3badb12b63e0109b2"),
    "36C25727Q0022":("roofing","238160",
                      "SERVICE_DISABLED_VETERAN_OWNED_SMALL_BUSINESS",
                      "ec71e534432b474abf888a7c9eb2c89c"),
    "140L4326Q0127":("hvac","238220","TOTAL_SMALL_BUSINESS",
                      "12d361c6fdc7478f9a8e1406cd054fcb"),
}


def _current_band(seconds_left:float)->str:
    if seconds_left <= 0:
        return "PAST_DEADLINE_NO_BID_INFERENCE"
    if seconds_left < 48*3600:
        return "DEADLINE_WITHIN_48_HOURS"
    if seconds_left < 7*24*3600:
        return "DEADLINE_WITHIN_SEVEN_DAYS"
    return "LATER_DEADLINE_OWNER_VERIFY"


def reconcile_official_work_notices(source:Mapping[str,Any], *,
                                     now:datetime)->dict[str,Any]:
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware review clock required")
    as_of=now.astimezone(timezone.utc)
    if (not isinstance(source,Mapping)
        or source.get("schema_version")!=INPUT_SCHEMA
        or source.get("status")!="OFFICIAL_PUBLIC_NOTICE_FIELDS_OBSERVED_ATTACHMENTS_UNREVIEWED"
        or source.get("verification_surface")!="official_sam_gov_public_text_via_indexed_web_result"
        or source.get("live_api_availability_confirmed") is not False
        or source.get("sam_notice_attachments_inspected") is not False
        or source.get("buyer_of_empire_ai_services_verified") is not False
        or source.get("bids_or_proposals_authorized") is not False
        or source.get("outbound_authorized") is not False
        or source.get("source_rights_and_vendor_eligibility_approved") is not False):
        raise ValueError("source record cannot grant original procurement authority")
    try:
        reviewed=date.fromisoformat(source.get("review_date_utc"))
    except (TypeError,ValueError):
        raise ValueError("public source observation date unavailable") from None
    # A static manual web observation gets old quickly; never call it a live
    # source even on the same day. Past/future dates require refresh.
    age_days=(as_of.date()-reviewed).days
    if age_days < 0:
        raise ValueError("dated original observation is in the future")
    receipt_current_for_owner_review=age_days<=1
    originals=source.get("opportunities")
    if not isinstance(originals,list) or len(originals)!=len(FIXED_NOTICES):
        raise ValueError("expected only the three owner-supplied notices")
    expected=set(FIXED_NOTICES)
    output=[]
    for source_row in originals:
        if not isinstance(source_row,Mapping):
            raise ValueError("invalid public notice")
        nid=source_row.get("notice_id")
        if not isinstance(nid,str) or nid not in expected:
            raise ValueError("unexpected or duplicated notice ID")
        expected.remove(nid)
        niche,naics,aside,uuid=FIXED_NOTICES[nid]
        parsed=urlsplit(source_row.get("exact_url",""))
        if (parsed.scheme!="https" or parsed.netloc!="sam.gov"
            or parsed.path!=f"/opp/{uuid}/view" or parsed.query or parsed.fragment
            or source_row.get("sector")!=niche
            or source_row.get("naics_code")!=naics
            or source_row.get("set_aside")!=aside
            or (source_row.get("original_posted_local_date"),
                source_row.get("last_updated_local_date"),
                source_row.get("deadline_local"))!=PINNED_OFFICIAL_DATES[nid]
            or source_row.get("opportunity_kind")!="CONTRACTOR_WORK_PROCUREMENT"
            or source_row.get("original_sam_page_reported_status")!="Active"
            or not all(isinstance(source_row.get(f),str)
                       and 0<len(source_row[f])<=300
                       for f in ("title","purchasing_agency","work_scope",
                                 "location_summary","deadline_zone"))
            or source_row.get("original_attachment_or_piee_package_verified") is not False
            or source_row.get("vendor_set_aside_eligibility_verified") is not False
            or source_row.get("agency_purchase_of_leadgen_or_saas_verified") is not False):
            raise ValueError("untrusted source/identity/set-aside fields")
        try:
            due=datetime.fromisoformat(source_row["deadline_local"])
            original_posted=date.fromisoformat(source_row["original_posted_local_date"])
            last_updated=date.fromisoformat(source_row["last_updated_local_date"])
            legal_zone=ZoneInfo(source_row["deadline_zone"])
            if due.utcoffset() is None or due.utcoffset()!=due.astimezone(legal_zone).utcoffset():
                raise ValueError("deadline offset mismatches legal notice zone")
            if not (original_posted<=last_updated<=due.date()):
                raise ValueError("invalid original publication/amendment dates")
            if due.date()<=date(2026,1,1) or due.date()>date(2027,12,31):
                raise ValueError("implausible fixed public notice deadline")
        except (KeyError,TypeError,ValueError,OverflowError) as exc:
            raise ValueError("invalid official notice deadline or update") from exc
        seconds=(due.astimezone(timezone.utc)-as_of).total_seconds()
        if not isfinite(seconds):
            raise ValueError("unusable source clock")
        output.append({
            "notice_id":nid,
            "official_notice_url":source_row["exact_url"],
            "title":source_row["title"],
            "contracting_entity":source_row["purchasing_agency"],
            "target_industry":niche,
            "naics_code":naics,
            "set_aside":aside,
            "work_scope":source_row["work_scope"],
            "location_summary":source_row["location_summary"],
            "last_public_notice_update_date":source_row["last_updated_local_date"],
            "deadline_local":source_row["deadline_local"],
            "deadline_zone":source_row["deadline_zone"],
            "time_band":_current_band(seconds),
            "time_to_deadline_hours_rounded":round(max(seconds,0)/3600,2),
            "source_listing_reported_active":True,
            "live_sam_notice_api_state_confirmed":False,
            "full_bid_package_and_amendments_reviewed":False,
            "individual_vendor_set_aside_eligibility_verified":False,
            "public_contract_work_is_not_purchase_of_empire_services":True,
            "agency_buys_empire_leadgen_or_saas_verified":False,
            "direct_empire_saas_sales_lead_qualified":False,
            "brokerage_or_subcontract_eligibility_verified":False,
            "next_owner_review":[
                "CONFIRM_LIVE_SAM_NOTICE_STATUS_AND_ALL_AMENDMENTS",
                "REVIEW_OFFICIAL_ATTACHMENTS_AND_PIEE_PORTAL_IF_APPLICABLE",
                "CHECK_US_VENDOR_REGISTRATION_SET_ASIDE_AND_ACTUAL_WORK_CAPABILITY",
                "CHECK_PERMITTED_PROCUREMENT_SUPPORT_ROLE_AND_SCOPE",
            ],
            "outreach_authorized":False,
            "automatic_bid_authorized":False,
        })
    if expected:
        raise ValueError("missing required official notice")
    output.sort(key=lambda r:r["deadline_local"])
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"OFFICIAL_NOTICE_FIELDS_REVIEWED_SEPARATE_CONTRACTOR_WORK_PIPELINE",
        "review_date_utc":as_of.date().isoformat(),
        "manual_source_snapshot_observation_date_utc":source["review_date_utc"],
        "manual_snapshot_recent_for_owner_review":receipt_current_for_owner_review,
        "notice_count":len(output),
        "deadline_watch_counts":{
            key:sum(row["time_band"]==key for row in output)
            for key in (
                "DEADLINE_WITHIN_48_HOURS",
                "DEADLINE_WITHIN_SEVEN_DAYS",
                "LATER_DEADLINE_OWNER_VERIFY",
                "PAST_DEADLINE_NO_BID_INFERENCE",
            )
        },
        "notices":output,
        "direct_empire_saas_buying_requests_verified":0,
        "approved_contractors_for_bid":0,
        "buyer_scout_payable_lead_buyboxes_verified":0,
        "independently_approved_data_rights":False,
        "no_raw_person_or_contact_export":True,
        "automatic_outbound_allowed":False,
        "crm_writes":False,
        "financial_actions":False,
        "model_calls":0,
        "execution_authority":"none",
    }
