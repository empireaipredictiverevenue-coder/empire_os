"""One EmpireOS Permit Intelligence weekday 08:00 local outreach planner.

Creates a DST-safe review-time schedule across London and the three actual US
business time zones. Never queues or executes sends. First-party address
appearance is NOT recipient permission, verified deliverability or buyer intent.
Activation must separately consume original Smart CRM, consent/suppression,
prior history, source-rights and founder exact-message release authorities.
"""
from __future__ import annotations

from collections import Counter
from datetime import date,datetime,time,timedelta,timezone
from typing import Any,Mapping
from zoneinfo import ZoneInfo

from empire_os.permit_multimarket_registry import digest
from empire_os.permit_national_volume_enrichment import (
    validate_enrichment,LIVE_GENERAL,LIVE_LIMITED,HISTORICAL,NO_EMAIL,
)

SCHEMA="empire.permit_data.national_permit_weekday_local_outreach_clock.v1"
LANES=(
    ("UK","Europe/London",()),
    ("US_EASTERN","America/New_York",("nyc","philadelphia")),
    ("US_CENTRAL","America/Chicago",("chicago","austin")),
    ("US_PACIFIC","America/Los_Angeles",("seattle","san_francisco")),
)
HOUR=8
MINUTE=0
MARKETS={m for _,_,markets in LANES for m in markets}


def _check_time(when:datetime)->datetime:
    if not isinstance(when,datetime) or when.utcoffset() is None:
        raise ValueError("outreach_clock_requires_aware_datetime")
    return when.astimezone(timezone.utc)


def due_at(*,when:datetime,tz_name:str)->bool:
    local=_check_time(when).astimezone(ZoneInfo(tz_name))
    return local.weekday()<5 and local.hour==HOUR and local.minute==MINUTE


def next_occurrences(*,when:datetime,tz_name:str,limit:int=5)->list[dict]:
    """Next >= current instant 08:00 local weekday starts, DST accounted for."""
    now=_check_time(when)
    if type(limit) is not int or not 1<=limit<=20:
        raise ValueError("outreach_clock_occurrence_limit")
    tz=ZoneInfo(tz_name)
    local=now.astimezone(tz)
    results=[]
    for delta in range(32):
        day=local.date()+timedelta(days=delta)
        if day.weekday()>4:continue
        tick=datetime.combine(day,time(HOUR,MINUTE),tzinfo=tz)
        utc=tick.astimezone(timezone.utc)
        if utc<now:continue
        results.append({
            "local_date":day.isoformat(),
            "local_wall_time":tick.isoformat(),
            "utc_instant":utc.isoformat(),
            "uk_wall_time":utc.astimezone(ZoneInfo("Europe/London")).isoformat(),
            "local_weekday":tick.strftime("%A"),
        })
        if len(results)==limit:return results
    raise ValueError("outreach_clock_no_weekday_found")


def build_clock(*,enrichment:Mapping[str,Any],at:datetime)->dict:
    validate_enrichment(enrichment)
    now=_check_time(at)
    source_at=datetime.fromisoformat(enrichment["evaluated_at_utc"]).astimezone(timezone.utc)
    if source_at>now or now-source_at>timedelta(days=30):
        raise ValueError("outreach_schedule_source_outside_review_window")
    rows=enrichment["companies"]
    if (len(rows)!=70 or enrichment["deduplicated_research_companies"]!=70
        or set(enrichment["by_market"])!=MARKETS):
        raise ValueError("original_seventy_company_market_map_changed")
    by_market={m:next(lane for lane in LANES if m in lane[2]) for m in MARKETS}
    allocations={lane[0]:[] for lane in LANES}
    seen=set()
    for row in rows:
        ident=row["stable_research_company_id"]
        if ident in seen or row["market_id"] not in by_market:
            raise ValueError("duplicate_or_unroutable_market")
        seen.add(ident)
        lane=by_market[row["market_id"]]
        tier=row["source_provenance_tier"]
        if tier==LIVE_GENERAL:workflow="REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND"
        elif tier==LIVE_LIMITED:workflow="HOLD_PURPOSE_RESTRICTED_ROUTE"
        elif tier==HISTORICAL:workflow="HOLD_HISTORICAL_SOURCE_RECHECK"
        elif tier==NO_EMAIL:workflow="HOLD_NO_BUSINESS_EMAIL"
        else:raise ValueError("unrecognised_source_contact_tier")
        allocations[lane[0]].append({
            "company_id":ident,"company":row["company"],
            "market_id":row["market_id"],"sector":row["sector"],
            "published_email_candidate":row["candidate_business_email"],
            "evidence_tier":tier,
            "owner_review_workflow":workflow,
            "original_suppression_clearance":False,
            "actual_recipient_verified":False,
            "email_deliverability_verified":False,
            "first_message_exact_copy_authorized":False,
            "permit_data_customer_use_authorized":False,
            "scheduled_for_send":False,
            "email_sent":False,
        })
    result_lanes=[]
    for lane_id,tz_name,markets in LANES:
        candidates=allocations[lane_id]
        candidates.sort(key=lambda r:(r["owner_review_workflow"],r["market_id"],r["company"]))
        local=now.astimezone(ZoneInfo(tz_name))
        next_slots=next_occurrences(when=now,tz_name=tz_name)
        current_id=f"{lane_id}:{local.date().isoformat()}:0800"
        stats=Counter(x["owner_review_workflow"] for x in candidates)
        result_lanes.append({
            "lane_id":lane_id,"tz_name":tz_name,
            "market_ids":list(markets),
            "local_review_start":"08:00",
            "weekdays_only":True,
            "local_now":local.isoformat(),
            "within_local_0800_minute":due_at(when=now,tz_name=tz_name),
            "current_local_slot_identity":current_id,
            "next_five_business_day_review_slots":next_slots,
            "company_research_count":len(candidates),
            "email_candidates":sum(x["published_email_candidate"] is not None for x in candidates),
            "first_party_general_review_queue_count":stats["REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND"],
            "source_or_mailbox_hold_count":len(candidates)-stats["REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND"],
            "recipient_approved_count":0,
            "ready_to_send_count":0,
            "automatic_send_enabled":False,
            "region_research_queue":candidates,
        })
    output={
        "schema_version":SCHEMA,
        "evaluated_at_utc":now.isoformat(),
        "original_source_enrichment_sha256":enrichment["enrichment_sha256"],
        "original_stack":"EMPIREOS_NATIONAL_PERMIT_ONE_SMART_CRM",
        "schedule_policy":"MON_FRI_0800_RECIPIENT_LOCAL_CIVIL_TIME",
        "uk_zone":"Europe/London",
        "business_timezone_lanes":4,
        "actual_us_timezone_lanes":3,
        "destination_market_count":len(MARKETS),
        "research_companies":len(rows),
        "published_business_email_candidates":sum(x["candidate_business_email"] is not None for x in rows),
        "owner_review_general_inbox_count":sum(x["source_provenance_tier"]==LIVE_GENERAL for x in rows),
        "schedule_live":False,
        "automatic_mail_delivery_enabled":False,
        "automatic_prospect_send_count":0,
        "recipient_authority_checked_count":0,
        "original_smart_crm_suppression_cleared_count":0,
        "approved_send_count":0,
        "new_empiredb_writes":0,
        "new_smart_crm_writes":0,
        "revenue_verified_usd":"0.00",
        "execution_authority":"none",
        "regional_clocks":result_lanes,
    }
    output["weekday_outreach_clock_sha256"]=digest(output)
    return output


def validate_clock(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("weekday_outreach_clock_sha256")!=digest({
            k:v for k,v in report.items() if k!="weekday_outreach_clock_sha256"})
        or report.get("original_stack")!="EMPIREOS_NATIONAL_PERMIT_ONE_SMART_CRM"
        or report.get("schedule_policy")!="MON_FRI_0800_RECIPIENT_LOCAL_CIVIL_TIME"
        or report.get("uk_zone")!="Europe/London"
        or report.get("business_timezone_lanes")!=4
        or report.get("actual_us_timezone_lanes")!=3
        or report.get("destination_market_count")!=6
        or report.get("research_companies")!=70
        or report.get("published_business_email_candidates")!=64
        or report.get("owner_review_general_inbox_count")!=10
        or report.get("schedule_live") is not False
        or report.get("automatic_mail_delivery_enabled") is not False
        or report.get("automatic_prospect_send_count")!=0
        or report.get("recipient_authority_checked_count")!=0
        or report.get("original_smart_crm_suppression_cleared_count")!=0
        or report.get("approved_send_count")!=0
        or report.get("new_empiredb_writes")!=0
        or report.get("new_smart_crm_writes")!=0
        or report.get("revenue_verified_usd")!="0.00"
        or report.get("execution_authority")!="none"):
        raise ValueError("unsafe_permit_weekday_outreach_clock")
    lanes=report.get("regional_clocks")
    if not isinstance(lanes,list) or len(lanes)!=4:
        raise ValueError("outreach_clock_lane_count_or_identity_changed")
    now=datetime.fromisoformat(report["evaluated_at_utc"])
    seen=set()
    counter=Counter()
    for lane,expected in zip(lanes,LANES):
        lane_id,zone,markets=expected
        entries=lane.get("region_research_queue")
        if (lane.get("lane_id")!=lane_id or lane.get("tz_name")!=zone
            or lane.get("market_ids")!=list(markets)
            or lane.get("local_review_start")!="08:00"
            or lane.get("weekdays_only") is not True
            or lane.get("within_local_0800_minute") is not due_at(when=now,tz_name=zone)
            or lane.get("next_five_business_day_review_slots")!=next_occurrences(when=now,tz_name=zone)
            or lane.get("current_local_slot_identity")!=(
                f"{lane_id}:{now.astimezone(ZoneInfo(zone)).date().isoformat()}:0800")
            or lane.get("local_now")!=now.astimezone(ZoneInfo(zone)).isoformat()
            or lane.get("recipient_approved_count")!=0
            or lane.get("ready_to_send_count")!=0
            or lane.get("automatic_send_enabled") is not False
            or not isinstance(entries,list)
            or lane.get("company_research_count")!=len(entries)
            or lane.get("email_candidates")!=sum(x.get("published_email_candidate") is not None for x in entries)):
            raise ValueError("outreach_clock_local_rule_or_dispatch_state_invalid")
        count_general=0
        for row in entries:
            company_id=row.get("company_id")
            if company_id in seen or row.get("market_id") not in markets:
                raise ValueError("duplicate_recipient_research_or_wrong_us_timezone")
            seen.add(company_id)
            tier=row.get("evidence_tier")
            workflow={
                LIVE_GENERAL:"REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND",
                LIVE_LIMITED:"HOLD_PURPOSE_RESTRICTED_ROUTE",
                HISTORICAL:"HOLD_HISTORICAL_SOURCE_RECHECK",
                NO_EMAIL:"HOLD_NO_BUSINESS_EMAIL",
            }.get(tier)
            if (row.get("owner_review_workflow")!=workflow
                or row.get("original_suppression_clearance") is not False
                or row.get("actual_recipient_verified") is not False
                or row.get("email_deliverability_verified") is not False
                or row.get("first_message_exact_copy_authorized") is not False
                or row.get("permit_data_customer_use_authorized") is not False
                or row.get("scheduled_for_send") is not False
                or row.get("email_sent") is not False):
                raise ValueError("outreach_clock_research_promoted_to_approved_send")
            count_general+=workflow=="REVIEW_GENERAL_BUSINESS_ROUTE_NO_SEND"
            counter[tier]+=1
        if (lane.get("first_party_general_review_queue_count")!=count_general
            or lane.get("source_or_mailbox_hold_count")!=len(entries)-count_general):
            raise ValueError("outreach_clock_company_route_count_mismatch")
    if (len(seen)!=70 or sum(counter.values())!=70
        or counter[LIVE_GENERAL]!=10
        or sum(l["email_candidates"] for l in lanes)!=64
        or len(lanes[0]["region_research_queue"])!=0):
        raise ValueError("outreach_clock_evidence_allocation_changed")
